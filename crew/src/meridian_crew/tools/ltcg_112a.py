"""`ltcg_112a` -- prices the long-term equity leg of a switch under section 112A.

The tool only prices what section 112A actually covers. Anything else in the
disposal list comes back named, with the section that does cover it, so the
agent routes it to the right tool instead of quietly taxing a debt fund at 12.5%.
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
    basic_exemption_headroom,
    coerce_disposals,
    equity_ltcg_charge,
    price_all,
)

SECTION = "112A"


class Ltcg112aInput(BaseModel):
    disposals: list[Disposal] = Field(
        description=(
            "The sale legs of the proposed switch, as a list of "
            '{category, redemption_value, ...} objects. Pass every leg; the tool '
            "prices the ones section 112A covers and names the rest."
        )
    )
    exemption_already_used: float = Field(
        default=0.0,
        ge=0,
        description=(
            "Section 112A gains the client has already realised this financial "
            "year. The annual exemption is shared across all of them."
        ),
    )
    other_taxable_income: float | None = Field(
        default=None,
        ge=0,
        description=(
            "The client's other income for the year. Supply it and any unused "
            "basic exemption is set against these gains; omit it and no "
            "absorption is claimed."
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


class Ltcg112aResult(BaseModel):
    section: str
    charge: Charge
    tax: float = Field(description="Rupees payable before surcharge and cess.")
    priced: list[PricedDisposal]
    not_priced_here: list[PricedDisposal] = Field(
        description="Legs this section does not cover, each carrying its own section."
    )
    basic_exemption_absorbed: float
    assumptions: list[str]
    next_step: str


class Ltcg112aTool(BaseTool):
    name: str = "ltcg_112a"
    description: str = (
        "Price the long-term capital gains tax on equity-oriented units being "
        "sold, under section 112A: 12.5% on gains above the Rs 1,25,000 annual "
        "exemption, no indexation. Give it the sale legs as "
        "{category, redemption_value, cost_basis, holding_months} objects and, if "
        "the client has already booked equity gains this year, "
        "`exemption_already_used`. Returns rupees of tax before surcharge and "
        "cess, and names any leg that belongs to another section instead. Rates "
        "are decimals; amounts are rupees."
    )
    args_schema: Type[BaseModel] = Ltcg112aInput

    def _run(
        self,
        disposals: list[Disposal],
        exemption_already_used: float = 0.0,
        other_taxable_income: float | None = None,
        regime: Regime = "new",
        age_band: AgeBand = "below_60",
    ) -> Ltcg112aResult:
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

        charge = equity_ltcg_charge(
            gain,
            exemption_already_used=exemption_already_used,
            basic_exemption_absorbed=absorbed,
        )

        if others:
            sections = sorted({entry.section for entry in others})
            next_step = (
                "Route the remaining legs to the section that covers them: "
                + ", ".join(sections)
                + ". Then call surcharge_band once with every charge together."
            )
        else:
            next_step = (
                "Every leg was priced here. Call surcharge_band with this charge "
                "to add surcharge and cess."
            )

        return Ltcg112aResult(
            section=SECTION,
            charge=charge,
            tax=charge.tax,
            priced=mine,
            not_priced_here=others,
            basic_exemption_absorbed=round(absorbed, 2),
            assumptions=sorted(set(assumptions)),
            next_step=next_step,
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        result = Ltcg112aResult.model_validate(raw_result)
        charge = result.charge
        lines = [
            f"Section {result.section} - {charge.label}",
            f"  Gain                 INR {charge.gain:,.0f}",
            f"  Exemption applied    INR {charge.exemption_applied:,.0f}",
            f"  Taxable gain         INR {charge.taxable_gain:,.0f}",
            f"  Rate                 {(charge.rate or 0) * 100:g}%",
            f"  TAX                  INR {charge.tax:,.0f}  (before surcharge and cess)",
            "",
            f"Basis: {charge.basis}",
        ]
        if result.priced:
            lines += ["", "Priced here:"]
            lines += [
                f"  {entry.category}: INR {entry.redemption_value:,.0f} redeemed, "
                f"INR {entry.gain:,.0f} gain, held {entry.holding_months:g} months"
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
