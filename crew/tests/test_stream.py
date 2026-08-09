"""The NDJSON contract the Express bridge reads.

`server/src/agents/crewProvider.ts` parses this output line by line, so the shape
is an interface between two languages with no shared type checker. These tests are
what stands in for one.
"""

from __future__ import annotations

import json

import pytest

from meridian_crew.agent import FeasibilityVerdict, GoalBrief
from meridian_crew.stream import _verdict_events, _summary, emit
from meridian_crew.crew import FeasibilityRun
from meridian_crew.trace import ToolCall

# Event types the TypeScript side knows how to map. Adding one here without
# teaching `toAgentEvent` about it means the console silently drops it.
KNOWN_TYPES = {"status", "log", "tool_call", "tool_result", "message", "done", "error"}


@pytest.fixture
def brief() -> GoalBrief:
    return GoalBrief(
        goal="Tuition",
        target_amount=5_000_000,
        years_to_goal=7,
        current_corpus=900_000,
        monthly_contribution=25_000,
        client_age=42,
        allocation="equity_large_cap=50,debt_liquid=50",
    )


@pytest.fixture
def verdict() -> FeasibilityVerdict:
    return FeasibilityVerdict(
        verdict="reachable_with_changes",
        headline="Short by INR 601,298; a 29 point shift closes it.",
        projected_corpus=4_398_701.75,
        target_amount=5_000_000.0,
        shortfall=601_298.25,
        expected_annual_return=0.084159,
        required_annual_return=0.112263,
        recommended_shift_pct=29.0,
        recommended_moves=["debt_liquid -> equity_mid_cap: 10.0%"],
        reasoning="Tools said so.",
    )


def test_emit_writes_one_parseable_line_per_event(capsys) -> None:
    emit({"type": "status", "state": "thinking", "label": "a"})
    emit({"type": "done", "summary": "b"})

    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    assert [json.loads(line)["type"] for line in lines] == ["status", "done"]


def test_emit_never_splits_an_event_across_lines(capsys) -> None:
    """A newline inside a value would desynchronise a line-based reader."""
    emit({"type": "log", "message": "first\nsecond", "source": "System"})

    out = capsys.readouterr().out
    assert out.count("\n") == 1
    assert json.loads(out)["message"] == "first\nsecond"


def test_verdict_narration_uses_only_known_event_types(verdict, brief) -> None:
    events = _verdict_events(verdict, brief)

    assert events, "a verdict must produce at least one event"
    for event in events:
        assert event["type"] in KNOWN_TYPES


def test_verdict_narration_reports_the_numbers_and_every_move(verdict, brief) -> None:
    text = " ".join(
        f"{event.get('message', '')} {event.get('highlight', '')} {event.get('text', '')}"
        for event in _verdict_events(verdict, brief)
    )

    assert "4,398,702" in text and "5,000,000" in text
    assert "601,298" in text
    assert "11.23%" in text and "8.42%" in text
    for move in verdict.recommended_moves:
        assert move in text
    assert verdict.headline in text


def test_a_funded_goal_is_not_described_as_short(brief) -> None:
    funded = FeasibilityVerdict(
        verdict="on_track",
        headline="Funded.",
        projected_corpus=6_000_000.0,
        target_amount=5_000_000.0,
        shortfall=0.0,
        expected_annual_return=0.09,
        reasoning="Tools said so.",
    )

    events = _verdict_events(funded, brief)
    text = " ".join(event.get("message", "") for event in events)

    assert "fully funded" in text
    assert "short by" not in text
    # No required return exists for a funded plan, so none should be narrated.
    assert "a year against" not in text


def test_the_closing_summary_counts_tools_and_names_the_verdict(verdict) -> None:
    run = FeasibilityRun(
        verdict=verdict,
        raw="",
        model="test",
        tool_calls=[ToolCall(name="goal_solver"), ToolCall(name="nav_history")],
    )

    assert "2 tool call(s)" in _summary(run)
    assert "reachable with changes" in _summary(run)


def test_a_run_without_a_verdict_still_summarises() -> None:
    run = FeasibilityRun(verdict=None, raw="bad output", model="test", tool_calls=[])

    assert "without a usable verdict" in _summary(run)
