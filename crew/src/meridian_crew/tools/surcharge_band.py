"""`surcharge_band` -- turns a set of charges into the number the client pays.

Three things happen here that a flat "add 4% cess" would get wrong.

Surcharge is not one rate. Tax charged under sections 111A, 112A and 112 carries
a surcharge capped at 15% however high the income goes, while the rest of the
tax carries the full band rate. A client at Rs 2.5 crore pays 25% surcharge on
their salary tax and 15% on their capital gains tax.

Marginal relief is real money. A rupee over a threshold cannot cost more than a
rupee, so the surcharge is trimmed to the excess where it would otherwise
overshoot.

Cess comes last, on tax plus surcharge, never on income.
"""

from __future__ import annotations

from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from .tax import (
    AgeBand,
    Regime,
    SurchargeResult,
    TaxComponent,
    apply_surcharge_and_cess,
    is_special_rate,
)


def _coerce_components(value: Any) -> Any:
    """Accept the shapes a model reaches for when handing over a list of charges."""
    if value is None:
        return None
    if isinstance(value, dict):
        # {"112A": 41000, "slab": 12000}
        if all(isinstance(item, (int, float)) for item in value.values()):
            return [
                {"section": key, "amount": amount} for key, amount in value.items()
            ]
        value = [value]
    if isinstance(value, list):
        out: list[Any] = []
        for item in value:
            if isinstance(item, TaxComponent):
                out.append(item)
            elif isinstance(item, dict):
                section = item.get("section") or item.get("name") or item.get("label")
                amount = (
                    item.get("amount")
                    if item.get("amount") is not None
                    else item.get("tax")
                )
                if section is None or amount is None:
                    raise ValueError(
                        f"Could not read the tax component {item!r}. Pass "
                        '[{"section": "112A", "amount": 41000}].'
                    )
                out.append({"section": str(section), "amount": amount})
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                out.append({"section": item[0], "amount": item[1]})
            else:
                raise ValueError(f"Could not read the tax component {item!r}.")
        return out
    return value


class SurchargeBandInput(BaseModel):
    total_income: float = Field(
        ge=0,
        description=(
            "The client's total income for the year including these gains. "
            "Surcharge is a function of income, not of the tax."
        ),
    )
    components: list[TaxComponent] = Field(
        description=(
            "Every charge already priced, as a list of {section, amount} objects, "
            'e.g. [{"section": "112A", "amount": 41000}, '
            '{"section": "slab", "amount": 18500}]. Sections 111A, 112A and 112 '
            "get the capped surcharge rate; anything else gets the full rate."
        )
    )
    special_rate_income: float = Field(
        default=0.0,
        ge=0,
        description=(
            "The part of total_income taxed under 111A, 112A or 112. Used only to "
            "work out marginal relief; omit it and relief is computed as if the "
            "whole income were ordinary."
        ),
    )
    regime: Regime = Field(default="new", description="'new' or 'old' tax regime.")
    age_band: AgeBand = Field(default="below_60")

    @field_validator("components", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return _coerce_components(value)


class SurchargeBandResult(BaseModel):
    result: SurchargeResult
    total_tax: float = Field(description="The number the client actually pays.")
    special_rate_tax: float
    ordinary_tax: float
    sections_priced: list[str]


class SurchargeBandTool(BaseTool):
    name: str = "surcharge_band"
    description: str = (
        "Take the charges already priced and produce the tax actually payable: "
        "find the client's surcharge band from their total income, apply the full "
        "rate to ordinary tax and the capped 15% rate to tax under sections 111A, "
        "112A and 112, allow marginal relief where crossing a threshold would "
        "otherwise cost more than the income that crossed it, then add 4% cess on "
        "tax plus surcharge. Give it total_income and a list of "
        '{section, amount} components. Call it once, at the end, with every '
        "charge together -- surcharge is not additive across separate calls."
    )
    args_schema: Type[BaseModel] = SurchargeBandInput

    def _run(
        self,
        total_income: float,
        components: list[TaxComponent],
        special_rate_income: float = 0.0,
        regime: Regime = "new",
        age_band: AgeBand = "below_60",
    ) -> SurchargeBandResult:
        result = apply_surcharge_and_cess(
            total_income,
            components,
            regime=regime,
            age_band=age_band,
            special_rate_income=special_rate_income,
        )

        def _field(entry: Any, name: str, default: Any) -> Any:
            return entry.get(name, default) if isinstance(entry, dict) else getattr(
                entry, name, default
            )

        sections = [str(_field(entry, "section", "slab")) for entry in components or []]
        special = sum(
            float(_field(entry, "amount", 0.0))
            for entry in components or []
            if is_special_rate(str(_field(entry, "section", "slab")))
        )

        return SurchargeBandResult(
            result=result,
            total_tax=result.total_tax,
            special_rate_tax=round(special, 2),
            ordinary_tax=round(result.tax_before_surcharge - special, 2),
            sections_priced=sections,
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        wrapper = SurchargeBandResult.model_validate(raw_result)
        result = wrapper.result
        lines = [
            f"Surcharge and cess on total income of INR {result.total_income:,.0f} "
            f"({result.regime} regime)",
            f"  Tax before surcharge INR {result.tax_before_surcharge:,.0f} "
            f"({', '.join(wrapper.sections_priced) or 'none'})",
            f"    of which special   INR {wrapper.special_rate_tax:,.0f} "
            f"at a capped {result.surcharge_rate_on_special_income * 100:g}% surcharge",
            f"    of which ordinary  INR {wrapper.ordinary_tax:,.0f} "
            f"at {result.surcharge_rate * 100:g}% surcharge",
            f"  Surcharge            INR {result.surcharge:,.0f}",
        ]
        if result.marginal_relief:
            lines.append(f"  Marginal relief      INR {result.marginal_relief:,.0f}")
        lines += [
            f"  Cess                 INR {result.cess:,.0f}",
            f"  TOTAL TAX PAYABLE    INR {result.total_tax:,.0f}",
            f"  Effective rate       {result.effective_rate_on_income * 100:.2f}% of total income",
            "",
        ]
        lines += [f"  - {note}" for note in result.notes]
        return "\n".join(lines)
