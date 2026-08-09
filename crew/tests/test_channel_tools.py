"""Deterministic maths for the Channel tools -- no network, no LLM."""

from __future__ import annotations

from meridian_crew.tools.drag_calc import DragCalcTool
from meridian_crew.tools.scope_guard import ScopeGuardTool
from meridian_crew.tools.ter_lookup import TerLookupTool


def test_ter_lookup_returns_regular_above_direct():
    result = TerLookupTool().run(categories=["equity_large_cap", "index_nifty50"])
    assert len(result.categories) == 2
    for row in result.categories:
        assert row.regular_ter > row.direct_ter
        assert row.ter_gap == round(row.regular_ter - row.direct_ter, 6)


def test_ter_lookup_names_unknown_categories():
    result = TerLookupTool().run(categories=["equity_large_cap", "not_a_fund"])
    assert result.unknown == ["not_a_fund"]
    assert [row.category for row in result.categories] == ["equity_large_cap"]


def test_drag_calc_only_charges_regular_mf_lines():
    result = DragCalcTool().run(
        holdings=[
            {"category": "equity_large_cap", "weight_pct": 50, "plan": "regular"},
            {"category": "debt_liquid", "weight_pct": 30, "plan": "direct"},
            {"category": "ppf", "weight_pct": 20, "plan": "regular", "kind": "small_savings"},
        ],
        portfolio_value=1_000_000,
    )
    assert result.mf_weight_pct == 80
    assert result.regular_mf_weight_pct == 50
    # Only the Regular equity line contributes.
    equity_gap = next(
        line.annual_drag_pct for line in result.lines if line.category == "equity_large_cap"
    )
    assert result.annual_drag_rupees == round(1_000_000 * 0.50 * equity_gap, 2)
    assert "ppf" in result.unpriced


def test_drag_calc_is_zero_when_everything_is_direct():
    result = DragCalcTool().run(
        holdings=[
            {"category": "equity_large_cap", "weight_pct": 60, "plan": "direct"},
            {"category": "debt_liquid", "weight_pct": 40, "plan": "direct"},
        ],
        portfolio_value=500_000,
    )
    assert result.annual_drag_rupees == 0
    assert result.annual_drag_pct_of_portfolio == 0


def test_scope_guard_splits_priced_from_unpriced():
    result = ScopeGuardTool().run(
        items=[
            {"id": "equity_large_cap", "kind": "mutual_fund"},
            {"id": "ppf"},
            {"id": "ulip"},
            {"id": "nps_tier1"},
        ]
    )
    in_ids = {item.id for item in result.in_scope}
    out_ids = {item.id for item in result.out_of_scope}
    assert "equity_large_cap" in in_ids
    assert {"ppf", "ulip", "nps_tier1"} <= out_ids
    assert any("Cannot price" in line for line in result.aloud)
