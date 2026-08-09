"""Crew assembly and a single entry point for running one feasibility check."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crewai import Crew, Process
from pydantic import ValidationError

from .agent import (
    FeasibilityVerdict,
    GoalBrief,
    build_feasibility_agent,
    build_feasibility_task,
    build_llm,
)
from .config import has_llm_credentials, llm_model
from .trace import ToolCall, tool_trace


class MissingCredentialsError(RuntimeError):
    pass


@dataclass
class FeasibilityRun:
    """The result of one run: the verdict, and evidence of how it was reached."""

    verdict: FeasibilityVerdict | None
    raw: str
    model: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def tools_used(self) -> list[str]:
        return [call.name for call in self.tool_calls]

    @property
    def tool_errors(self) -> list[ToolCall]:
        return [call for call in self.tool_calls if not call.ok]


def _describe_validation_error(error: ValidationError) -> str:
    """Say which fields the model failed to produce, and what it sent instead."""
    problems = error.errors()
    lines = [
        f"The model's final answer did not fit FeasibilityVerdict "
        f"({len(problems)} problem(s)):"
    ]
    for problem in problems:
        field = ".".join(str(part) for part in problem["loc"]) or "(root)"
        lines.append(f"  {field}: {problem['msg']}")
    if problems:
        lines += ["", f"It sent: {problems[0].get('input')!r}"]
    return "\n".join(lines)


def build_feasibility_crew(brief: GoalBrief, model: str | None = None, verbose: bool = False) -> Crew:
    agent = build_feasibility_agent(llm=build_llm(model), verbose=verbose)
    return Crew(
        agents=[agent],
        tasks=[build_feasibility_task(brief, agent)],
        process=Process.sequential,
        verbose=verbose,
    )


def run_feasibility(
    brief: GoalBrief,
    model: str | None = None,
    verbose: bool = False,
    trace: bool = False,
    sink: Any = None,
) -> FeasibilityRun:
    """Run the agent once.

    `trace` echoes each tool call to stdout as it happens; `sink` forwards the
    same calls as dicts to a caller that wants to stream them elsewhere.
    """
    if not has_llm_credentials():
        raise MissingCredentialsError(
            "No LLM credentials found. Put OPENROUTER_API_KEY in crew/.env "
            "(see .env.example), or export it in your shell."
        )

    resolved_model = model or llm_model()
    crew = build_feasibility_crew(brief, model=resolved_model, verbose=verbose)

    with tool_trace(echo=trace, sink=sink) as recorded:
        try:
            output = crew.kickoff()
        except ValidationError as error:
            # CrewAI raises when the final answer will not fit `output_pydantic`.
            # A run that got this far still produced a tool trace worth seeing, so
            # report the mismatch instead of surfacing a stack trace.
            return FeasibilityRun(
                verdict=None,
                raw=_describe_validation_error(error),
                model=resolved_model,
                tool_calls=recorded.calls,
            )

    usage: dict[str, Any] = {}
    if getattr(output, "token_usage", None) is not None:
        usage = (
            output.token_usage.model_dump()
            if hasattr(output.token_usage, "model_dump")
            else dict(output.token_usage)
        )

    verdict = output.pydantic if isinstance(output.pydantic, FeasibilityVerdict) else None

    return FeasibilityRun(
        verdict=verdict,
        raw=str(output.raw),
        model=resolved_model,
        tool_calls=recorded.calls,
        usage=usage,
    )
