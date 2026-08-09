"""The lock-in screen. The rule is contractual, so the tests are specific about
named products rather than about counts."""

from __future__ import annotations

import pytest

from meridian_crew.datasets import products
from meridian_crew.tools import HorizonFilterTool
from meridian_crew.tools.horizon_filter import effective_lockup

TOOL = HorizonFilterTool()


def _ids(verdicts):
    return {verdict.id for verdict in verdicts}


def test_a_two_year_goal_rules_out_elss_and_the_tax_saver_fd():
    result = TOOL.run(years_to_goal=2)
    excluded = _ids(result.excluded)
    assert {"mf_elss", "tax_saver_fd", "ppf", "nsc", "sgb", "ulip"} <= excluded
    assert "mf_debt_liquid" in _ids(result.eligible)


def test_a_seven_year_goal_admits_elss_but_never_ppf():
    result = TOOL.run(years_to_goal=7)
    assert "mf_elss" in _ids(result.eligible)
    assert "ppf" in _ids(result.excluded)


def test_a_twenty_year_goal_admits_ppf():
    result = TOOL.run(years_to_goal=20)
    assert "ppf" in _ids(result.eligible)


def test_every_product_lands_in_exactly_one_bucket():
    result = TOOL.run(years_to_goal=6, client_age=40)
    assert len(result.eligible) + len(result.excluded) == len(products())
    assert _ids(result.eligible).isdisjoint(_ids(result.excluded))


def test_exclusions_always_carry_a_reason():
    result = TOOL.run(years_to_goal=3)
    assert result.excluded
    for verdict in result.excluded:
        # Either the lock-in outlives the goal, or the age rule cannot be evaluated.
        assert "goal" in verdict.reason or "client_age" in verdict.reason, verdict.reason


def test_age_locked_products_need_an_age():
    without_age = TOOL.run(years_to_goal=25)
    reasons = {v.id: v.reason for v in without_age.excluded}
    assert "nps_tier1" in reasons
    assert "client_age" in reasons["nps_tier1"]


def test_age_locked_product_opens_up_once_the_client_is_close_enough():
    # A 55-year-old is five years from the NPS unlock age of 60.
    assert TOOL.run(years_to_goal=6, client_age=55).eligible
    assert "nps_tier1" in _ids(TOOL.run(years_to_goal=6, client_age=55).eligible)
    assert "nps_tier1" in _ids(TOOL.run(years_to_goal=4, client_age=55).excluded)


def test_effective_lockup_is_measured_from_the_client_age():
    nps = next(p for p in products() if p["id"] == "nps_tier1")
    assert effective_lockup(nps, client_age=45) == 15
    assert effective_lockup(nps, client_age=62) == 0
    assert effective_lockup(nps, client_age=None) is None


def test_suitability_is_an_advisory_not_an_exclusion():
    """A small cap fund is sellable tomorrow; it is just wrong for a short goal."""
    result = TOOL.run(years_to_goal=3)
    assert "mf_equity_small_cap" in _ids(result.eligible)
    assert any("Small Cap" in note for note in result.advisories)


def test_eligible_categories_drop_the_unsuitable_ones():
    """Eligible on paper is not the same as suitable, and only suitable
    categories should reach the reallocation search."""
    result = TOOL.run(years_to_goal=3)
    assert "equity_small_cap" not in result.eligible_categories
    assert "debt_liquid" in result.eligible_categories


def test_eligible_categories_are_all_real_category_keys():
    from meridian_crew.datasets import categories

    result = TOOL.run(years_to_goal=10, client_age=40)
    assert result.eligible_categories
    assert set(result.eligible_categories) <= set(categories())


def test_a_longer_goal_never_excludes_more_than_a_shorter_one():
    short = _ids(TOOL.run(years_to_goal=2, client_age=40).excluded)
    long = _ids(TOOL.run(years_to_goal=12, client_age=40).excluded)
    assert long <= short


def test_restricting_to_product_ids_only_screens_those():
    result = TOOL.run(years_to_goal=4, product_ids=["mf_elss", "ppf"])
    assert _ids(result.eligible) == {"mf_elss"}
    assert _ids(result.excluded) == {"ppf"}


def test_unknown_product_id_is_rejected_with_the_valid_ids():
    with pytest.raises(ValueError, match="mf_elss"):
        TOOL.run(years_to_goal=4, product_ids=["gold_bars_under_the_bed"])


def test_product_ids_accept_a_comma_separated_string():
    result = TOOL.run(years_to_goal=4, product_ids="mf_elss,ppf")
    assert _ids(result.eligible) == {"mf_elss"}
