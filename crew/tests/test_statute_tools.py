"""Deterministic statute maths -- no network, no LLM."""

from __future__ import annotations

from meridian_crew.statute_agent import disposals_from_moves
from meridian_crew.tools.debt_slab import DebtSlabTool
from meridian_crew.tools.fy_stager import FyStagerTool
from meridian_crew.tools.ltcg_112a import Ltcg112aTool
from meridian_crew.tools.stcg_111a import Stcg111aTool
from meridian_crew.tools.surcharge_band import SurchargeBandTool


def test_disposals_from_moves_scales_by_portfolio_value():
    disposals = disposals_from_moves(
        ["debt_liquid -> equity_mid_cap: 10.0%", "hybrid_aggressive -> equity_large_cap: 5%"],
        portfolio_value=900_000,
    )
    assert len(disposals) == 2
    assert disposals[0]["category"] == "debt_liquid"
    assert disposals[0]["redemption_value"] == 90_000
    assert disposals[1]["redemption_value"] == 45_000


def test_ltcg_112a_prices_long_equity_and_names_debt():
    result = Ltcg112aTool().run(
        disposals=[
            {
                "category": "equity_large_cap",
                "redemption_value": 800_000,
                "holding_months": 40,
                "embedded_gain_pct": 25,
            },
            {
                "category": "debt_liquid",
                "redemption_value": 200_000,
                "holding_months": 40,
            },
        ]
    )
    assert result.section == "112A"
    assert result.priced and result.priced[0].category == "equity_large_cap"
    assert any(entry.category == "debt_liquid" for entry in result.not_priced_here)
    # 200k gain, 125k exemption -> 75k taxable at 12.5% = 9375
    assert result.tax == 9375.0


def test_stcg_111a_is_twenty_percent_with_no_exemption():
    result = Stcg111aTool().run(
        disposals=[
            {
                "category": "equity_mid_cap",
                "redemption_value": 400_000,
                "holding_months": 8,
                "embedded_gain_pct": 25,
            }
        ]
    )
    assert result.section == "111A"
    assert result.tax == 20_000.0  # 100k * 20%
    assert result.months_to_long_term["equity_mid_cap"] > 0


def test_debt_slab_needs_other_income():
    result = DebtSlabTool().run(
        disposals=[
            {
                "category": "debt_liquid",
                "redemption_value": 300_000,
                "holding_months": 36,
                "embedded_gain_pct": 20,
            }
        ],
        other_taxable_income=1_200_000,
        regime="new",
    )
    assert result.slab_gain == 60_000
    assert result.tax > 0
    assert result.marginal_rate_on_gain is not None


def test_surcharge_band_adds_cess():
    result = SurchargeBandTool().run(
        total_income=1_500_000,
        components=[{"section": "112A", "amount": 10_000}],
    )
    # No surcharge below 50L; 4% cess on 10_000 = 400
    assert result.total_tax == 10_400.0


def test_fy_stager_can_save_when_exemption_is_the_binding_constraint():
    # Two years of 112A exemption beats one when the gain is large.
    result = FyStagerTool().run(
        disposals=[
            {
                "category": "equity_large_cap",
                "redemption_value": 2_000_000,
                "holding_months": 40,
                "embedded_gain_pct": 40,
            }
        ],
        other_taxable_income=1_200_000,
        financial_years=2,
    )
    assert result.single_year_tax >= result.staged_tax
    assert result.saving == result.single_year_tax - result.staged_tax
