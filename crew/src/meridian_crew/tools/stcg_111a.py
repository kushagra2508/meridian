"""`stcg_111a` -- prices the short-term equity leg of a switch under section 111A.

Section 111A is the expensive half of the equity story and the half advisers
forget: 20% from the first rupee, with no annual exemption to hide behind. A
switch out of a holding bought eleven months ago is priced here, not under 112A.
"""

from __future__ import annotations

from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from ..datasets import tax_rules
from .tax import (
    AgeBand,
    Charge,
    Disposal,
    PricedDisposal,
    Regime,
    basic_exemption_headroom,
    coerce_disposals,
    equity_stcg_charge,
    price_all,
)

SECTION = "111A"


class Stcg111aInput(BaseModel):
    disposals: list[Disposal] = Field(
        description=(
            "The sale legs of the proposed switch, as a list of "
            "{category, redemption_value, ...} objects. Pass every leg; the tool "
            "prices the ones section 111A covers and names the rest."
        )
    )
    other_taxable_income: float | None = Field(
        default=None,
        ge=0,
        description=(
            "The client's other income for the year. Supply it and any unused "
            "basic exemption is set against these gains first, because 20% is "
            "the dearer of the two special rates."
        ),
    )
    regime: Regime = Field(default="new", description="'new' or 'old' tax regime.")
    age_band: AgeBand = Field(
        default="below_60",
        description="Only affects the old regime's basic exemption.",
    )

    @field_validator("disposals", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return coerce_disposals(value)


class Stcg111aResult(BaseModel):
    section: str
    charge: Charge
    tax: float = Field(description="Rupees payable before surcharge and cess.")
    priced: list[PricedDisposal]
    not_priced_here: list[PricedDisposal]
    basic_exemption_absorbed: float
    months_to_long_term: dict[str, float] = Field(
        description="Per category, how much longer the units must be held to reach 112A."
    )
    assumptions: list[str]
    next_step: str


class Stcg111aTool(BaseTool):
    name: str = "stcg_111a"
    description: str = (
        "Price the short-term capital gains tax on equity-oriented units held 12 "
        "months or less, under section 111A: a flat 20% from the first rupee, "
        "with no annual exemption. Give it the sale legs as "
        "{category, redemption_value, cost_basis, holding_months} objects. "
        "Returns rupees of tax before surcharge and cess, names any leg that "
        "belongs to another section, and reports how many months short of "
        "long-term each holding is -- which is often the cheapest fix available."
    )
    args_schema: Type[BaseModel] = Stcg111aInput

    def _run(
        self,
        disposals: list[Disposal],
        other_taxable_income: float | None = None,
        regime: Regime = "new",
        age_band: AgeBand = "below_60",
    ) -> Stcg111aResult:
        priced = price_all(disposals)
        mine = [entry for entry in priced if entry.section == SECTION]
        others = [entry for entry in priced if entry.section != SECTION]
        gain = sum(entry.gain for entry in mine)

        absorbed = 0.0
        assumptions = [note for entry in priced for note in entry.assumptions]
        if other_taxable_income is None:
            assumptions.append(
                "No other income was supplied, so no unused basic exemption was "
                "claimed against these gains."
            )
        else:
            absorbed = min(
                gain, basic_exemption_headroom(other_taxable_income, regime, age_band)
            )

        charge = equity_stcg_charge(gain, basic_exemption_absorbed=absorbed)

        threshold = float(
            tax_rules()["capital_gains"]["equity_ltcg_112a"]["min_holding_months"]
        )
        waits = {
            entry.category: round(max(0.0, threshold - entry.holding_months) + 0.01, 2)
            for entry in mine
        }

        if waits:
            soonest = min(waits.values())
            next_step = (
                f"Holding the shortest leg {soonest:g} more months moves it to "
                "section 112A at 12.5% with an annual exemption. Weigh that against "
                "the market risk of delaying the switch."
            )
        else:
            next_step = "No leg falls under section 111A. Nothing to price here."

        return Stcg111aResult(
            section=SECTION,
            charge=charge,
            tax=charge.tax,
            priced=mine,
            not_priced_here=others,
            basic_exemption_absorbed=round(absorbed, 2),
            months_to_long_term=waits,
            assumptions=sorted(set(assumptions)),
            next_step=next_step,
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        result = Stcg111aResult.model_validate(raw_result)
        charge = result.charge
        lines = [
            f"Section {result.section} - {charge.label}",
            f"  Gain                 INR {charge.gain:,.0f}",
            f"  Taxable gain         INR {charge.taxable_gain:,.0f}",
            f"  Rate                 {(charge.rate or 0) * 100:g}%",
            f"  TAX                  INR {charge.tax:,.0f}  (before surcharge and cess)",
            "",
            f"Basis: {charge.basis}",
        ]
        if result.priced:
            lines += ["", "Priced here:"]
            lines += [
                f"  {entry.category}: INR {entry.gain:,.0f} gain, held "
                f"{entry.holding_months:g} months, "
                f"{result.months_to_long_term.get(entry.category, 0):g} months short "
                "of long-term"
                for entry in result.priced
            ]
        if result.not_priced_here:
            lines += ["", "NOT priced here, send these elsewhere:"]
            lines += [
                f"  {entry.category}: falls under section {entry.section}"
                for entry in result.not_priced_here
            ]
        for note in charge.notes + result.assumptions:
            lines.append(f"  - {note}")
        lines += ["", result.next_step]
        return "\n".join(lines)
