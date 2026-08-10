"""Crew assembly and entry points for the full Meridian desk pipeline."""

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
from .reframe_agent import (
    ReframeBrief,
    ReframeVerdict,
    build_reframe_agent,
    build_reframe_task,
)
from .shared_agent import (
    SharedBrief,
    SharedVerdict,
    build_shared_agent,
    build_shared_task,
)
from .statute_agent import (
    StatuteVerdict,
    SwitchBrief,
    build_statute_agent,
    build_statute_task,
    disposals_from_moves,
)
from .trace import ToolCall, tool_trace

AgentName = Literal["Planner", "Tax", "Fees", "Rethink", "Verdict"]


class MissingCredentialsError(RuntimeError):
    pass


@dataclass
class AgentRun:
    """The result of one agent run: the verdict, and evidence of how it was reached."""

    verdict: (
        FeasibilityVerdict
        | StatuteVerdict
        | ChannelVerdict
        | ReframeVerdict
        | SharedVerdict
        | None
    )
    raw: str
    model: str
    agent: AgentName = "Planner"
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
    """Planner → Tax → Fees → Rethink → Verdict."""

    feasibility: AgentRun
    statute: AgentRun | None = None
    channel: AgentRun | None = None
    reframe: AgentRun | None = None
    shared: AgentRun | None = None
    model: str = ""

    @property
    def tool_calls(self) -> list[ToolCall]:
        calls: list[ToolCall] = list(self.feasibility.tool_calls)
        for stage in (self.statute, self.channel, self.reframe, self.shared):
            if stage:
                calls.extend(stage.tool_calls)
        return calls

    @property
    def ok(self) -> bool:
        stages = [
            self.feasibility,
            self.statute,
            self.channel,
            self.reframe,
            self.shared,
        ]
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


def build_reframe_crew(
    brief: ReframeBrief, model: str | None = None, verbose: bool = False
) -> Crew:
    agent = build_reframe_agent(llm=build_llm(model), verbose=verbose)
    return Crew(
        agents=[agent],
        tasks=[build_reframe_task(brief, agent)],
        process=Process.sequential,
        verbose=verbose,
    )


def build_shared_crew(
    brief: SharedBrief, model: str | None = None, verbose: bool = False
) -> Crew:
    agent = build_shared_agent(llm=build_llm(model), verbose=verbose)
    return Crew(
        agents=[agent],
        tasks=[build_shared_task(brief, agent)],
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
        agent="Planner",
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
        agent="Tax",
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
        agent="Fees",
        model=resolved,
        verdict_type=ChannelVerdict,
        trace=trace,
        sink=sink,
    )


def run_reframe(
    brief: ReframeBrief,
    model: str | None = None,
    verbose: bool = False,
    trace: bool = False,
    sink: Any = None,
) -> AgentRun:
    _require_credentials()
    resolved = model or llm_model()
    return _kickoff(
        build_reframe_crew(brief, model=resolved, verbose=verbose),
        agent="Rethink",
        model=resolved,
        verdict_type=ReframeVerdict,
        trace=trace,
        sink=sink,
    )


