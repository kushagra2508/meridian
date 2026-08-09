"""Crew assembly and entry points for Feasibility, Statute, Channel, and the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from crewai import Crew, Process
from pydantic import ValidationError

from .agent import (
    FeasibilityVerdict,
    GoalBrief,
    build_feasibility_agent,
    build_feasibility_task,
    build_llm,
)
from .channel_agent import (
    ChannelBrief,
    ChannelVerdict,
    build_channel_agent,
    build_channel_task,
    holdings_from_allocation,
)
from .config import has_llm_credentials, llm_model
from .statute_agent import (
    StatuteVerdict,
    SwitchBrief,
    build_statute_agent,
    build_statute_task,
    disposals_from_moves,
)
from .trace import ToolCall, tool_trace

AgentName = Literal["Feasibility", "Statute", "Channel"]


class MissingCredentialsError(RuntimeError):
    pass


@dataclass
class AgentRun:
    """The result of one agent run: the verdict, and evidence of how it was reached."""

    verdict: FeasibilityVerdict | StatuteVerdict | ChannelVerdict | None
    raw: str
    model: str
    agent: AgentName = "Feasibility"
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def tools_used(self) -> list[str]:
        return [call.name for call in self.tool_calls]

    @property
    def tool_errors(self) -> list[ToolCall]:
        return [call for call in self.tool_calls if not call.ok]


# Back-compat alias used by stream tests and older imports.
FeasibilityRun = AgentRun


@dataclass
class PipelineRun:
    """Feasibility, then Statute, then Channel -- in that order."""

    feasibility: AgentRun
    statute: AgentRun | None = None
    channel: AgentRun | None = None
    model: str = ""

    @property
    def tool_calls(self) -> list[ToolCall]:
        calls: list[ToolCall] = list(self.feasibility.tool_calls)
        if self.statute:
            calls.extend(self.statute.tool_calls)
        if self.channel:
            calls.extend(self.channel.tool_calls)
        return calls

    @property
    def ok(self) -> bool:
        stages = [self.feasibility, self.statute, self.channel]
        return all(stage is not None and stage.verdict is not None for stage in stages)


def _describe_validation_error(error: ValidationError, model_name: str) -> str:
    problems = error.errors()
    lines = [
        f"The model's final answer did not fit {model_name} "
        f"({len(problems)} problem(s)):"
    ]
    for problem in problems:
        field_name = ".".join(str(part) for part in problem["loc"]) or "(root)"
        lines.append(f"  {field_name}: {problem['msg']}")
    if problems:
        lines += ["", f"It sent: {problems[0].get('input')!r}"]
    return "\n".join(lines)


def _usage_of(output: Any) -> dict[str, Any]:
    if getattr(output, "token_usage", None) is None:
        return {}
    if hasattr(output.token_usage, "model_dump"):
        return output.token_usage.model_dump()
    return dict(output.token_usage)


def _require_credentials() -> None:
    if not has_llm_credentials():
        raise MissingCredentialsError(
            "No LLM credentials found. Put OPENROUTER_API_KEY in crew/.env "
            "(see .env.example), or export it in your shell."
        )


def _kickoff(
    crew: Crew,
    *,
    agent: AgentName,
    model: str,
    verdict_type: type,
    trace: bool,
    sink: Any,
) -> AgentRun:
    with tool_trace(echo=trace, sink=sink) as recorded:
        try:
            output = crew.kickoff()
        except ValidationError as error:
            return AgentRun(
                agent=agent,
                verdict=None,
                raw=_describe_validation_error(error, verdict_type.__name__),
                model=model,
                tool_calls=recorded.calls,
            )

    verdict = output.pydantic if isinstance(output.pydantic, verdict_type) else None
    return AgentRun(
        agent=agent,
        verdict=verdict,
        raw=str(output.raw),
        model=model,
        tool_calls=recorded.calls,
        usage=_usage_of(output),
    )


def build_feasibility_crew(
    brief: GoalBrief, model: str | None = None, verbose: bool = False
) -> Crew:
    agent = build_feasibility_agent(llm=build_llm(model), verbose=verbose)
    return Crew(
        agents=[agent],
        tasks=[build_feasibility_task(brief, agent)],
        process=Process.sequential,
        verbose=verbose,
    )


def build_statute_crew(
    brief: SwitchBrief, model: str | None = None, verbose: bool = False
) -> Crew:
    agent = build_statute_agent(llm=build_llm(model), verbose=verbose)
    return Crew(
        agents=[agent],
        tasks=[build_statute_task(brief, agent)],
        process=Process.sequential,
        verbose=verbose,
    )


def build_channel_crew(
    brief: ChannelBrief, model: str | None = None, verbose: bool = False
) -> Crew:
    agent = build_channel_agent(llm=build_llm(model), verbose=verbose)
    return Crew(
        agents=[agent],
        tasks=[build_channel_task(brief, agent)],
        process=Process.sequential,
        verbose=verbose,
    )


def run_feasibility(
    brief: GoalBrief,
    model: str | None = None,
    verbose: bool = False,
    trace: bool = False,
    sink: Any = None,
) -> AgentRun:
    _require_credentials()
    resolved = model or llm_model()
    return _kickoff(
        build_feasibility_crew(brief, model=resolved, verbose=verbose),
        agent="Feasibility",
        model=resolved,
        verdict_type=FeasibilityVerdict,
        trace=trace,
        sink=sink,
    )


def run_statute(
    brief: SwitchBrief,
    model: str | None = None,
    verbose: bool = False,
    trace: bool = False,
    sink: Any = None,
) -> AgentRun:
    _require_credentials()
    resolved = model or llm_model()
    return _kickoff(
        build_statute_crew(brief, model=resolved, verbose=verbose),
        agent="Statute",
        model=resolved,
        verdict_type=StatuteVerdict,
        trace=trace,
        sink=sink,
    )


def run_channel(
    brief: ChannelBrief,
    model: str | None = None,
    verbose: bool = False,
    trace: bool = False,
    sink: Any = None,
) -> AgentRun:
    _require_credentials()
    resolved = model or llm_model()
    return _kickoff(
        build_channel_crew(brief, model=resolved, verbose=verbose),
        agent="Channel",
        model=resolved,
        verdict_type=ChannelVerdict,
        trace=trace,
        sink=sink,
    )


def default_switch_brief(
    goal: GoalBrief,
    feasibility: FeasibilityVerdict | None,
    other_taxable_income: float = 1_200_000.0,
    regime: str = "new",
    age_band: str = "below_60",
) -> SwitchBrief:
    """Build the Statute brief from the goal and Feasibility's recommended moves."""
    moves = list(feasibility.recommended_moves) if feasibility else []
    disposals = disposals_from_moves(moves, goal.current_corpus)
    purpose = (
        f"Reallocation to fund: {goal.goal}"
        if moves
        else f"No switch proposed for: {goal.goal}"
    )
    notes = None
    if feasibility and not moves:
        notes = (
            f"Feasibility verdict was '{feasibility.verdict}' with no recommended "
            "moves. Price an empty switch (tax should be zero)."
        )
    elif feasibility:
        notes = (
            f"Feasibility verdict: {feasibility.verdict}. "
            f"Headline: {feasibility.headline}"
        )
    return SwitchBrief(
        purpose=purpose,
        disposals=disposals,
        other_taxable_income=other_taxable_income,
        regime=regime,  # type: ignore[arg-type]
        age_band=age_band,  # type: ignore[arg-type]
        currency=goal.currency,
        notes=notes,
    )


