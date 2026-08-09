"""Newline-delimited JSON output, for a consumer that wants a live feed.

The Express API spawns `python -m meridian_crew --stream` and forwards each line
to the browser over SSE. The event names here deliberately match the `AgentEvent`
union the client already renders, but this module emits no ids or timestamps: the
Node side owns those, because it is the process that knows when the browser saw
each line.

One line per event, flushed immediately. A partial line is never written, so the
reader can split on newlines without buffering rules of its own.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from .agent import FeasibilityVerdict, GoalBrief
from .channel_agent import ChannelBrief, ChannelVerdict
from .config import llm_model
from .crew import (
    AgentRun,
    MissingCredentialsError,
    PipelineRun,
    default_channel_brief,
    default_reframe_brief,
    default_shared_brief,
    default_switch_brief,
    run_channel,
    run_feasibility,
    run_reframe,
    run_shared,
    run_statute,
)
from .reframe_agent import ReframeBrief, ReframeVerdict
from .shared_agent import SharedBrief, SharedVerdict
from .statute_agent import StatuteVerdict, SwitchBrief


def emit(event: dict[str, Any]) -> None:
    """Write one event. Flushed, because a buffered stream is not a stream."""
    sys.stdout.write(json.dumps(event, default=str) + "\n")
    sys.stdout.flush()


def _money(amount: float, currency: str = "INR") -> str:
    return f"{currency} {amount:,.0f}"


def _feasibility_events(
    verdict: FeasibilityVerdict, brief: GoalBrief
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        {
            "type": "log",
            "source": "Feasibility",
            "message": "Verdict:",
            "highlight": verdict.verdict.replace("_", " "),
        },
        {
            "type": "log",
            "source": "Feasibility",
            "message": (
                f"Projects {_money(verdict.projected_corpus, brief.currency)} "
                f"against a target of {_money(verdict.target_amount, brief.currency)}"
                + (
                    f" -- short by {_money(verdict.shortfall, brief.currency)}."
                    if verdict.shortfall > 0
                    else " -- fully funded."
                )
            ),
        },
    ]

    if verdict.required_annual_return is not None:
        events.append(
            {
                "type": "log",
                "source": "Feasibility",
                "message": (
                    f"Needs {verdict.required_annual_return * 100:.2f}% a year against "
                    f"{verdict.expected_annual_return * 100:.2f}% expected."
                ),
            }
        )

    for move in verdict.recommended_moves:
        events.append(
            {
                "type": "log",
                "source": "Feasibility",
                "message": "Shift:",
                "highlight": move,
            }
        )

    events.append(
        {
            "type": "message",
            "source": "Feasibility",
            "text": verdict.headline,
            "report": {
                "agent": "Feasibility",
                "title": "Goal feasibility",
                "headline": verdict.headline,
                "verdict": verdict.verdict,
                "metrics": [
                    {
                        "label": "Projected corpus",
                        "value": _money(verdict.projected_corpus, brief.currency),
                    },
                    {
                        "label": "Target",
                        "value": _money(verdict.target_amount, brief.currency),
                    },
                    {
                        "label": "Shortfall",
                        "value": _money(verdict.shortfall, brief.currency),
                    },
                    {
                        "label": "Expected return",
                        "value": f"{verdict.expected_annual_return * 100:.2f}%",
                    },
                ],
                "bullets": verdict.recommended_moves
                + ([f"Risk: {r}" for r in verdict.risks[:2]] if verdict.risks else []),
            },
        }
    )
    return events


def _statute_events(verdict: StatuteVerdict, currency: str = "INR") -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        {
            "type": "log",
            "source": "Statute",
            "message": "Tax payable:",
            "highlight": _money(verdict.total_tax, currency),
        },
    ]
    if verdict.sections_applied:
        events.append(
            {
                "type": "log",
                "source": "Statute",
                "message": "Sections:",
                "highlight": ", ".join(verdict.sections_applied),
            }
        )
    if verdict.staging_saves:
        events.append(
            {
                "type": "log",
                "source": "Statute",
                "message": "FY staging saves:",
                "highlight": _money(verdict.staging_saves, currency),
            }
        )

    metrics = [
        {"label": "Total tax", "value": _money(verdict.total_tax, currency)},
    ]
    if verdict.equity_ltcg_112a is not None:
        metrics.append(
            {"label": "112A", "value": _money(verdict.equity_ltcg_112a, currency)}
        )
    if verdict.equity_stcg_111a is not None:
        metrics.append(
            {"label": "111A", "value": _money(verdict.equity_stcg_111a, currency)}
        )
    if verdict.debt_slab_tax is not None:
        metrics.append(
            {"label": "Debt / slab", "value": _money(verdict.debt_slab_tax, currency)}
        )
    if verdict.staging_saves is not None:
        metrics.append(
            {"label": "Staging saves", "value": _money(verdict.staging_saves, currency)}
        )

    events.append(
        {
            "type": "message",
            "source": "Statute",
            "text": verdict.headline,
            "report": {
                "agent": "Statute",
                "title": "Switch tax cost",
                "headline": verdict.headline,
                "verdict": "stage" if verdict.recommend_staging else "price",
                "metrics": metrics,
                "bullets": verdict.assumptions[:3]
                + ([f"Risk: {r}" for r in verdict.risks[:2]] if verdict.risks else []),
            },
        }
    )
    return events


def _channel_events(verdict: ChannelVerdict, currency: str = "INR") -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        {
            "type": "log",
            "source": "Channel",
            "message": "Annual Regular drag:",
            "highlight": _money(verdict.annual_drag_rupees, currency),
        },
        {
            "type": "log",
            "source": "Channel",
            "message": (
                f"{verdict.annual_drag_pct_of_portfolio * 100:.3f}% of the portfolio a year"
            ),
        },
    ]
    for item in verdict.out_of_scope:
        events.append(
            {
                "type": "log",
                "source": "Channel",
                "message": "Cannot price:",
                "highlight": item,
            }
        )

    metrics = [
        {
            "label": "Annual drag",
            "value": _money(verdict.annual_drag_rupees, currency),
        },
        {
            "label": "Drag / portfolio",
            "value": f"{verdict.annual_drag_pct_of_portfolio * 100:.3f}%",
        },
    ]
    if verdict.five_year_drag_rupees is not None:
        metrics.append(
            {
                "label": "Five-year floor",
                "value": _money(verdict.five_year_drag_rupees, currency),
            }
        )

    events.append(
        {
            "type": "message",
            "source": "Channel",
            "text": verdict.headline,
            "report": {
                "agent": "Channel",
                "title": "Regular vs Direct drag",
                "headline": verdict.headline,
                "verdict": "drag",
                "metrics": metrics,
                "bullets": verdict.recommendations[:3]
                + [f"Out of scope: {item}" for item in verdict.out_of_scope[:3]],
            },
        }
    )
    return events


def _reframe_events(verdict: ReframeVerdict, currency: str = "INR") -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        {
            "type": "log",
            "source": "Reframe",
            "message": "Preferred lever:",
            "highlight": verdict.preferred_lever,
        },
    ]
    if verdict.slip_delay_months is not None:
        events.append(
            {
                "type": "log",
                "source": "Reframe",
                "message": "Slip delay:",
                "highlight": f"{verdict.slip_delay_months} months",
            }
        )
    if verdict.shrink_reachable_target is not None:
        events.append(
            {
                "type": "log",
                "source": "Reframe",
                "message": "Reachable target:",
                "highlight": _money(verdict.shrink_reachable_target, currency),
            }
        )
    if verdict.topup_additional_monthly is not None:
        events.append(
            {
                "type": "log",
                "source": "Reframe",
                "message": "Monthly top-up:",
                "highlight": _money(verdict.topup_additional_monthly, currency) + "/mo",
            }
        )

    metrics = []
    if verdict.slip_delay_months is not None:
        metrics.append(
            {"label": "Slip delay", "value": f"{verdict.slip_delay_months} mo"}
        )
    if verdict.shrink_reachable_target is not None:
        metrics.append(
            {
                "label": "Reachable target",
                "value": _money(verdict.shrink_reachable_target, currency),
            }
        )
    if verdict.topup_additional_monthly is not None:
        metrics.append(
            {
                "label": "Top-up / mo",
                "value": _money(verdict.topup_additional_monthly, currency),
            }
        )
    if verdict.cheapest_friction_kind:
        metrics.append(
            {"label": "Lowest friction", "value": verdict.cheapest_friction_kind}
        )

    bullets = [lever.summary for lever in verdict.levers[:3]]
    events.append(
        {
            "type": "message",
            "source": "Reframe",
            "text": verdict.headline,
            "report": {
                "agent": "Reframe",
                "title": "Reframed levers",
                "headline": verdict.headline,
                "verdict": verdict.preferred_lever,
                "metrics": metrics,
                "bullets": bullets,
            },
        }
    )
    return events


def _shared_events(verdict: SharedVerdict, currency: str = "INR") -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = [
        {
            "type": "log",
            "source": "Shared",
            "message": "Best path:",
            "highlight": verdict.best_path,
        },
        {
            "type": "log",
            "source": "Shared",
            "message": "Eligibility:",
            "highlight": verdict.highest_eligible_lane,
        },
    ]
    for stance in verdict.stances[:4]:
        events.append(
            {
                "type": "log",
                "source": "Shared",
                "message": f"[{stance.posture}] {stance.path}:",
                "highlight": stance.line,
            }
        )

    events.append(
        {
            "type": "message",
            "source": "Shared",
            "text": verdict.headline,
            "report": {
                "agent": "Shared",
                "title": "Desk close",
                "headline": verdict.headline,
                "verdict": verdict.best_path,
                "metrics": [
                    {"label": "Best path", "value": verdict.best_path},
                    {
                        "label": "Eligible lane",
                        "value": verdict.highest_eligible_lane,
                    },
                ],
                "bullets": [verdict.ranked_recommendation, verdict.adviser_blurb]
                + [f"{s.posture}: {s.path}" for s in verdict.stances[:4]],
            },
        }
    )
    return events


# Kept for the stream unit tests that import the old name.
def _verdict_events(
    verdict: FeasibilityVerdict, brief: GoalBrief
) -> list[dict[str, Any]]:
    return _feasibility_events(verdict, brief)


def _summary(run: AgentRun | PipelineRun) -> str:
    if isinstance(run, PipelineRun):
        parts = []
        for stage in (
            run.feasibility,
            run.statute,
            run.channel,
            run.reframe,
            run.shared,
        ):
            if stage is None:
                continue
            label = stage.agent
            if stage.verdict is None:
                parts.append(f"{label}: failed")
            else:
                parts.append(f"{label}: ok ({len(stage.tool_calls)} tools)")
        return "Pipeline complete - " + "; ".join(parts)

    tools = len(run.tool_calls)
    if run.verdict is None:
        return f"{run.agent} ended without a usable verdict after {tools} tool call(s)"
    return f"{run.agent} complete - {tools} tool call(s)"


def _emit_run_verdict(run: AgentRun, *, goal: GoalBrief | None = None) -> None:
    if run.verdict is None:
        emit({"type": "error", "message": f"{run.agent}: {run.raw}"})
        return
    currency = goal.currency if goal else "INR"
    if isinstance(run.verdict, FeasibilityVerdict) and goal is not None:
        for event in _feasibility_events(run.verdict, goal):
            emit(event)
    elif isinstance(run.verdict, StatuteVerdict):
        for event in _statute_events(run.verdict, currency):
            emit(event)
    elif isinstance(run.verdict, ChannelVerdict):
        for event in _channel_events(run.verdict, currency):
            emit(event)
    elif isinstance(run.verdict, ReframeVerdict):
        for event in _reframe_events(run.verdict, currency):
            emit(event)
    elif isinstance(run.verdict, SharedVerdict):
        for event in _shared_events(run.verdict, currency):
            emit(event)


def stream_feasibility(brief: GoalBrief, model: str | None = None) -> int:
    """Run Feasibility alone. Prefer `stream_pipeline` for the full desk."""
    emit({"type": "status", "state": "thinking", "label": "Assessing goal feasibility"})
    emit(
        {
            "type": "log",
            "source": "System",
            "message": f"Brief: {brief.goal} | {_money(brief.target_amount, brief.currency)} "
            f"in {brief.years_to_goal:g} years",
        }
    )
    emit({"type": "log", "source": "System", "message": f"Model: {model or llm_model()}"})

    try:
        run = run_feasibility(brief, model=model, sink=emit)
    except MissingCredentialsError as error:
        emit({"type": "error", "message": str(error)})
        emit({"type": "status", "state": "halted", "label": "Missing credentials"})
        return 3
    except Exception as error:  # noqa: BLE001
        emit({"type": "error", "message": f"{type(error).__name__}: {error}"})
        emit({"type": "status", "state": "halted", "label": "Run failed"})
        return 1

    _emit_run_verdict(run, goal=brief)
    emit({"type": "status", "state": "idle", "label": "Awaiting direction"})
    emit({"type": "done", "summary": _summary(run)})
    return 0 if run.verdict else 1


def stream_pipeline(brief: GoalBrief, model: str | None = None, **pipeline_kwargs: Any) -> int:
    """Run Feasibility → Statute → Channel → Reframe → Shared."""
    emit(
        {
            "type": "status",
            "state": "thinking",
            "label": "Running Feasibility → Statute → Channel → Reframe → Shared",
        }
    )
    emit(
        {
            "type": "log",
            "source": "System",
            "message": f"Brief: {brief.goal} | {_money(brief.target_amount, brief.currency)} "
            f"in {brief.years_to_goal:g} years",
        }
    )
    emit({"type": "log", "source": "System", "message": f"Model: {model or llm_model()}"})

    def sink(event: dict[str, Any]) -> None:
        emit(event)

    try:
        stages = [
            ("1/5", "Feasibility", "Feasibility assessing goal"),
            ("2/5", "Statute", "Statute pricing the switch"),
            ("3/5", "Channel", "Channel measuring TER drag"),
            ("4/5", "Reframe", "Reframe solving the three levers"),
            ("5/5", "Shared", "Shared closing the desk"),
        ]

        emit({"type": "status", "state": "thinking", "label": stages[0][2]})
        emit(
            {
                "type": "log",
                "source": "System",
                "message": f"Stage {stages[0][0]}:",
                "highlight": stages[0][1],
            }
        )
        feasibility = run_feasibility(brief, model=model, sink=sink)
        _emit_run_verdict(feasibility, goal=brief)
        feasibility_verdict = (
            feasibility.verdict
            if isinstance(feasibility.verdict, FeasibilityVerdict)
            else None
        )

        emit({"type": "status", "state": "thinking", "label": stages[1][2]})
        emit(
            {
                "type": "log",
                "source": "System",
                "message": f"Stage {stages[1][0]}:",
                "highlight": stages[1][1],
            }
        )
        switch = default_switch_brief(
            brief,
            feasibility_verdict,
            other_taxable_income=float(
                pipeline_kwargs.get("other_taxable_income", 1_200_000)
            ),
            regime=str(pipeline_kwargs.get("regime", "new")),
            age_band=str(pipeline_kwargs.get("age_band", "below_60")),
        )
        statute = run_statute(switch, model=model, sink=sink)
        _emit_run_verdict(statute, goal=brief)
        statute_verdict = (
            statute.verdict if isinstance(statute.verdict, StatuteVerdict) else None
        )

        emit({"type": "status", "state": "thinking", "label": stages[2][2]})
        emit(
            {
                "type": "log",
                "source": "System",
                "message": f"Stage {stages[2][0]}:",
                "highlight": stages[2][1],
            }
        )
        channel_brief = default_channel_brief(
            brief, plan=pipeline_kwargs.get("channel_plan", "regular")
        )
        channel = run_channel(channel_brief, model=model, sink=sink)
        _emit_run_verdict(channel, goal=brief)
        channel_verdict = (
            channel.verdict if isinstance(channel.verdict, ChannelVerdict) else None
        )

        emit({"type": "status", "state": "thinking", "label": stages[3][2]})
        emit(
            {
                "type": "log",
                "source": "System",
                "message": f"Stage {stages[3][0]}:",
                "highlight": stages[3][1],
            }
        )
        reframe_brief = default_reframe_brief(
            brief,
            feasibility_verdict,
            statute_verdict,
            channel_verdict,
            other_taxable_income=float(
                pipeline_kwargs.get("other_taxable_income", 1_200_000)
            ),
            regime=str(pipeline_kwargs.get("regime", "new")),
            age_band=str(pipeline_kwargs.get("age_band", "below_60")),
            channel_plan=pipeline_kwargs.get("channel_plan", "regular"),
        )
        reframe = run_reframe(reframe_brief, model=model, sink=sink)
        _emit_run_verdict(reframe, goal=brief)
        reframe_verdict = (
            reframe.verdict if isinstance(reframe.verdict, ReframeVerdict) else None
        )

        emit({"type": "status", "state": "thinking", "label": stages[4][2]})
        emit(
            {
                "type": "log",
                "source": "System",
                "message": f"Stage {stages[4][0]}:",
                "highlight": stages[4][1],
            }
        )
        shared_brief = default_shared_brief(
            brief,
            feasibility_verdict,
            statute_verdict,
            channel_verdict,
            reframe_verdict,
        )
        shared = run_shared(shared_brief, model=model, sink=sink)
        _emit_run_verdict(shared, goal=brief)

        pipeline = PipelineRun(
            feasibility=feasibility,
            statute=statute,
            channel=channel,
            reframe=reframe,
            shared=shared,
            model=model or llm_model(),
        )
    except MissingCredentialsError as error:
        emit({"type": "error", "message": str(error)})
        emit({"type": "status", "state": "halted", "label": "Missing credentials"})
        return 3
    except Exception as error:  # noqa: BLE001
        emit({"type": "error", "message": f"{type(error).__name__}: {error}"})
        emit({"type": "status", "state": "halted", "label": "Run failed"})
        return 1

    emit({"type": "status", "state": "idle", "label": "Awaiting direction"})
    emit({"type": "done", "summary": _summary(pipeline)})
    return 0 if pipeline.ok else 1


def stream_statute(brief: SwitchBrief, model: str | None = None) -> int:
    emit({"type": "status", "state": "thinking", "label": "Pricing switch tax"})
    emit({"type": "log", "source": "System", "message": f"Model: {model or llm_model()}"})
    try:
        run = run_statute(brief, model=model, sink=emit)
    except MissingCredentialsError as error:
        emit({"type": "error", "message": str(error)})
        emit({"type": "status", "state": "halted", "label": "Missing credentials"})
        return 3
    except Exception as error:  # noqa: BLE001
        emit({"type": "error", "message": f"{type(error).__name__}: {error}"})
        emit({"type": "status", "state": "halted", "label": "Run failed"})
        return 1
    _emit_run_verdict(run)
    emit({"type": "status", "state": "idle", "label": "Awaiting direction"})
    emit({"type": "done", "summary": _summary(run)})
    return 0 if run.verdict else 1


def stream_channel(brief: ChannelBrief, model: str | None = None) -> int:
    emit({"type": "status", "state": "thinking", "label": "Measuring channel drag"})
    emit({"type": "log", "source": "System", "message": f"Model: {model or llm_model()}"})
    try:
        run = run_channel(brief, model=model, sink=emit)
    except MissingCredentialsError as error:
        emit({"type": "error", "message": str(error)})
        emit({"type": "status", "state": "halted", "label": "Missing credentials"})
        return 3
    except Exception as error:  # noqa: BLE001
        emit({"type": "error", "message": f"{type(error).__name__}: {error}"})
        emit({"type": "status", "state": "halted", "label": "Run failed"})
        return 1
    _emit_run_verdict(run)
    emit({"type": "status", "state": "idle", "label": "Awaiting direction"})
    emit({"type": "done", "summary": _summary(run)})
    return 0 if run.verdict else 1


def stream_reframe(brief: ReframeBrief, model: str | None = None) -> int:
    emit({"type": "status", "state": "thinking", "label": "Solving reframe levers"})
    emit({"type": "log", "source": "System", "message": f"Model: {model or llm_model()}"})
    try:
        run = run_reframe(brief, model=model, sink=emit)
    except MissingCredentialsError as error:
        emit({"type": "error", "message": str(error)})
        emit({"type": "status", "state": "halted", "label": "Missing credentials"})
        return 3
    except Exception as error:  # noqa: BLE001
        emit({"type": "error", "message": f"{type(error).__name__}: {error}"})
        emit({"type": "status", "state": "halted", "label": "Run failed"})
        return 1
    _emit_run_verdict(run)
    emit({"type": "status", "state": "idle", "label": "Awaiting direction"})
    emit({"type": "done", "summary": _summary(run)})
    return 0 if run.verdict else 1


def stream_shared(brief: SharedBrief, model: str | None = None) -> int:
    emit({"type": "status", "state": "thinking", "label": "Closing the shared desk"})
    emit({"type": "log", "source": "System", "message": f"Model: {model or llm_model()}"})
    try:
        run = run_shared(brief, model=model, sink=emit)
    except MissingCredentialsError as error:
        emit({"type": "error", "message": str(error)})
        emit({"type": "status", "state": "halted", "label": "Missing credentials"})
        return 3
    except Exception as error:  # noqa: BLE001
        emit({"type": "error", "message": f"{type(error).__name__}: {error}"})
        emit({"type": "status", "state": "halted", "label": "Run failed"})
        return 1
    _emit_run_verdict(run)
    emit({"type": "status", "state": "idle", "label": "Awaiting direction"})
    emit({"type": "done", "summary": _summary(run)})
    return 0 if run.verdict else 1