def run_shared(
    brief: SharedBrief,
    model: str | None = None,
    verbose: bool = False,
    trace: bool = False,
    sink: Any = None,
) -> AgentRun:
    _require_credentials()
    resolved = model or llm_model()
    return _kickoff(
        build_shared_crew(brief, model=resolved, verbose=verbose),
        agent="Verdict",
        model=resolved,
        verdict_type=SharedVerdict,
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
    """Build the Tax brief from the goal and Planner's recommended moves."""
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
            f"Planner verdict was '{feasibility.verdict}' with no recommended "
            "moves. Price an empty switch (tax should be zero)."
        )
    elif feasibility:
        notes = (
            f"Planner verdict: {feasibility.verdict}. "
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
    """Fees brief from the goal allocation; demo defaults to Regular plans."""
    value = goal.current_corpus if goal.current_corpus > 0 else 1.0
    return ChannelBrief(
        portfolio_value=value,
        holdings=holdings_from_allocation(
            goal.allocation, plan=plan, extra=extra_holdings
        ),
        currency=goal.currency,
        notes=(
            f"Holdings inferred from the Planner allocation for '{goal.goal}'. "
            f"Plan type assumed: {plan}."
        ),
    )


def default_reframe_brief(
    goal: GoalBrief,
    feasibility: FeasibilityVerdict | None,
    statute: StatuteVerdict | None,
    channel: ChannelVerdict | None,
    *,
    other_taxable_income: float = 1_200_000.0,
    regime: str = "new",
    age_band: str = "below_60",
    channel_plan: Literal["regular", "direct"] = "regular",
) -> ReframeBrief:
    """Rethink brief from the goal plus Planner / Tax / Fees outputs."""
    moves = list(feasibility.recommended_moves) if feasibility else []
    disposals = disposals_from_moves(moves, goal.current_corpus)
    value = goal.current_corpus if goal.current_corpus > 0 else 1.0
    notes_parts = []
    if feasibility:
        notes_parts.append(
            f"Planner: {feasibility.verdict} — {feasibility.headline}"
        )
    if statute:
        notes_parts.append(f"Tax tax INR {statute.total_tax:,.0f}.")
    if channel:
        notes_parts.append(
            f"Fees annual drag INR {channel.annual_drag_rupees:,.0f}."
        )
    return ReframeBrief(
        goal=goal.goal,
        target_amount=goal.target_amount,
        years_to_goal=goal.years_to_goal,
        current_corpus=goal.current_corpus,
        monthly_contribution=goal.monthly_contribution,
        allocation=goal.allocation,
        portfolio_value=value,
        holdings=holdings_from_allocation(goal.allocation, plan=channel_plan),
        disposals=disposals,
        other_taxable_income=other_taxable_income,
        regime=regime,  # type: ignore[arg-type]
        age_band=age_band,  # type: ignore[arg-type]
        shortfall=feasibility.shortfall if feasibility else None,
        feasibility_verdict=feasibility.verdict if feasibility else None,
        statute_tax=statute.total_tax if statute else None,
        channel_annual_drag=channel.annual_drag_rupees if channel else None,
        currency=goal.currency,
        annual_step_up_pct=goal.annual_step_up_pct,
        notes=" ".join(notes_parts) or None,
    )


def default_shared_brief(
    goal: GoalBrief,
    feasibility: FeasibilityVerdict | None,
    statute: StatuteVerdict | None,
    channel: ChannelVerdict | None,
    reframe: ReframeVerdict | None,
) -> SharedBrief:
    """Verdict brief assembled from every prior stage."""
    priced = []
    if reframe:
        for lever in reframe.levers:
            priced.append(
                {
                    "kind": lever.kind,
                    "summary": lever.summary,
                    "target_amount": lever.target_amount,
                    "years_to_goal": lever.years_to_goal,
                    "monthly_contribution": lever.monthly_contribution,
                    "all_in_friction": lever.all_in_friction,
                    "statute_tax": lever.statute_tax,
                    "channel_horizon_drag": lever.channel_horizon_drag,
                }
            )
    return SharedBrief(
        goal=goal.goal,
        investable_corpus=goal.current_corpus if goal.current_corpus > 0 else 1.0,
        currency=goal.currency,
        feasibility_headline=feasibility.headline if feasibility else None,
        feasibility_verdict=feasibility.verdict if feasibility else None,
        shortfall=feasibility.shortfall if feasibility else None,
        statute_headline=statute.headline if statute else None,
        statute_tax=statute.total_tax if statute else None,
        channel_headline=channel.headline if channel else None,
        channel_annual_drag=channel.annual_drag_rupees if channel else None,
        reframe_headline=reframe.headline if reframe else None,
        preferred_lever=reframe.preferred_lever if reframe else None,
        slip_delay_months=reframe.slip_delay_months if reframe else None,
        shrink_rupees=reframe.shrink_rupees if reframe else None,
        topup_additional_monthly=(
            reframe.topup_additional_monthly if reframe else None
        ),
        priced_options=priced,
        notes=goal.notes,
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
    """Run Planner → Tax → Fees → Rethink → Verdict."""
    _require_credentials()
    resolved = model or llm_model()

    feasibility = run_feasibility(
        goal, model=resolved, verbose=verbose, trace=trace, sink=sink
    )
    feasibility_verdict = (
        feasibility.verdict
        if isinstance(feasibility.verdict, FeasibilityVerdict)
        else None
    )

    switch = default_switch_brief(
        goal,
        feasibility_verdict,
        other_taxable_income=other_taxable_income,
        regime=regime,
        age_band=age_band,
    )
    statute = run_statute(
        switch, model=resolved, verbose=verbose, trace=trace, sink=sink
    )
    statute_verdict = (
        statute.verdict if isinstance(statute.verdict, StatuteVerdict) else None
    )

    channel_brief = default_channel_brief(
        goal, plan=channel_plan, extra_holdings=extra_holdings
    )
    channel = run_channel(
        channel_brief, model=resolved, verbose=verbose, trace=trace, sink=sink
    )
    channel_verdict = (
        channel.verdict if isinstance(channel.verdict, ChannelVerdict) else None
    )

    reframe_brief = default_reframe_brief(
        goal,
        feasibility_verdict,
        statute_verdict,
        channel_verdict,
        other_taxable_income=other_taxable_income,
        regime=regime,
        age_band=age_band,
        channel_plan=channel_plan,
    )
    reframe = run_reframe(
        reframe_brief, model=resolved, verbose=verbose, trace=trace, sink=sink
    )
    reframe_verdict = (
        reframe.verdict if isinstance(reframe.verdict, ReframeVerdict) else None
    )

    shared_brief = default_shared_brief(
        goal,
        feasibility_verdict,
        statute_verdict,
        channel_verdict,
        reframe_verdict,
    )
    shared = run_shared(
        shared_brief, model=resolved, verbose=verbose, trace=trace, sink=sink
    )

    return PipelineRun(
        feasibility=feasibility,
        statute=statute,
        channel=channel,
        reframe=reframe,
        shared=shared,
        model=resolved,
    )
