"""`fy_stager` -- tests whether splitting the switch across financial years pays.

The Rs 1,25,000 exemption under section 112A is annual, not per transaction. A
switch executed in one go uses it once; the same switch split either side of
31 March uses it twice. Slab-rate debt gains benefit too, for a different reason:
half a gain may sit in a lower band than the whole one, and may leave the section
87A rebate intact.

The tool prices both plans in full and reports the difference. It does not
recommend staging: the second tranche stays in the wrong asset for months, and
that exposure is a real cost this tool cannot price.
"""

from __future__ import annotations

from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from ..datasets import tax_rules
from .tax import (
    AgeBand,
    Disposal,
    Regime,
    apply_surcharge_and_cess,
    assess,
    coerce_disposals,
)

MAX_TRANCHES = 5


def _scaled(disposals: list[Any], fraction: float) -> list[dict[str, Any]]:
    """The same disposals, each cut to a fraction of its size."""
    out: list[dict[str, Any]] = []
    for entry in disposals or []:
        record = entry if isinstance(entry, dict) else entry.model_dump()
        scaled = dict(record)
        scaled["redemption_value"] = float(record.get("redemption_value") or 0.0) * fraction
        if record.get("cost_basis") is not None:
            scaled["cost_basis"] = float(record["cost_basis"]) * fraction
        out.append(scaled)
    return out


