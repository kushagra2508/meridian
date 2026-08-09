"""`eligibility_gate` -- SEBI product ladder by investable corpus.

Custom rule table: PMS at ₹50L, AIF at ₹1Cr, UHNI desk at ₹2Cr. Below PMS the
client stays in the mutual-fund / advisory lane.
"""

from __future__ import annotations

from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

# (lane, minimum corpus, label) — descending.
SEBI_LADDER: tuple[tuple[str, float, str], ...] = (
    ("uhni", 20_000_000.0, "UHNI / family-office desk"),
    ("aif", 10_000_000.0, "Alternative Investment Fund (Cat I/II ticket)"),
    ("pms", 5_000_000.0, "Portfolio Management Services"),
    ("mf_advisory", 0.0, "Mutual funds and advisory products only"),
)

_RANK = {"uhni": 3, "aif": 2, "pms": 1, "mf_advisory": 0}


class EligibilityGateInput(BaseModel):
    investable_corpus: float = Field(
        ge=0,
        description="Corpus available to invest, in rupees.",
    )
    proposed_product: str | None = Field(
        default=None,
        description=(
            "Optional product lane to check: 'mf_advisory', 'pms', 'aif', or 'uhni'."
        ),
    )


class EligibilityGateResult(BaseModel):
    investable_corpus: float
    highest_eligible: str
    highest_eligible_label: str
    eligible_lanes: list[str]
    blocked_lanes: list[str]
    proposed_product: str | None
    proposed_allowed: bool | None
    ladder: list[dict[str, float | str]]
    assumptions: list[str]


class EligibilityGateTool(BaseTool):
    name: str = "eligibility_gate"
    description: str = (
        "Gate product access on the SEBI investable-corpus ladder: PMS at "
        "INR 50L, AIF at INR 1Cr, UHNI desk at INR 2Cr. Below PMS the client "
        "stays in mutual funds / advisory. Pass investable_corpus in rupees and "
        "optionally a proposed_product lane to test."
    )
    args_schema: Type[BaseModel] = EligibilityGateInput

    def _run(
        self,
        investable_corpus: float,
        proposed_product: str | None = None,
    ) -> EligibilityGateResult:
        eligible = [
            key for key, threshold, _ in SEBI_LADDER if investable_corpus >= threshold
        ]
        blocked = [
            key
            for key, threshold, _ in SEBI_LADDER
            if key != "mf_advisory" and investable_corpus < threshold
        ]
        highest = max(eligible, key=lambda key: _RANK[key])
        highest_label = next(
            label for key, _, label in SEBI_LADDER if key == highest
        )

        proposed = proposed_product.lower().strip() if proposed_product else None
        proposed_allowed: bool | None = None
        if proposed is not None:
            proposed_allowed = proposed in eligible

        return EligibilityGateResult(
            investable_corpus=round(investable_corpus, 2),
            highest_eligible=highest,
            highest_eligible_label=highest_label,
            eligible_lanes=eligible,
            blocked_lanes=blocked,
            proposed_product=proposed,
            proposed_allowed=proposed_allowed,
            ladder=[
                {"lane": key, "min_corpus": threshold, "label": label}
                for key, threshold, label in SEBI_LADDER
            ],
            assumptions=[
                "PMS minimum ticket INR 50,00,000 (SEBI).",
                "AIF typical ticket INR 1,00,00,000.",
                "UHNI desk threshold INR 2,00,00,000 (house rule).",
            ],
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        result = EligibilityGateResult.model_validate(raw_result)
        lines = [
            f"Investable corpus       INR {result.investable_corpus:,.0f}",
            f"Highest eligible lane   {result.highest_eligible} "
            f"({result.highest_eligible_label})",
            f"Open                    {', '.join(result.eligible_lanes)}",
        ]
        if result.blocked_lanes:
            lines.append(f"Blocked                 {', '.join(result.blocked_lanes)}")
        if result.proposed_product is not None:
            verdict = "ALLOWED" if result.proposed_allowed else "BLOCKED"
            lines.append(f"Proposed {result.proposed_product}: {verdict}")
        return "\n".join(lines)