def default_channel_brief(
    goal: GoalBrief,
    plan: Literal["regular", "direct"] = "regular",
    extra_holdings: list[dict[str, Any]] | None = None,
) -> ChannelBrief:
    """Channel brief from the goal allocation; demo defaults to Regular plans."""
    value = goal.current_corpus if goal.current_corpus > 0 else 1.0
    return ChannelBrief(
        portfolio_value=value,
        holdings=holdings_from_allocation(
            goal.allocation, plan=plan, extra=extra_holdings
        ),
        currency=goal.currency,
        notes=(
            f"Holdings inferred from the Feasibility allocation for '{goal.goal}'. "
            f"Plan type assumed: {plan}."
        ),
    )


def run_pipeline(
    goal: GoalBrief,
    *,
    other_taxable_income: float = 1_200_000.0,
    regime: str = "new",
    age_band: str = "below_60",
    channel_plan: Literal["regular", "direct"] = "regular",
    extra_holdings: list[dict[str, Any]] | None = None,
    model: str | None = None,
    verbose: bool = False,
    trace: bool = False,
    sink: Any = None,
) -> PipelineRun:
    """Run Feasibility, then Statute, then Channel, feeding each into the next."""
    _require_credentials()
    resolved = model or llm_model()

    feasibility = run_feasibility(
        goal, model=resolved, verbose=verbose, trace=trace, sink=sink
    )

    switch = default_switch_brief(
        goal,
        feasibility.verdict if isinstance(feasibility.verdict, FeasibilityVerdict) else None,
        other_taxable_income=other_taxable_income,
        regime=regime,
        age_band=age_band,
    )
    statute = run_statute(
        switch, model=resolved, verbose=verbose, trace=trace, sink=sink
    )

    channel_brief = default_channel_brief(
        goal, plan=channel_plan, extra_holdings=extra_holdings
    )
    channel = run_channel(
        channel_brief, model=resolved, verbose=verbose, trace=trace, sink=sink
    )

    return PipelineRun(
        feasibility=feasibility,
        statute=statute,
        channel=channel,
        model=resolved,
    )
