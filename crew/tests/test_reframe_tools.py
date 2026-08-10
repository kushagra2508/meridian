"""Deterministic maths for the Rethink tool pack."""

from __future__ import annotations

import math

import numpy_financial as npf
import pytest

from meridian_crew.tools.goal_solver import monthly_rate, project_corpus
from meridian_crew.tools.monthly_topup import MonthlyTopupTool
from meridian_crew.tools.price_options import PriceOptionsTool
from meridian_crew.tools.shrink_target import ShrinkTargetTool
from meridian_crew.tools.slip_year import SlipYearTool

ALLOCATION = "equity_large_cap=30,hybrid_aggressive=20,debt_short_duration=30,debt_liquid=20"
HOLDINGS = [
    {"category": "equity_large_cap", "weight_pct": 30, "plan": "regular"},
    {"category": "hybrid_aggressive", "weight_pct": 20, "plan": "regular"},
    {"category": "debt_short_duration", "weight_pct": 30, "plan": "regular"},
    {"category": "debt_liquid", "weight_pct": 20, "plan": "regular"},
]


def test_slip_year_matches_nper_for_level_sip():
    annual = 0.10
    months_original = 84
    corpus = 900_000.0
    sip = 25_000.0
    target = 5_000_000.0

    result = SlipYearTool().run(
        target_amount=target,
        years_to_goal=months_original / 12,
        current_corpus=corpus,
        monthly_contribution=sip,
        expected_annual_return=annual,
    )
    raw = float(npf.nper(monthly_rate(annual), -sip, -corpus, target))
    expected_months = int(math.ceil(raw - 1e-9))
    assert result.months_needed == expected_months
    assert result.delay_months == max(0, expected_months - months_original)


def test_shrink_target_matches_fv_projection():
    annual = 0.09
    years = 7.0
    corpus = 900_000.0
    sip = 25_000.0
    target = 5_000_000.0

    result = ShrinkTargetTool().run(
        target_amount=target,
        years_to_goal=years,
        current_corpus=corpus,
        monthly_contribution=sip,
        expected_annual_return=annual,
    )
    truth = project_corpus(annual, int(years * 12), corpus, sip)
    assert result.reachable_target == pytest.approx(truth, rel=1e-6)
    assert result.shrink_rupees == pytest.approx(max(0.0, target - truth), rel=1e-6)


def test_monthly_topup_closes_the_gap():
    annual = 0.09
    years = 7.0
    corpus = 900_000.0
    sip = 25_000.0
    target = 5_000_000.0

    result = MonthlyTopupTool().run(
        target_amount=target,
        years_to_goal=years,
        current_corpus=corpus,
        monthly_contribution=sip,
        expected_annual_return=annual,
    )
    assert result.additional_monthly_contribution is not None
    assert result.additional_monthly_contribution > 0
    required = result.required_monthly_contribution
    assert required is not None
    projected = project_corpus(annual, int(years * 12), corpus, required)
    assert projected == pytest.approx(target, rel=1e-4)


def test_funded_plan_needs_no_reframe_levers():
    result_slip = SlipYearTool().run(
        target_amount=1_000_000,
        years_to_goal=7,
        current_corpus=2_000_000,
        monthly_contribution=0,
        expected_annual_return=0.08,
    )
    result_shrink = ShrinkTargetTool().run(
        target_amount=1_000_000,
        years_to_goal=7,
        current_corpus=2_000_000,
        monthly_contribution=0,
        expected_annual_return=0.08,
    )
    result_topup = MonthlyTopupTool().run(
        target_amount=1_000_000,
        years_to_goal=7,
        current_corpus=2_000_000,
        monthly_contribution=0,
        expected_annual_return=0.08,
    )
    assert result_slip.delay_months == 0
    assert result_shrink.shrink_rupees == 0
    assert result_topup.already_funded


def test_price_options_invokes_statute_and_channel_stack():
    options = [
        {
            "kind": "slip_year",
            "label": "Slip 14 months",
            "target_amount": 5_000_000,
            "years_to_goal": 8.2,
            "monthly_contribution": 25_000,
            "delay_months": 14,
        },
        {
            "kind": "shrink_target",
            "label": "Shrink to fv",
            "target_amount": 4_400_000,
            "years_to_goal": 7,
            "monthly_contribution": 25_000,
        },
        {
            "kind": "monthly_topup",
            "label": "Top up SIP",
            "target_amount": 5_000_000,
            "years_to_goal": 7,
            "monthly_contribution": 30_000,
        },
    ]
    result = PriceOptionsTool().run(
        options=options,
        portfolio_value=900_000,
        holdings=HOLDINGS,
        disposals=[
            {
                "category": "debt_liquid",
                "redemption_value": 180_000,
                "holding_months": 40,
                "embedded_gain_pct": 15,
            }
        ],
        other_taxable_income=1_200_000,
    )
    assert len(result.priced) == 3
    assert result.cheapest_kind is not None
    for row in result.priced:
        assert row.statute_tax >= 0
        assert row.channel_annual_drag >= 0
        assert row.all_in_friction == pytest.approx(
            row.statute_tax + row.channel_horizon_drag, abs=0.02
        )


def test_reframe_tools_accept_allocation_strings():
    slip = SlipYearTool().run(
        target_amount=5_000_000,
        years_to_goal=7,
        current_corpus=900_000,
        monthly_contribution=25_000,
        allocation=ALLOCATION,
    )
    assert slip.expected_annual_return > 0
