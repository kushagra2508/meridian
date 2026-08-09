"""Tests for the mfapi.in ETL.

The metric maths is checked offline against synthetic series. The two tests that
touch the network are marked `network` and excluded from the default run, because
a committed snapshot should not need the internet to be trustworthy.

    uv run pytest -m network
"""

from __future__ import annotations

import math
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from pull_nav_history import (  # noqa: E402
    CATEGORY_SPECS,
    annualised_volatility,
    cagr,
    fetch_scheme_list,
    fetch_series,
    max_drawdown,
    nav_near,
    parse_points,
    rank_candidates,
    scheme_metrics,
    _session,
)

TODAY = date(2026, 8, 1)


def _series(daily_growth: float, days: int, start: float = 100.0):
    """A NAV series compounding at a fixed daily rate, oldest first."""
    return [
        (TODAY - timedelta(days=days - 1 - i), start * (1 + daily_growth) ** i)
        for i in range(days)
    ]


def test_parse_points_normalises_order_and_drops_junk():
    raw = [
        {"date": "03-08-2026", "nav": "102.0"},
        {"date": "02-08-2026", "nav": "bad"},
        {"date": "01-08-2026", "nav": "100.0"},
        {"date": "31-07-2026", "nav": "0"},
    ]
    points = parse_points(raw)
    assert [nav for _, nav in points] == [100.0, 102.0]
    assert points[0][0] < points[1][0]


def test_cagr_recovers_a_known_growth_rate():
    # Exactly 10% over one year, measured a year apart.
    points = [(TODAY - timedelta(days=365), 100.0), (TODAY, 110.0)]
    assert cagr(points, 1) == pytest.approx(0.10, rel=1e-3)


def test_cagr_annualises_a_multi_year_run():
    points = [(TODAY - timedelta(days=1096), 100.0), (TODAY, 133.1)]
    assert cagr(points, 3) == pytest.approx(0.10, rel=1e-2)


def test_cagr_is_none_when_the_history_is_too_short():
    points = _series(0.0003, 200)
    assert cagr(points, 5) is None


def test_nav_near_refuses_a_distant_observation():
    points = [(TODAY - timedelta(days=200), 100.0), (TODAY, 110.0)]
    assert nav_near(points, TODAY - timedelta(days=365)) is None
    assert nav_near(points, TODAY - timedelta(days=195)) == 100.0


def test_a_straight_line_series_has_no_volatility_and_no_drawdown():
    points = _series(0.0004, 800)
    assert annualised_volatility(points) == pytest.approx(0.0, abs=1e-9)
    assert max_drawdown(points) == pytest.approx(0.0, abs=1e-12)


def test_volatility_scales_with_the_size_of_the_wobble():
    calm = [(TODAY - timedelta(days=800 - i), 100 + (i % 2)) for i in range(800)]
    wild = [(TODAY - timedelta(days=800 - i), 100 + 10 * (i % 2)) for i in range(800)]
    assert annualised_volatility(wild) > annualised_volatility(calm) > 0


def test_max_drawdown_measures_peak_to_trough():
    points = (
        _series(0.0, 100, start=100.0)
        + [(TODAY - timedelta(days=100 - i), 80.0) for i in range(50)]
        + [(TODAY - timedelta(days=50 - i), 95.0) for i in range(50)]
    )
    points.sort(key=lambda item: item[0])
    assert max_drawdown(points) == pytest.approx(-0.20, abs=1e-9)


def test_scheme_metrics_rejects_a_thin_series():
    payload = {"meta": {"scheme_code": 1}, "data": [{"date": "01-08-2026", "nav": "10"}]}
    assert scheme_metrics(payload) is None


def test_the_nifty_50_pattern_excludes_nifty_500_and_next_50():
    spec = CATEGORY_SPECS["index_nifty50"]
    assert spec.matches_name("HDFC Nifty 50 Index Fund - Direct Plan - Growth")
    assert not spec.matches_name("SBI Nifty 500 Index Fund - Direct Plan - Growth")
    assert not spec.matches_name("UTI Nifty Next 50 Index Fund - Direct Plan - Growth")


def test_regular_plans_and_payout_variants_are_filtered_out():
    spec = CATEGORY_SPECS["equity_large_cap"]
    assert spec.matches_name("SBI Large Cap Fund - Direct Plan - Growth")
    assert not spec.matches_name("SBI Large Cap Fund - Regular Plan - Growth")
    assert not spec.matches_name("SBI Large Cap Fund - Direct Plan - IDCW")
    assert not spec.matches_name("SBI Large Cap Fund - Direct Plan Growth - Bonus Option")


def test_us_and_global_funds_do_not_count_as_indian_large_cap():
    spec = CATEGORY_SPECS["equity_large_cap"]
    assert not spec.matches_name(
        "ICICI Prudential US Bluechip Equity Fund - Direct Plan - Growth"
    )


def test_gilt_funds_are_kept_out_of_short_duration():
    spec = CATEGORY_SPECS["debt_short_duration"]
    assert spec.matches_name("HDFC Short Term Debt Fund - Direct Plan - Growth")
    assert not spec.matches_name(
        "ICICI Prudential Short Term Gilt Fund - Direct Plan - Growth"
    )


def test_candidate_ranking_prefers_the_large_houses_and_caps_each_one():
    schemes = [
        {"schemeName": f"HDFC Large Cap Fund Plan {i} - Direct Plan - Growth"}
        for i in range(6)
    ] + [{"schemeName": "SBI Large Cap Fund - Direct Plan - Growth"}]
    ranked = rank_candidates(schemes, CATEGORY_SPECS["equity_large_cap"])
    houses = [name["schemeName"].split()[0] for name in ranked]
    assert houses.count("HDFC") <= 3
    assert "SBI" in houses


def test_the_category_gate_is_the_authority_not_the_name():
    spec = CATEGORY_SPECS["equity_large_cap"]
    assert spec.confirms("Equity Scheme - Large Cap Fund")
    assert not spec.confirms("Equity Scheme - Sectoral/ Thematic")
    assert not spec.confirms("Income")


@pytest.mark.network
def test_mfapi_still_serves_the_scheme_list():
    schemes = fetch_scheme_list(_session())
    assert len(schemes) > 10_000
    assert {"schemeCode", "schemeName"} <= set(schemes[0])


@pytest.mark.network
def test_a_committed_scheme_still_resolves_and_is_still_classified_the_same_way():
    """Catches an AMC re-categorising a fund under us."""
    from meridian_crew.datasets import categories

    key = "equity_large_cap"
    scheme = categories()[key]["schemes"][0]
    payload = fetch_series(_session(), scheme["code"])
    assert payload["meta"]["scheme_category"] == scheme["scheme_category"]
    assert CATEGORY_SPECS[key].confirms(payload["meta"]["scheme_category"])
