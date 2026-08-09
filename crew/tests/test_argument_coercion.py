"""The tool-argument boundary.

A live run against gpt-5-mini failed here first: `allocation` was declared as a
mapping, which JSON Schema can only describe through `additionalProperties`, so
strict function-calling gave the model an object with no nameable keys and it sent
`{}` four times in a row. The wire format is now a list of explicit objects. These
tests pin that down, along with the shapes a model might improvise.
"""

from __future__ import annotations

import pytest

from meridian_crew.tools import GoalSolverTool, ReallocationSearchTool
from meridian_crew.tools.common import (
    AssetClassCap,
    CategoryWeight,
    caps_to_mapping,
    coerce_allocation,
    coerce_allocation_to_mapping,
    weights_to_mapping,
)

GOAL = GoalSolverTool()
REALLOC = ReallocationSearchTool()

EXPECTED = {"equity_large_cap": 60.0, "debt_liquid": 40.0}


def test_the_advertised_schema_declares_every_key_it_needs():
    """No `additionalProperties`-only object may reach the model again."""
    schema = GOAL.args_schema.model_json_schema()
    allocation = schema["properties"]["allocation"]
    rendered = str(allocation) + str(schema.get("$defs", {}))
    assert "additionalProperties" not in rendered, allocation
    assert "category" in rendered and "weight_pct" in rendered


def test_reallocation_schema_declares_every_key_too():
    schema = REALLOC.args_schema.model_json_schema()
    rendered = str(schema)
    assert "additionalProperties" not in rendered
    assert "asset_class" in rendered and "max_pct" in rendered


@pytest.mark.parametrize(
    "value",
    [
        {"equity_large_cap": 60, "debt_liquid": 40},
        [{"category": "equity_large_cap", "weight_pct": 60}, {"category": "debt_liquid", "weight_pct": 40}],
        "equity_large_cap=60,debt_liquid=40",
        "equity_large_cap: 60; debt_liquid: 40",
        "equity_large_cap=60%, debt_liquid=40%",
        '{"equity_large_cap": 60, "debt_liquid": 40}',
        '[{"category": "equity_large_cap", "weight_pct": 60}, {"category": "debt_liquid", "weight_pct": 40}]',
        [("equity_large_cap", 60), ("debt_liquid", 40)],
        [{"key": "equity_large_cap", "weight": 60}, {"key": "debt_liquid", "weight": 40}],
        [CategoryWeight(category="equity_large_cap", weight_pct=60), CategoryWeight(category="debt_liquid", weight_pct=40)],
    ],
)
def test_every_plausible_allocation_shape_lands_in_the_same_place(value):
    assert coerce_allocation_to_mapping(value) == EXPECTED


def test_coercion_always_produces_the_list_wire_format():
    coerced = coerce_allocation({"equity_large_cap": 60, "debt_liquid": 40})
    assert isinstance(coerced, list)
    assert coerced[0] == {"category": "equity_large_cap", "weight_pct": 60}


def test_duplicate_categories_are_summed_not_dropped():
    value = [
        {"category": "equity_large_cap", "weight_pct": 30},
        {"category": "equity_large_cap", "weight_pct": 30},
        {"category": "debt_liquid", "weight_pct": 40},
    ]
    assert weights_to_mapping(value) == EXPECTED


def test_an_unreadable_entry_is_rejected_with_the_format_hint():
    with pytest.raises(ValueError, match="weight_pct"):
        coerce_allocation([{"fund": "something", "amount": 50}])


def test_an_unparsable_string_is_rejected_with_the_format_hint():
    with pytest.raises(ValueError, match="weight_pct"):
        coerce_allocation("just some prose")


def test_an_empty_allocation_says_so_actionably():
    """The exact failure from the live run: an empty argument must explain itself."""
    with pytest.raises(ValueError, match="weight_pct"):
        GOAL.run(target_amount=1_000_000, years_to_goal=5, current_corpus=100_000, allocation=[])


def test_caps_read_as_dicts_or_as_models():
    expected = {"commodity": 5.0, "equity": 50.0}
    as_dicts = [
        {"asset_class": "commodity", "max_pct": 5},
        {"asset_class": "equity", "max_pct": 50},
    ]
    as_models = [
        AssetClassCap(asset_class="commodity", max_pct=5),
        AssetClassCap(asset_class="equity", max_pct=50),
    ]
    assert caps_to_mapping(as_dicts) == expected
    assert caps_to_mapping(as_models) == expected


def test_tools_accept_the_list_form_end_to_end():
    solved = GOAL.run(
        target_amount=5_000_000,
        years_to_goal=7,
        current_corpus=900_000,
        monthly_contribution=25_000,
        allocation=[
            {"category": "equity_large_cap", "weight_pct": 30},
            {"category": "hybrid_aggressive", "weight_pct": 20},
            {"category": "debt_short_duration", "weight_pct": 30},
            {"category": "debt_liquid", "weight_pct": 20},
        ],
    )
    assert solved.shortfall > 0

    shifted = REALLOC.run(
        current_allocation=[
            {"category": "equity_large_cap", "weight_pct": 30},
            {"category": "hybrid_aggressive", "weight_pct": 20},
            {"category": "debt_short_duration", "weight_pct": 30},
            {"category": "debt_liquid", "weight_pct": 20},
        ],
        required_annual_return=solved.required_annual_return,
        max_asset_class_pct=[{"asset_class": "commodity", "max_pct": 5}],
    )
    assert shifted.caps_applied["commodity"] == 5.0
    assert shifted.allocation_after.get("commodity_gold", 0) <= 5


def test_the_brief_hands_the_agent_a_ready_made_argument():
    """The prompt should contain the argument, not a description of it."""
    from meridian_crew.agent import GoalBrief

    brief = GoalBrief(
        goal="test",
        target_amount=1_000_000,
        years_to_goal=5,
        allocation="equity_large_cap=60,debt_liquid=40",
    )
    assert brief.allocation == EXPECTED
    assert '"category": "equity_large_cap"' in brief.allocation_argument()
    assert brief.allocation_argument() in brief.as_prompt_block()
