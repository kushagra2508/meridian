"""The search has to be correct about three things: that it closes the gap when
that is possible, that it says so when it is not, and that it never breaches a
constraint to get there."""

from __future__ import annotations

import pytest

from meridian_crew.datasets import forward_returns
from meridian_crew.tools import ReallocationSearchTool
from meridian_crew.tools.common import asset_class_weights, blended_return

TOOL = ReallocationSearchTool()

BALANCED = {
    "equity_large_cap": 30,
    "hybrid_aggressive": 20,
    "debt_short_duration": 30,
    "debt_liquid": 20,
}


def test_no_change_when_the_gap_is_already_closed():
    current = blended_return(BALANCED)
    result = TOOL.run(
        current_allocation=BALANCED, required_annual_return=current - 0.01
    )
    assert result.feasible is True
    assert result.total_shift_pct == 0
    assert result.moves == []
    assert result.allocation_after == result.allocation_before


def test_closing_a_reachable_gap_moves_weight_and_raises_the_return():
    required = blended_return(BALANCED) + 0.02
    result = TOOL.run(current_allocation=BALANCED, required_annual_return=required)
    assert result.feasible is True
    assert result.total_shift_pct > 0
    assert result.return_after >= required
    assert result.residual_return_gap == 0


def test_the_result_allocation_still_sums_to_one_hundred():
    required = blended_return(BALANCED) + 0.025
    result = TOOL.run(current_allocation=BALANCED, required_annual_return=required)
    assert sum(result.allocation_after.values()) == pytest.approx(100.0, abs=1e-6)


def test_the_shift_is_reported_honestly():
    """total_shift_pct must equal the weight that actually changed hands."""
    required = blended_return(BALANCED) + 0.02
    result = TOOL.run(current_allocation=BALANCED, required_annual_return=required)
    before, after = result.allocation_before, result.allocation_after
    keys = set(before) | set(after)
    increases = sum(
        max(0.0, after.get(key, 0.0) - before.get(key, 0.0)) for key in keys
    )
    assert result.total_shift_pct == pytest.approx(increases, abs=1e-6)
    assert sum(move.weight_pct for move in result.moves) == pytest.approx(
        result.total_shift_pct, abs=1e-6
    )


def test_an_impossible_return_is_reported_as_infeasible():
    result = TOOL.run(
        current_allocation={"debt_liquid": 100}, required_annual_return=0.60
    )
    assert result.feasible is False
    assert result.residual_return_gap > 0
    assert result.binding_constraint is not None
    assert any("contribution" in note for note in result.notes)


def test_the_search_is_smallest_first():
    """A bigger required return must never need a smaller shift."""
    base = blended_return(BALANCED)
    small = TOOL.run(current_allocation=BALANCED, required_annual_return=base + 0.005)
    large = TOOL.run(current_allocation=BALANCED, required_annual_return=base + 0.02)
    assert small.total_shift_pct <= large.total_shift_pct


def test_commodity_is_capped_by_default():
    """Gold has the highest trailing return in the dataset; unchecked, a greedy
    search would put the whole portfolio in it."""
    returns = forward_returns()
    assert returns["commodity_gold"] == max(returns.values()), (
        "this test is only meaningful while gold leads the dataset"
    )
    result = TOOL.run(
        current_allocation={"debt_liquid": 100}, required_annual_return=0.20
    )
    assert result.allocation_after.get("commodity_gold", 0.0) <= 10.0
    assert result.caps_applied["commodity"] == 10.0


def test_an_explicit_asset_class_cap_is_respected():
    result = TOOL.run(
        current_allocation={"debt_liquid": 100},
        required_annual_return=0.20,
        max_asset_class_pct={"commodity": 3, "equity": 50},
    )
    weights = asset_class_weights(result.allocation_after)
    assert weights.get("commodity", 0.0) <= 3 + 1e-6
    assert weights.get("equity", 0.0) <= 50 + 1e-6


def test_equity_ceiling_is_respected():
    result = TOOL.run(
        current_allocation=BALANCED,
        required_annual_return=0.20,
        max_equity_pct=45,
    )
    assert result.equity_weight_after <= 45 + 1e-6


def test_per_category_cap_is_respected_for_receivers():
    result = ReallocationSearchTool(max_weight_per_category=25).run(
        current_allocation={"debt_liquid": 100},
        required_annual_return=0.20,
    )
    receivers = {
        key: weight
        for key, weight in result.allocation_after.items()
        if key != "debt_liquid"
    }
    assert receivers, "expected the search to move something"
    assert max(receivers.values()) <= 25 + 1e-6


def test_an_existing_overweight_holding_is_not_forcibly_trimmed():
    """The tool closes return gaps; it does not rebalance uninvited."""
    result = TOOL.run(
        current_allocation={"debt_liquid": 100},
        required_annual_return=blended_return({"debt_liquid": 100}),
    )
    assert result.allocation_after["debt_liquid"] == 100
    assert result.total_shift_pct == 0


def test_house_concentration_policy_is_not_an_llm_argument():
    """A live run had the model pass 100 here, switching the limit off."""
    assert "max_weight_per_category" not in TOOL.args_schema.model_fields
    assert "step_pct" not in TOOL.args_schema.model_fields
    assert TOOL.max_weight_per_category == 40.0


def test_max_shift_caps_the_movement():
    result = TOOL.run(
        current_allocation=BALANCED, required_annual_return=0.20, max_shift_pct=5
    )
    assert result.total_shift_pct <= 5 + 1e-6
    assert result.binding_constraint is not None


def test_locked_categories_are_never_reduced():
    result = TOOL.run(
        current_allocation=BALANCED,
        required_annual_return=0.20,
        locked_categories=["debt_short_duration"],
    )
    assert result.allocation_after.get("debt_short_duration", 0) >= 30 - 1e-6


def test_eligible_categories_restrict_the_destinations():
    allowed = ["debt_corporate_bond", "debt_short_duration", "debt_liquid"]
    result = TOOL.run(
        current_allocation=BALANCED,
        required_annual_return=0.20,
        eligible_categories=allowed,
    )
    introduced = set(result.allocation_after) - set(result.allocation_before)
    assert introduced <= set(allowed)
    assert result.feasible is False  # debt alone cannot reach 20%


def test_required_return_given_as_a_percentage_is_read_as_one():
    as_percent = TOOL.run(current_allocation=BALANCED, required_annual_return=11.0)
    as_decimal = TOOL.run(current_allocation=BALANCED, required_annual_return=0.11)
    assert as_percent.total_shift_pct == as_decimal.total_shift_pct


def test_unknown_eligible_category_is_rejected_with_the_valid_keys():
    with pytest.raises(ValueError, match="equity_large_cap"):
        TOOL.run(
            current_allocation=BALANCED,
            required_annual_return=0.12,
            eligible_categories=["not_a_category"],
        )


def test_volatility_rises_when_the_search_reaches_for_return():
    required = blended_return(BALANCED) + 0.025
    result = TOOL.run(current_allocation=BALANCED, required_annual_return=required)
    assert result.volatility_after_upper_bound > result.volatility_before_upper_bound
