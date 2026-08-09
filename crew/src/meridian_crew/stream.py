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
from .config import llm_model
from .crew import FeasibilityRun, MissingCredentialsError, run_feasibility

AGENT_NAME = "Feasibility"


def emit(event: dict[str, Any]) -> None:
    """Write one event. Flushed, because a buffered stream is not a stream."""
    sys.stdout.write(json.dumps(event, default=str) + "\n")
    sys.stdout.flush()


def _money(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.0f}"


def _verdict_events(verdict: FeasibilityVerdict, brief: GoalBrief) -> list[dict[str, Any]]:
    """The console shows prose, so the structured verdict is narrated."""
    events: list[dict[str, Any]] = [
        {
            "type": "log",
            "source": AGENT_NAME,
            "message": "Verdict:",
            "highlight": verdict.verdict.replace("_", " "),
        },
        {
            "type": "log",
            "source": AGENT_NAME,
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
                "source": AGENT_NAME,
                "message": (
                    f"Needs {verdict.required_annual_return * 100:.2f}% a year against "
                    f"{verdict.expected_annual_return * 100:.2f}% expected."
                ),
            }
        )

    for move in verdict.recommended_moves:
        events.append(
            {"type": "log", "source": AGENT_NAME, "message": "Shift:", "highlight": move}
        )

    events.append({"type": "message", "source": AGENT_NAME, "text": verdict.headline})
    return events


def _summary(run: FeasibilityRun) -> str:
    tools = len(run.tool_calls)
    if run.verdict is None:
        return f"Run ended without a usable verdict after {tools} tool call(s)"
    return (
        f"Run complete - {tools} tool call(s), verdict: "
        f"{run.verdict.verdict.replace('_', ' ')}"
    )


def stream_feasibility(brief: GoalBrief, model: str | None = None) -> int:
    """Run the agent, emitting NDJSON throughout. Returns a process exit code."""
    emit({"type": "status", "state": "thinking", "label": "Assessing goal feasibility"})
    emit(
        {
            "type": "log",
            "source": "System",
            "message": f"Brief: {brief.goal} | {_money(brief.target_amount, brief.currency)} "
            f"in {brief.years_to_goal:g} years",
        }
    )
    emit(
        {
            "type": "log",
            "source": "System",
            "message": f"Model: {model or llm_model()}",
        }
    )

    try:
        run = run_feasibility(brief, model=model, sink=emit)
    except MissingCredentialsError as error:
        emit({"type": "error", "message": str(error)})
        emit({"type": "status", "state": "halted", "label": "Missing credentials"})
        return 3
    except Exception as error:  # noqa: BLE001 - the stream must always close cleanly
        emit({"type": "error", "message": f"{type(error).__name__}: {error}"})
        emit({"type": "status", "state": "halted", "label": "Run failed"})
        return 1

    if run.verdict is not None:
        for event in _verdict_events(run.verdict, brief):
            emit(event)
    else:
        emit({"type": "error", "message": run.raw})

    emit({"type": "status", "state": "idle", "label": "Awaiting direction"})
    emit({"type": "done", "summary": _summary(run)})
    return 0 if run.verdict else 1
