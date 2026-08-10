"""`price_options` -- re-invoke Tax + Fees maths on each reframed path.

This is an internal call, not a second LLM crew: it runs the same deterministic
tax and TER tools Tax and Fees use, once per option, so every path carries
a signed rupee cost the Verdict ledger can rank.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from .drag_calc import DragCalcTool, HoldingLine, coerce_holdings
from .surcharge_band import SurchargeBandTool
from .tax import assess

OptionKind = Literal["slip_year", "shrink_target", "monthly_topup", "status_quo"]


class ReframeOption(BaseModel):
    kind: OptionKind
    label: str = Field(description="Short human label for the path.")
    target_amount: float = Field(gt=0)
    years_to_goal: float = Field(gt=0)
    monthly_contribution: float = Field(ge=0)
    delay_months: int = Field(default=0, ge=0)
    notes: str | None = None


def coerce_options(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError(
                "Pass options as a JSON list of "
                '{kind, label, target_amount, years_to_goal, monthly_contribution}.'
            ) from error
        return coerce_options(parsed)
    if isinstance(value, dict):
        return [value]
    return value


class PriceOptionsInput(BaseModel):
    options: list[ReframeOption] = Field(
        description=(
            "The reframed paths to price. Typically slip_year, shrink_target, "
            "and monthly_topup, each with its solved target/years/contribution."
        )
    )
    portfolio_value: float = Field(gt=0)
    holdings: list[HoldingLine] = Field(
        description="Current holdings for Fees drag (same shape as drag_calc)."
    )
    disposals: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Switch legs to price through Tax tools. Empty when no "
            "reallocation is on the table."
        ),
    )
    other_taxable_income: float = Field(default=1_200_000.0, ge=0)
    regime: Literal["new", "old"] = "new"
    age_band: Literal["below_60", "60_to_80", "80_plus"] = "below_60"

    @field_validator("options", mode="before")
    @classmethod
    def _coerce_options(cls, value: Any) -> Any:
        return coerce_options(value)

    @field_validator("holdings", mode="before")
    @classmethod
    def _coerce_holdings(cls, value: Any) -> Any:
        return coerce_holdings(value)

    @field_validator("disposals", mode="before")
    @classmethod
    def _coerce_disposals(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                # category=rupees pairs
                out = []
                for chunk in text.split(","):
                    key, _, amount = chunk.partition("=")
                    if not _:
                        continue
                    out.append(
                        {
                            "category": key.strip(),
                            "redemption_value": float(amount),
                            "holding_months": 36,
                            "embedded_gain_pct": 25,
                        }
                    )
                return out
            return parsed if isinstance(parsed, list) else [parsed]
        return value


class PricedOption(BaseModel):
    kind: OptionKind
    label: str
    target_amount: float
    years_to_goal: float
    monthly_contribution: float
    delay_months: int
    statute_tax: float
    channel_annual_drag: float
    channel_horizon_drag: float = Field(
        description="Simple annual drag × years on the path (no compounding)."
    )
    all_in_friction: float = Field(
        description="statute_tax + channel_horizon_drag -- signed cost of the path."
    )
    sections_applied: list[str]
    notes: list[str]


class PriceOptionsResult(BaseModel):
    priced: list[PricedOption]
    cheapest_kind: OptionKind | None
    assumptions: list[str]


def _price_statute(
    disposals: list[dict[str, Any]],
    other_taxable_income: float,
    regime: str,
    age_band: str,
) -> tuple[float, list[str], list[str]]:
    if not disposals:
        return 0.0, [], ["No disposals: Tax tax is zero on this path."]

    charges, priced = assess(
        disposals,
        other_taxable_income=other_taxable_income,
        regime=regime,  # type: ignore[arg-type]
        age_band=age_band,  # type: ignore[arg-type]
    )
    components = [
        {"section": charge.section, "amount": charge.tax}
        for charge in charges
        if charge.tax > 0
    ]
    sections = sorted({charge.section for charge in charges if charge.tax > 0})
    special_income = sum(
        entry.gain for entry in priced if entry.section in ("111A", "112A", "112")
    )
    total_gains = sum(entry.gain for entry in priced)
    total_income = other_taxable_income + total_gains

    if not components:
        return 0.0, [], ["Switch gains produced no tax before surcharge."]

    surcharged = SurchargeBandTool().run(
        total_income=total_income,
        components=components,
        special_rate_income=special_income,
        regime=regime,
        age_band=age_band,
    )
    return (
        round(float(surcharged.total_tax), 2),
        sections,
        ["Tax tax from assess() + surcharge_band (same stack as the Tax agent)."],
    )


class PriceOptionsTool(BaseTool):
    name: str = "price_options"
    description: str = (
        "Re-invoke Tax and Fees pricing on each reframed option. Pass the "
        "options from slip_year / shrink_target / monthly_topup (with their solved "
        "target, years, and contribution), plus holdings and any switch disposals. "
        "Returns statute_tax, channel drag over the path horizon, and all_in_friction "
        "per option. Deterministic -- no second LLM call."
    )
    args_schema: Type[BaseModel] = PriceOptionsInput

    def _run(
        self,
        options: list[ReframeOption],
        portfolio_value: float,
        holdings: list[HoldingLine],
        disposals: list[dict[str, Any]] | None = None,
        other_taxable_income: float = 1_200_000.0,
        regime: str = "new",
        age_band: str = "below_60",
    ) -> PriceOptionsResult:
        disposals = disposals or []
        drag = DragCalcTool().run(holdings=holdings, portfolio_value=portfolio_value)
        annual_drag = float(drag.annual_drag_rupees)

        priced: list[PricedOption] = []
        for raw_option in options:
            option = (
                raw_option
                if isinstance(raw_option, ReframeOption)
                else ReframeOption.model_validate(raw_option)
            )
            tax, sections, tax_notes = _price_statute(
                disposals, other_taxable_income, regime, age_band
            )
            horizon_drag = round(annual_drag * float(option.years_to_goal), 2)
            notes = list(tax_notes)
            if option.notes:
                notes.append(option.notes)
            notes.append(
                f"Fees annual drag INR {annual_drag:,.0f} × "
                f"{option.years_to_goal:g}y = INR {horizon_drag:,.0f}."
            )
            priced.append(
                PricedOption(
                    kind=option.kind,
                    label=option.label,
                    target_amount=round(option.target_amount, 2),
                    years_to_goal=round(float(option.years_to_goal), 4),
                    monthly_contribution=round(option.monthly_contribution, 2),
                    delay_months=option.delay_months,
                    statute_tax=tax,
                    channel_annual_drag=round(annual_drag, 2),
                    channel_horizon_drag=horizon_drag,
                    all_in_friction=round(tax + horizon_drag, 2),
                    sections_applied=sections,
                    notes=notes,
                )
            )

        cheapest = min(priced, key=lambda row: row.all_in_friction) if priced else None
        return PriceOptionsResult(
            priced=priced,
            cheapest_kind=cheapest.kind if cheapest else None,
            assumptions=[
                "Tax tax from ltcg_112a / stcg_111a / debt_slab / surcharge_band.",
                "Fees drag from drag_calc; horizon drag is annual × years (simple).",
                "Same disposals and holdings are applied to every option.",
            ],
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        result = PriceOptionsResult.model_validate(raw_result)
        lines = ["Priced reframed options (Tax + Fees):", ""]
        for row in result.priced:
            lines.append(
                f"{row.kind} — {row.label}\n"
                f"  target INR {row.target_amount:,.0f} | "
                f"{row.years_to_goal:g}y | SIP INR {row.monthly_contribution:,.0f}\n"
                f"  statute tax INR {row.statute_tax:,.0f} | "
                f"horizon drag INR {row.channel_horizon_drag:,.0f} | "
                f"ALL-IN INR {row.all_in_friction:,.0f}"
            )
        if result.cheapest_kind:
            lines += ["", f"Lowest friction: {result.cheapest_kind}"]
        return "\n".join(lines)
