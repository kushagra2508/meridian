"""Projection maths. These tests exist to catch sign-convention slips in
numpy-financial, which fail silently and plausibly rather than loudly."""

from __future__ import annotations

import pytest

from meridian_crew.tools import GoalSolverTool
from meridian_crew.tools.goal_solver import (
    monthly_rate,
    project_corpus,
    solve_required_contribution,
    solve_required_return,
    total_contributed,
)

TOOL = GoalSolverTool()


def test_monthly_rate_compounds_back_to_the_annual_rate():
    assert (1 + monthly_rate(0.12)) ** 12 == pytest.approx(1.12)


def test_lump_sum_only_is_plain_compounding():
    # 100,000 at 10% for 3 years, compounded monthly at the equivalent rate.
    assert project_corpus(0.10, 36, 100_000, 0) == pytest.approx(133_100, rel=1e-6)


def test_contributions_only_at_zero_return_is_just_the_sum():
    assert project_corpus(0.0, 24, 0, 5_000) == pytest.approx(120_000)


def test_projection_grows_with_the_return():
    low = project_corpus(0.05, 120, 100_000, 10_000)
    high = project_corpus(0.12, 120, 100_000, 10_000)
    assert high > low


def test_step_up_beats_a_level_contribution():
    level = project_corpus(0.10, 120, 0, 10_000, annual_step_up_pct=0)
    stepped = project_corpus(0.10, 120, 0, 10_000, annual_step_up_pct=10)
    assert stepped > level
    assert total_contributed(120, 10_000, 10) > total_contributed(120, 10_000, 0)


def test_step_up_of_zero_matches_the_closed_form_path():
    """The loop and numpy_financial.fv must not disagree."""
    looped = project_corpus(0.11, 84, 900_000, 25_000, annual_step_up_pct=1e-12)
    closed = project_corpus(0.11, 84, 900_000, 25_000, annual_step_up_pct=0)
    assert looped == pytest.approx(closed, rel=1e-9)


@pytest.mark.parametrize(
    ("corpus", "monthly", "months", "target"),
    [
        (900_000, 25_000, 84, 5_000_000),
        (0, 10_000, 240, 10_000_000),
        (500_000, 0, 120, 1_500_000),
        (50_000, 3_000, 36, 200_000),
    ],
)
def test_required_return_lands_on_the_target(corpus, monthly, months, target):
    rate = solve_required_return(target, months, corpus, monthly)
    assert rate is not None
    assert project_corpus(rate, months, corpus, monthly) == pytest.approx(target, rel=1e-6)


def test_required_return_with_step_up_lands_on_the_target():
    rate = solve_required_return(5_000_000, 84, 900_000, 20_000, annual_step_up_pct=10)
    assert rate is not None
    assert project_corpus(
        rate, 84, 900_000, 20_000, annual_step_up_pct=10
    ) == pytest.approx(5_000_000, rel=1e-6)


def test_required_return_is_unsolvable_with_no_money():
    assert solve_required_return(1_000_000, 120, 0, 0) is None


@pytest.mark.parametrize("step_up", [0.0, 8.0])
def test_required_contribution_lands_on_the_target(step_up):
    contribution = solve_required_contribution(
        5_000_000, 84, 900_000, 0.09, annual_step_up_pct=step_up
    )
    assert contribution is not None
    assert project_corpus(
        0.09, 84, 900_000, contribution, annual_step_up_pct=step_up
    ) == pytest.approx(5_000_000, rel=1e-6)


def test_required_contribution_is_zero_when_the_corpus_already_gets_there():
    assert solve_required_contribution(100_000, 12, 1_000_000, 0.07) == 0.0


def test_tool_reports_a_shortfall_and_a_consistent_required_return():
    result = TOOL.run(
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
    )
    assert result.on_track is False
    assert result.months == 84
    assert result.shortfall > 0
    assert result.surplus == 0
    assert result.funded_ratio < 1
    # The gap has to point the same way as the returns that produced it.
    assert result.required_annual_return > result.expected_annual_return
    assert result.required_return_gap == pytest.approx(
        result.required_annual_return - result.expected_annual_return, abs=1e-6
    )
    assert result.additional_monthly_contribution > 0
    assert project_corpus(
        result.required_annual_return, result.months, 900_000, 25_000
    ) == pytest.approx(5_000_000, rel=1e-5)


def test_tool_reports_a_surplus_when_the_plan_is_ahead():
    result = TOOL.run(
        target_amount=1_000_000,
        years_to_goal=10,
        current_corpus=800_000,
        monthly_contribution=5_000,
        allocation={"equity_large_cap": 60, "debt_short_duration": 40},
    )
    assert result.on_track is True
    assert result.shortfall == 0
    assert result.surplus > 0
    assert result.required_annual_return is None
    assert result.additional_monthly_contribution == 0


def test_allocation_blend_beats_hand_arithmetic():
    """An allocation and its equivalent explicit return must agree."""
    blended = TOOL.run(
        target_amount=1_000_000,
        years_to_goal=5,
        current_corpus=100_000,
        monthly_contribution=10_000,
        allocation={"debt_liquid": 100},
    )
    explicit = TOOL.run(
        target_amount=1_000_000,
        years_to_goal=5,
        current_corpus=100_000,
        monthly_contribution=10_000,
        expected_annual_return=blended.expected_annual_return,
    )
    assert explicit.projected_corpus == pytest.approx(blended.projected_corpus, rel=1e-9)


def test_percentage_style_return_is_read_as_a_percentage():
    as_percent = TOOL.run(
        target_amount=1_000_000, years_to_goal=5, current_corpus=500_000,
        expected_annual_return=11,
    )
    as_decimal = TOOL.run(
        target_amount=1_000_000, years_to_goal=5, current_corpus=500_000,
        expected_annual_return=0.11,
    )
    assert as_percent.projected_corpus == pytest.approx(as_decimal.projected_corpus)


def test_growth_component_reconciles_the_projection():
    result = TOOL.run(
        target_amount=5_000_000, years_to_goal=7, current_corpus=900_000,
        monthly_contribution=25_000, expected_annual_return=0.10,
    )
    assert (
        result.growth_component + result.total_contributions + 900_000
    ) == pytest.approx(result.projected_corpus, abs=0.01)


def test_missing_return_and_allocation_is_rejected():
    with pytest.raises(ValueError, match="allocation"):
        TOOL.run(target_amount=1_000_000, years_to_goal=5, current_corpus=100_000)


def test_unknown_category_names_the_valid_keys():
    with pytest.raises(ValueError, match="equity_large_cap"):
        TOOL.run(
            target_amount=1_000_000,
            years_to_goal=5,
            allocation={"crypto_moonshot": 100},
        )


def test_weights_must_sum_to_one_hundred():
    with pytest.raises(ValueError, match="sum to"):
        TOOL.run(
            target_amount=1_000_000,
            years_to_goal=5,
            allocation={"debt_liquid": 40, "equity_large_cap": 40},
        )


def test_allocation_accepts_the_compact_string_form():
    """Small models routinely pass a string where a dict was asked for."""
    result = TOOL.run(
        target_amount=1_000_000,
        years_to_goal=5,
        current_corpus=100_000,
        allocation="equity_large_cap=60, debt_short_duration=40",
    )
    assert result.expected_annual_return > 0
