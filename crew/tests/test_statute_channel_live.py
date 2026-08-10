"""Live Tax and Fees runs against gpt-5-mini (via OpenRouter).

Marked `live`, so excluded from the default suite.

    uv run pytest -m live tests/test_statute_channel_live.py
"""

from __future__ import annotations

import pytest

from meridian_crew.channel_agent import ChannelBrief, ChannelVerdict
from meridian_crew.config import has_llm_credentials, llm_model
from meridian_crew.crew import run_channel, run_statute
from meridian_crew.statute_agent import StatuteVerdict, SwitchBrief
from meridian_crew.tools.drag_calc import DragCalcTool
from meridian_crew.tools.ltcg_112a import Ltcg112aTool

pytestmark = pytest.mark.live


@pytest.fixture(scope="module", autouse=True)
def _require_credentials():
    if not has_llm_credentials():
        pytest.skip("no LLM credentials; set OPENROUTER_API_KEY in crew/.env")


@pytest.fixture(scope="module")
def statute_run():
    brief = SwitchBrief(
        purpose="Rebalance toward mid-cap for a tuition goal",
        disposals=[
            {
                "category": "debt_liquid",
                "redemption_value": 180_000,
                "holding_months": 40,
                "embedded_gain_pct": 15,
            },
            {
                "category": "equity_large_cap",
                "redemption_value": 270_000,
                "holding_months": 30,
                "embedded_gain_pct": 30,
            },
        ],
        other_taxable_income=1_200_000,
        regime="new",
    )
    return run_statute(brief)


@pytest.fixture(scope="module")
def channel_run():
    brief = ChannelBrief(
        portfolio_value=900_000,
        holdings=[
            {"category": "equity_large_cap", "weight_pct": 30, "plan": "regular"},
            {"category": "hybrid_aggressive", "weight_pct": 20, "plan": "regular"},
            {"category": "debt_short_duration", "weight_pct": 30, "plan": "regular"},
            {"category": "debt_liquid", "weight_pct": 20, "plan": "regular"},
        ],
    )
    return run_channel(brief)


def test_statute_uses_pricing_tools(statute_run):
    used = set(statute_run.tools_used)
    assert statute_run.tool_errors == []
    assert "surcharge_band" in used or "ltcg_112a" in used, used
    assert isinstance(statute_run.verdict, StatuteVerdict), statute_run.raw
    assert statute_run.verdict.total_tax >= 0


def test_statute_numbers_track_the_tools(statute_run):
    """The headline tax should be in the same ballpark as a direct tool price."""
    legs = [
        {
            "category": "debt_liquid",
            "redemption_value": 180_000,
            "holding_months": 40,
            "embedded_gain_pct": 15,
        },
        {
            "category": "equity_large_cap",
            "redemption_value": 270_000,
            "holding_months": 30,
            "embedded_gain_pct": 30,
        },
    ]
    equity = Ltcg112aTool().run(disposals=legs)
    # Rough ceiling: equity tax + a generous debt/slab allowance, plus cess headroom.
    assert statute_run.verdict is not None
    assert statute_run.verdict.total_tax < equity.tax + 100_000


def test_channel_uses_ter_tools(channel_run):
    used = set(channel_run.tools_used)
    assert channel_run.tool_errors == []
    assert "drag_calc" in used, used
    assert "ter_lookup" in used or "scope_guard" in used, used
    assert isinstance(channel_run.verdict, ChannelVerdict), channel_run.raw


def test_channel_drag_matches_the_tool(channel_run):
    truth = DragCalcTool().run(
        holdings=[
            {"category": "equity_large_cap", "weight_pct": 30, "plan": "regular"},
            {"category": "hybrid_aggressive", "weight_pct": 20, "plan": "regular"},
            {"category": "debt_short_duration", "weight_pct": 30, "plan": "regular"},
            {"category": "debt_liquid", "weight_pct": 20, "plan": "regular"},
        ],
        portfolio_value=900_000,
    )
    assert channel_run.verdict is not None
    assert channel_run.verdict.annual_drag_rupees == pytest.approx(
        truth.annual_drag_rupees, rel=0.05
    )


def test_live_runs_report_the_model(statute_run, channel_run):
    assert statute_run.model == llm_model()
    assert channel_run.model == llm_model()
