"""One real agent run, checked against the tools it was supposed to use.

Marked `live`, so it is excluded from the default run. The interesting assertion
is not that the model produced prose -- it is that the numbers in the verdict are
the same numbers `goal_solver` returns when called directly. That is the
difference between an agent using its tools and an agent narrating around them.

    uv run pytest -m live
"""

from __future__ import annotations

import pytest

from meridian_crew.agent import FeasibilityVerdict, GoalBrief
from meridian_crew.config import has_llm_credentials, llm_model
from meridian_crew.crew import run_feasibility
from meridian_crew.tools import GoalSolverTool, HorizonFilterTool

pytestmark = pytest.mark.live

SHORTFALL_BRIEF = GoalBrief(
    goal="Daughter's undergraduate tuition",
    target_amount=5_000_000,
    years_to_goal=7,
    current_corpus=900_000,
    monthly_contribution=25_000,
    allocation={
        "equity_large_cap": 30,
        "hybrid_aggressive": 20,
        "debt_short_duration": 30,
        "debt_liquid": 20,
    },
    client_age=42,
    max_equity_pct=70,
)

ON_TRACK_BRIEF = GoalBrief(
    goal="Car replacement fund",
    target_amount=1_000_000,
    years_to_goal=10,
    current_corpus=800_000,
    monthly_contribution=5_000,
    allocation={"equity_large_cap": 60, "debt_short_duration": 40},
    client_age=45,
)


@pytest.fixture(scope="module", autouse=True)
def _require_credentials():
    if not has_llm_credentials():
        pytest.skip("no LLM credentials; set OPENROUTER_API_KEY in crew/.env")


@pytest.fixture(scope="module")
def shortfall_run():
    return run_feasibility(SHORTFALL_BRIEF)


@pytest.fixture(scope="module")
def ground_truth():
    """What the tools say, computed without the model in the loop."""
    solver = GoalSolverTool().run(
        target_amount=SHORTFALL_BRIEF.target_amount,
        years_to_goal=SHORTFALL_BRIEF.years_to_goal,
        current_corpus=SHORTFALL_BRIEF.current_corpus,
        monthly_contribution=SHORTFALL_BRIEF.monthly_contribution,
        allocation=SHORTFALL_BRIEF.allocation,
    )
    horizon = HorizonFilterTool().run(
        years_to_goal=SHORTFALL_BRIEF.years_to_goal,
        client_age=SHORTFALL_BRIEF.client_age,
    )
    return solver, horizon


def test_no_tool_call_failed(shortfall_run):
    assert shortfall_run.tool_errors == [], [
        (call.name, call.error) for call in shortfall_run.tool_errors
    ]


def test_it_actually_used_its_tools(shortfall_run):
    used = set(shortfall_run.tools_used)
    assert "goal_solver" in used, f"only called {used}"
    assert "horizon_filter" in used, f"only called {used}"
    assert "reallocation_search" in used, f"only called {used}"


def test_the_answer_is_structured(shortfall_run):
    assert isinstance(shortfall_run.verdict, FeasibilityVerdict), shortfall_run.raw


def test_it_found_the_shortfall(shortfall_run):
    verdict = shortfall_run.verdict
    assert verdict.verdict in {"reachable_with_changes", "not_reachable"}
    assert verdict.shortfall > 0


def test_the_reported_numbers_are_the_tools_numbers(shortfall_run, ground_truth):
    """The whole point: no arithmetic of the model's own invention."""
    solver, _ = ground_truth
    verdict = shortfall_run.verdict

    assert verdict.target_amount == pytest.approx(solver.target_amount, rel=1e-3)
    assert verdict.projected_corpus == pytest.approx(solver.projected_corpus, rel=0.01)
    assert verdict.shortfall == pytest.approx(solver.shortfall, rel=0.01)
    assert verdict.expected_annual_return == pytest.approx(
        solver.expected_annual_return, abs=0.002
    )
    assert verdict.required_annual_return == pytest.approx(
        solver.required_annual_return, abs=0.002
    )


def test_it_reports_what_the_goal_date_rules_out(shortfall_run):
    """A 7-year goal cannot use PPF, and the agent should have said so."""
    text = " ".join(shortfall_run.verdict.ruled_out_products).lower()
    assert "ppf" in text or "provident" in text, shortfall_run.verdict.ruled_out_products


def test_it_recommends_a_shift_it_can_justify(shortfall_run):
    verdict = shortfall_run.verdict
    if verdict.verdict != "reachable_with_changes":
        pytest.skip("agent judged the goal unreachable by reallocation alone")
    assert verdict.recommended_moves
    assert verdict.recommended_shift_pct is not None
    assert 0 < verdict.recommended_shift_pct <= 100


def test_a_funded_goal_is_left_alone():
    """The failure mode worth guarding: inventing work on a plan already ahead."""
    run = run_feasibility(ON_TRACK_BRIEF)
    assert run.tool_errors == []
    assert run.verdict is not None, run.raw
    assert run.verdict.verdict == "on_track", run.verdict.reasoning
    assert run.verdict.shortfall == 0
    assert not run.verdict.recommended_moves


def test_the_run_reports_the_model_it_used(shortfall_run):
    assert shortfall_run.model == llm_model()
