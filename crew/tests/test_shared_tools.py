"""Deterministic Verdict tool pack tests (eligibility + ledger)."""

from __future__ import annotations

from meridian_crew.tools.eligibility_gate import EligibilityGateTool
from meridian_crew.tools.ledger import LedgerTool


def test_eligibility_ladder_thresholds():
    gate = EligibilityGateTool()

    mf = gate.run(investable_corpus=900_000)
    assert mf.highest_eligible == "mf_advisory"
    assert "pms" in mf.blocked_lanes

    pms = gate.run(investable_corpus=5_000_000)
    assert pms.highest_eligible == "pms"
    assert "pms" in pms.eligible_lanes
    assert "aif" in pms.blocked_lanes

    aif = gate.run(investable_corpus=10_000_000)
    assert aif.highest_eligible == "aif"

    uhni = gate.run(investable_corpus=20_000_000, proposed_product="uhni")
    assert uhni.highest_eligible == "uhni"
    assert uhni.proposed_allowed is True


def test_eligibility_blocks_proposed_product():
    result = EligibilityGateTool().run(
        investable_corpus=900_000, proposed_product="pms"
    )
    assert result.proposed_allowed is False


def test_ledger_ranks_by_signed_net():
    result = LedgerTool().run(
        claims=[
            {
                "path": "status_quo",
                "label": "Do nothing",
                "amount": 601_298,
                "sign": "cost",
                "source": "Planner",
                "note": "shortfall",
            },
            {
                "path": "shrink_target",
                "label": "Shrink",
                "amount": 40_000,
                "sign": "cost",
                "source": "Rethink",
            },
            {
                "path": "monthly_topup",
                "label": "Top up",
                "amount": 80_000,
                "sign": "cost",
                "source": "Rethink",
            },
            {
                "path": "shrink_target",
                "label": "Tax",
                "amount": 19_500,
                "sign": "cost",
                "source": "Tax",
            },
        ]
    )
    assert result.best_path == "shrink_target"
    assert result.paths[0].rank == 1
    assert result.paths[0].net_rupees < 0
    # status_quo is the most negative
    by_path = {row.path: row.net_rupees for row in result.paths}
    assert by_path["status_quo"] < by_path["monthly_topup"] < by_path["shrink_target"]
