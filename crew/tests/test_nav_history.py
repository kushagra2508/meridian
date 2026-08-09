"""The dataset and its reader. A committed snapshot can rot silently, so these
tests check the shape and the internal consistency of the numbers."""

from __future__ import annotations

import pytest

from meridian_crew.config import FORWARD_RETURN_HAIRCUT
from meridian_crew.datasets import categories, forward_returns, nav_history, products
from meridian_crew.tools import NavHistoryTool

TOOL = NavHistoryTool()

EXPECTED_CATEGORIES = {
    "commodity_gold",
    "debt_corporate_bond",
    "debt_gilt",
    "debt_liquid",
    "debt_short_duration",
    "equity_elss",
    "equity_flexi_cap",
    "equity_large_cap",
    "equity_mid_cap",
    "equity_small_cap",
    "hybrid_aggressive",
    "hybrid_balanced_advantage",
    "index_nifty50",
}


def test_the_snapshot_covers_the_expected_categories():
    assert set(categories()) == EXPECTED_CATEGORIES


def test_every_category_is_backed_by_named_schemes():
    for key, value in categories().items():
        assert value["schemes"], f"{key} has no schemes"
        for scheme in value["schemes"]:
            assert scheme["name"].strip()
            assert scheme["code"]


def test_asset_classes_are_ones_the_haircut_table_knows():
    classes = {value["asset_class"] for value in categories().values()}
    assert classes <= set(FORWARD_RETURN_HAIRCUT)


def test_forward_return_is_below_the_trailing_cagr():
    """The haircut must actually reduce the number it is applied to."""
    for key, value in categories().items():
        trailing = value["cagr_5y"] if value["cagr_5y"] is not None else value["cagr_3y"]
        assert value["assumed_forward_return"] < trailing, key


def test_forward_return_matches_the_documented_haircut():
    for key, value in categories().items():
        trailing = value["cagr_5y"] if value["cagr_5y"] is not None else value["cagr_3y"]
        haircut = FORWARD_RETURN_HAIRCUT[value["asset_class"]]
        assert value["assumed_forward_return"] == pytest.approx(
            trailing * (1 - haircut), abs=1e-6
        ), key


def test_returns_are_decimals_not_percentages():
    for key, value in forward_returns().items():
        assert 0 < value < 0.5, f"{key} looks like a percentage, not a decimal"


def test_equity_is_more_volatile_than_debt():
    table = categories()
    equity = table["equity_large_cap"]["volatility_annualised"]
    debt = table["debt_short_duration"]["volatility_annualised"]
    liquid = table["debt_liquid"]["volatility_annualised"]
    assert equity > debt > liquid


def test_small_caps_draw_down_harder_than_large_caps():
    table = categories()
    assert table["equity_small_cap"]["max_drawdown_5y"] < table["equity_large_cap"][
        "max_drawdown_5y"
    ]


def test_drawdowns_are_negative_and_volatility_positive():
    for key, value in categories().items():
        assert value["max_drawdown_5y"] <= 0, key
        assert value["volatility_annualised"] > 0, key


def test_the_tool_returns_every_category_by_default():
    result = TOOL.run()
    assert {stats.category for stats in result.categories} == EXPECTED_CATEGORIES
    assert result.source.startswith("https://api.mfapi.in")


def test_the_tool_can_be_narrowed_to_a_few_categories():
    result = TOOL.run(categories=["equity_large_cap", "debt_liquid"])
    assert [stats.category for stats in result.categories] == [
        "equity_large_cap",
        "debt_liquid",
    ]


def test_the_tool_accepts_a_comma_separated_string():
    result = TOOL.run(categories="equity_large_cap,debt_liquid")
    assert len(result.categories) == 2


def test_unknown_category_names_the_valid_keys():
    with pytest.raises(ValueError, match="equity_large_cap"):
        TOOL.run(categories=["equity_bananas"])


def test_the_agent_facing_table_is_compact_and_complete():
    result = TOOL.run()
    rendered = TOOL.format_output_for_agent(result)
    assert len(rendered) < len(result.model_dump_json()) / 2
    for key in EXPECTED_CATEGORIES:
        assert key in rendered


def test_product_categories_all_exist_in_the_nav_snapshot():
    """A product pointing at a missing category would break the handoff into
    reallocation_search."""
    known = set(categories())
    for product in products():
        if product.get("category"):
            assert product["category"] in known, product["id"]


def test_products_declare_a_lockup_or_an_unlock_age():
    for product in products():
        assert (
            product.get("lockup_years") is not None or product.get("unlock_age") is not None
        ), product["id"]
        assert product["basis"].strip()


def test_product_ids_are_unique():
    ids = [product["id"] for product in products()]
    assert len(ids) == len(set(ids))


def test_the_snapshot_records_where_it_came_from():
    snapshot = nav_history()
    assert snapshot["source"]
    assert snapshot["generated_at"]
    assert snapshot["method"]["aggregation"]
