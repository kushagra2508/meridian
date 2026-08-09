"""`debt_slab` -- prices the debt leg, which since section 50AA has no long term.

Units of a specified mutual fund bought on or after 1 April 2023 are deemed
short-term however long they are held, so the gain simply joins ordinary income.
That makes the answer depend on the client's other income, which is why this
tool asks for it and the equity tools do not.

The charge is computed as the difference between two complete assessments rather
than by multiplying by a marginal rate. A gain that straddles two slabs, or that
pushes total income past the section 87A ceiling and forfeits the rebate, is then
priced correctly instead of approximately.
"""

from __future__ import annotations

from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from .tax import (
    AgeBand,
    Charge,
    Disposal,
    PricedDisposal,
    Regime,
    coerce_disposals,
    legacy_ltcg_charge,
    price_all,
    rebate_87a,
    slab_charge,
    slab_tax,
)

SLAB_SECTIONS = ("slab", "112")


class DebtSlabInput(BaseModel):
    disposals: list[Disposal] = Field(
        description=(
            "The sale legs of the proposed switch, as a list of "
            "{category, redemption_value, ...} objects. Set "
            "`acquired_before_apr_2023` on any debt leg bought before that date: "
            "those units can still be long-term."
        )
    )
    other_taxable_income: float = Field(
        ge=0,
        description=(
            "The client's taxable income for the year before these gains. "
            "Required: a slab-rate charge cannot be priced without it."
        ),
    )
    regime: Regime = Field(default="new", description="'new' or 'old' tax regime.")
    age_band: AgeBand = Field(
        default="below_60",
        description="'below_60', '60_to_80' or '80_plus'. Only the old regime uses it.",
    )

    @field_validator("disposals", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return coerce_disposals(value)


class DebtSlabResult(BaseModel):
    section: str
    charges: list[Charge]
    tax: float = Field(description="Rupees payable before surcharge and cess.")
    slab_gain: float
    legacy_ltcg_gain: float
    income_before: float
    income_after: float
    marginal_rate_on_gain: float | None = Field(
        description="Tax on the gain divided by the gain. Decimal."
    )
    rebate_87a_lost: float = Field(
        description="Rupees of section 87A rebate the gain costs the client."
    )
    priced: list[PricedDisposal]
    not_priced_here: list[PricedDisposal]
    assumptions: list[str]
    next_step: str


class DebtSlabTool(BaseTool):
    name: str = "debt_slab"
    description: str = (
        "Price the tax on debt fund units being sold. Since section 50AA, units "
        "of a specified mutual fund bought on or after 1 April 2023 are deemed "
        "short-term however long they were held, so the gain is added to ordinary "
        "income and taxed at the client's slab rate -- which means this tool needs "
        "`other_taxable_income`. Units bought before 1 April 2023 and held over 24 "
        "months are priced at 12.5% under section 112 instead. Returns rupees of "
        "tax before surcharge and cess, the effective rate on the gain, and any "
        "section 87A rebate the gain destroys."
    )
    args_schema: Type[BaseModel] = DebtSlabInput

    def _run(
        self,
        disposals: list[Disposal],
        other_taxable_income: float,
        regime: Regime = "new",
        age_band: AgeBand = "below_60",
    ) -> DebtSlabResult:
        priced = price_all(disposals)
        mine = [entry for entry in priced if entry.section in SLAB_SECTIONS]
        others = [entry for entry in priced if entry.section not in SLAB_SECTIONS]

        slab_gain = sum(entry.gain for entry in priced if entry.section == "slab")
        legacy_gain = sum(entry.gain for entry in priced if entry.section == "112")
        special_income = sum(
            entry.gain for entry in priced if entry.section in ("111A", "112A")
        )

        charges: list[Charge] = []
        if slab_gain > 0:
            charges.append(
                slab_charge(
                    slab_gain,
                    other_taxable_income,
                    special_rate_income=special_income,
                    regime=regime,
                    age_band=age_band,
                )
            )
        if legacy_gain > 0:
            charges.append(legacy_ltcg_charge(legacy_gain))

        tax = sum(charge.tax for charge in charges)
        income_after = other_taxable_income + slab_gain

        # Reported separately because it is the part of the bill nobody expects:
        # the gain can cost more than its own slab rate by tipping the client out
        # of the rebate.
        lost = max(
            0.0,
            rebate_87a(
                slab_tax(other_taxable_income, regime, age_band),
                other_taxable_income + special_income,
                regime,
            )
            - rebate_87a(
                slab_tax(income_after, regime, age_band),
                income_after + special_income,
                regime,
            ),
        )

        assumptions = sorted({note for entry in priced for note in entry.assumptions})

        if others:
            next_step = (
                "The equity legs are not priced here. Send them to ltcg_112a and "
                "stcg_111a, then call surcharge_band once with every charge."
            )
        else:
            next_step = (
                "Call surcharge_band with this charge to add surcharge and cess."
            )

        return DebtSlabResult(
            section="50AA",
            charges=charges,
            tax=round(tax, 2),
            slab_gain=round(slab_gain, 2),
            legacy_ltcg_gain=round(legacy_gain, 2),
            income_before=round(other_taxable_income, 2),
            income_after=round(income_after, 2),
            marginal_rate_on_gain=(
                round(tax / (slab_gain + legacy_gain), 6)
                if (slab_gain + legacy_gain) > 0
                else None
            ),
            rebate_87a_lost=round(lost, 2),
            priced=mine,
            not_priced_here=others,
            assumptions=assumptions,
            next_step=next_step,
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        result = DebtSlabResult.model_validate(raw_result)
        lines = [
            "Debt legs, priced at slab rates (section 50AA)",
            f"  Gain taxed at slab   INR {result.slab_gain:,.0f}",
            f"  Income before        INR {result.income_before:,.0f}",
            f"  Income after         INR {result.income_after:,.0f}",
        ]
        if result.legacy_ltcg_gain:
            lines.append(
                f"  Pre-2023 units, s112 INR {result.legacy_ltcg_gain:,.0f} at 12.5%"
            )
        lines += [
            f"  TAX                  INR {result.tax:,.0f}  (before surcharge and cess)",
        ]
        if result.marginal_rate_on_gain is not None:
            lines.append(
                f"  Effective rate       {result.marginal_rate_on_gain * 100:.2f}% on the gain"
            )
        if result.rebate_87a_lost:
            lines.append(
                f"  Rebate 87A forfeited INR {result.rebate_87a_lost:,.0f} "
                "(included in the tax above)"
            )
        for charge in result.charges:
            lines += ["", f"Basis: {charge.basis}"]
            lines += [f"  - {note}" for note in charge.notes]
        if result.not_priced_here:
            lines += ["", "NOT priced here, send these elsewhere:"]
            lines += [
                f"  {entry.category}: falls under section {entry.section}"
                for entry in result.not_priced_here
            ]
        lines += [f"  - {note}" for note in result.assumptions]
        lines += ["", result.next_step]
        return "\n".join(lines)
