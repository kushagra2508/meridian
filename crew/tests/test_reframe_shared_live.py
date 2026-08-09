"""Live Reframe and Shared runs against gpt-5-mini (via OpenRouter).

Marked `live`, so excluded from the default suite.

    uv run pytest -m live tests/test_reframe_shared_live.py
"""

from __future__ import annotations

import pytest

from meridian_crew.config import has_llm_credentials, llm_model
from meridian_crew.crew import default_reframe_brief, default_shared_brief, run_reframe, run_shared
from meridian_crew.agent import GoalBrief
from meridian_crew.reframe_agent import ReframeVerdict
from meridian_crew.shared_agent import SharedVerdict
from meridian_crew.tools.monthly_topup import MonthlyTopupTool
from meridian_crew.tools.shrink_target import ShrinkTargetTool
from meridian_crew.tools.slip_year import SlipYearTool

pytestmark = pytest.mark.live


@pytest.fixture(scope="module", autouse=True)
def _require_credentials():
    if not has_llm_credentials():
        pytest.skip("no LLM credentials; set OPENROUTER_API_KEY in crew/.env")


@pytest.fixture(scope="module")
def goal() -> GoalBrief:
    return GoalBrief(
        goal="Daughter's undergraduate tuition",
        target_amount=5_000_000,
        years_to_goal=7,
        current_corpus=900_000,
        monthly_contribution=25_000,
        allocation="equity_large_cap=30,hybrid_aggressive=20,debt_short_duration=30,debt_liquid=20",
        client_age=42,
    )


@pytest.fixture(scope="module")
def reframe_run(goal):
    brief = default_reframe_brief(
        goal,
        feasibility=None,
        statute=None,
        channel=None,
    )
    # Seed a shortfall context so the agent has a reason to reframe.
    brief.shortfall = 600_000
    brief.feasibility_verdict = "not_reachable"
    brief.disposals = [
        {
            "category": "debt_liquid",
            "redemption_value": 180_000,
            "holding_months": 40,
            "embedded_gain_pct": 15,
        }
    ]
    return run_reframe(brief)


@pytest.fixture(scope="module")
def shared_run(goal, reframe_run):
    reframe_verdict = (
        reframe_run.verdict if isinstance(reframe_run.verdict, ReframeVerdict) else None
    )
    brief = default_shared_brief(goal, None, None, None, reframe_verdict)
    brief.shortfall = 600_000
    brief.statute_tax = 19_500
    brief.channel_annual_drag = 7_740
    brief.feasibility_headline = "Short on the tuition goal."
    return run_shared(brief)


def test_reframe_uses_lever_tools(reframe_run):
    used = set(reframe_run.tools_used)
    # price_options is argument-sensitive; tolerate retries as long as the
    # three lever tools ran and a structured verdict came back.
    lever_errors = [
        err for err in reframe_run.tool_errors if err.name in {"slip_year", "shrink_target", "monthly_topup"}
    ]
    assert lever_errors == [], lever_errors
    assert "slip_year" in used, used
    assert "shrink_target" in used, used
    assert "monthly_topup" in used, used
    assert isinstance(reframe_run.verdict, ReframeVerdict), reframe_run.raw
    assert reframe_run.verdict.preferred_lever in {
        "slip_year",
        "shrink_target",
        "monthly_topup",
        "none",
    }


def test_reframe_numbers_track_the_tools(reframe_run, goal):
    assert reframe_run.verdict is not None
    slip = SlipYearTool().run(
        target_amount=goal.target_amount,
        years_to_goal=goal.years_to_goal,
        current_corpus=goal.current_corpus,
        monthly_contribution=goal.monthly_contribution,
        allocation=goal.allocation_argument(),
    )
    shrink = ShrinkTargetTool().run(
        target_amount=goal.target_amount,
        years_to_goal=goal.years_to_goal,
        current_corpus=goal.current_corpus,
        monthly_contribution=goal.monthly_contribution,
        allocation=goal.allocation_argument(),
    )
    topup = MonthlyTopupTool().run(
        target_amount=goal.target_amount,
        years_to_goal=goal.years_to_goal,
        current_corpus=goal.current_corpus,
        monthly_contribution=goal.monthly_contribution,
        allocation=goal.allocation_argument(),
    )
    verdict = reframe_run.verdict
    # At least one lever figure must land; gpt-mini sometimes omits a field
    # after a price_options retry even when the tool ran cleanly.
    matched = False
    if verdict.slip_delay_months is not None:
        assert verdict.slip_delay_months == pytest.approx(slip.delay_months, abs=3)
        matched = True
    if verdict.shrink_reachable_target is not None:
        assert verdict.shrink_reachable_target == pytest.approx(
            shrink.reachable_target, rel=0.08
        )
        matched = True
    if (
        verdict.topup_additional_monthly is not None
        and topup.additional_monthly_contribution
    ):
        assert verdict.topup_additional_monthly == pytest.approx(
            topup.additional_monthly_contribution, rel=0.08
        )
        matched = True
    assert matched, "verdict carried no lever figures to compare against the tools"


def test_shared_uses_desk_tools(shared_run):
    used = set(shared_run.tools_used)
    assert shared_run.tool_errors == []
    assert "eligibility_gate" in used, used
    assert "ledger" in used or "prose_writer" in used, used
    assert isinstance(shared_run.verdict, SharedVerdict), shared_run.raw
    assert shared_run.verdict.best_path
    assert len(shared_run.verdict.stances) == 4


def test_live_runs_report_the_model(reframe_run, shared_run):
    assert reframe_run.model == llm_model()
    assert shared_run.model == llm_model()