class FyStagerInput(BaseModel):
    disposals: list[Disposal] = Field(
        description=(
            "The whole switch, as a list of {category, redemption_value, ...} "
            "objects. The tool splits it internally; do not pre-split it."
        )
    )
    other_taxable_income: float = Field(
        default=0.0,
        ge=0,
        description="The client's income before these gains, in each of the years.",
    )
    financial_years: int = Field(
        default=2,
        ge=1,
        le=MAX_TRANCHES,
        description="How many financial years to spread the switch across.",
    )
    exemption_already_used: float = Field(
        default=0.0,
        ge=0,
        description=(
            "Section 112A gains already realised in the first year. Later years "
            "start with the full exemption again."
        ),
    )
    regime: Regime = Field(default="new")
    age_band: AgeBand = Field(default="below_60")

    @field_validator("disposals", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return coerce_disposals(value)


class TranchePlan(BaseModel):
    financial_year_index: int = Field(description="1 is the current year.")
    share_of_switch: float = Field(description="Fraction of the switch executed.")
    gains_realised: float
    exemption_112a_used: float
    tax: float


class FyStagerResult(BaseModel):
    single_year_tax: float
    staged_tax: float
    saving: float = Field(description="single_year_tax less staged_tax. Never negative.")
    saving_pct_of_switch: float
    financial_years: int
    tranches: list[TranchePlan]
    annual_exemption: float
    exemption_used_once: float
    exemption_used_staged: float
    worth_doing: bool
    notes: list[str]


class FyStagerTool(BaseTool):
    name: str = "fy_stager"
    description: str = (
        "Test whether executing the switch across two financial years costs less "
        "tax than doing it in one. The Rs 1,25,000 section 112A exemption resets "
        "on 1 April, so splitting a switch either side of 31 March can use it "
        "twice; slab-rate debt gains can also fall into a lower band when halved. "
        "Give it the whole switch as {category, redemption_value, ...} objects "
        "and the client's other income. Returns the tax under both plans and the "
        "rupee difference. It does not price the market risk of leaving half the "
        "money in the wrong asset for a few months -- weigh that yourself."
    )
    args_schema: Type[BaseModel] = FyStagerInput

    def _run(
        self,
        disposals: list[Disposal],
        other_taxable_income: float = 0.0,
        financial_years: int = 2,
        exemption_already_used: float = 0.0,
        regime: Regime = "new",
        age_band: AgeBand = "below_60",
    ) -> FyStagerResult:
        annual_exemption = float(
            tax_rules()["capital_gains"]["equity_ltcg_112a"]["annual_exemption"]
        )

        def price(legs: list[Any], used: float) -> tuple[float, float, float]:
            """(tax payable, gains realised, 112A exemption consumed)."""
            charges, priced = assess(
                legs,
                other_taxable_income=other_taxable_income,
                regime=regime,
                age_band=age_band,
                exemption_already_used=used,
            )
            gains = sum(entry.gain for entry in priced)
            special_income = sum(
                entry.gain for entry in priced if entry.section in ("111A", "112A", "112")
            )
            slab_gains = sum(entry.gain for entry in priced if entry.section == "slab")
            total = apply_surcharge_and_cess(
                other_taxable_income + slab_gains + special_income,
                [{"section": charge.section, "amount": charge.tax} for charge in charges],
                regime=regime,
                age_band=age_band,
                special_rate_income=special_income,
            )
            consumed = sum(
                charge.exemption_applied for charge in charges if charge.section == "112A"
            )
            return total.total_tax, gains, consumed

        single_tax, total_gains, single_exemption = price(
            list(disposals or []), exemption_already_used
        )

        share = 1.0 / financial_years
        tranches: list[TranchePlan] = []
        staged_tax = 0.0
        staged_exemption = 0.0
        for index in range(financial_years):
            # Only the current year carries gains the client has already booked.
            used = exemption_already_used if index == 0 else 0.0
            tax, gains, consumed = price(_scaled(list(disposals or []), share), used)
            staged_tax += tax
            staged_exemption += consumed
            tranches.append(
                TranchePlan(
                    financial_year_index=index + 1,
                    share_of_switch=round(share, 4),
                    gains_realised=round(gains, 2),
                    exemption_112a_used=round(consumed, 2),
                    tax=round(tax, 2),
                )
            )

        saving = max(0.0, single_tax - staged_tax)
        switch_value = sum(
            float(
                (entry if isinstance(entry, dict) else entry.model_dump()).get(
                    "redemption_value"
                )
                or 0.0
            )
            for entry in disposals or []
        )

        notes = [
            f"The section 112A exemption is Rs {annual_exemption:,.0f} per financial "
            f"year and resets on 1 April, so a {financial_years}-year split can claim "
            f"it {financial_years} times.",
            "Both plans are priced through the full assessment, including surcharge "
            "and cess, so the difference is the tax actually saved.",
        ]
        if saving <= 0:
            notes.append(
                "Staging saves nothing here: the exemption is already exhausted or "
                "the gains are not of a kind that an extra year helps."
            )
        else:
            notes.append(
                "This saving is not free. The untraded tranche stays in the asset "
                "the plan is trying to leave, and a few months of that exposure can "
                "cost more than the tax it saves. Say so when you recommend it."
            )
        if financial_years > 2:
            notes.append(
                f"A {financial_years}-year stagger keeps the portfolio mid-switch "
                "for years. Two tranches is usually the most a goal date tolerates."
            )

        return FyStagerResult(
            single_year_tax=round(single_tax, 2),
            staged_tax=round(staged_tax, 2),
            saving=round(saving, 2),
            saving_pct_of_switch=(
                round(saving / switch_value, 6) if switch_value > 0 else 0.0
            ),
            financial_years=financial_years,
            tranches=tranches,
            annual_exemption=annual_exemption,
            exemption_used_once=round(single_exemption, 2),
            exemption_used_staged=round(staged_exemption, 2),
            worth_doing=saving > 0,
            notes=notes,
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        result = FyStagerResult.model_validate(raw_result)
        lines = [
            "Staging the switch across financial years",
            f"  All in one year      INR {result.single_year_tax:,.0f} tax",
            f"  Split over {result.financial_years}         INR {result.staged_tax:,.0f} tax",
            f"  SAVING               INR {result.saving:,.0f} "
            f"({result.saving_pct_of_switch * 100:.2f}% of the amount switched)",
            "",
            f"  Section 112A exemption used: INR {result.exemption_used_once:,.0f} "
            f"in one year, INR {result.exemption_used_staged:,.0f} staged "
            f"(cap INR {result.annual_exemption:,.0f} a year)",
            "",
            "Per financial year:",
        ]
        lines += [
            f"  FY{tranche.financial_year_index}: "
            f"{tranche.share_of_switch * 100:g}% of the switch, "
            f"INR {tranche.gains_realised:,.0f} gains, "
            f"INR {tranche.exemption_112a_used:,.0f} exemption, "
            f"INR {tranche.tax:,.0f} tax"
            for tranche in result.tranches
        ]
        lines += [""] + [f"  - {note}" for note in result.notes]
        return "\n".join(lines)
