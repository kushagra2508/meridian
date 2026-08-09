"""`drag_calc` -- annualised expense drag on the mutual-fund portion only.

The arithmetic is deliberate: only holdings that are mutual funds and currently
on a Regular plan contribute to the Regular-vs-Direct drag. Cash, deposits,
PPF and anything Direct already pay nothing into this number, so the agent
cannot inflate a saving by counting money that is not in Regular MFs.
"""

from __future__ import annotations

from typing import Any, Literal, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from ..datasets import expense_ratios
from .common import coerce_allocation_to_mapping

Plan = Literal["regular", "direct"]


class HoldingLine(BaseModel):
    category: str = Field(description="nav_history category key, or a product id.")
    weight_pct: float = Field(description="Percent of the whole portfolio.")
    plan: Plan = Field(
        default="regular",
        description="'regular' or 'direct'. Only Regular MF lines contribute drag.",
    )
    kind: str = Field(
        default="mutual_fund",
        description="Product kind. Only 'mutual_fund' lines are priced here.",
    )


def coerce_holdings(value: Any) -> Any:
    """Accept list / dict / compact string shapes a model reaches for."""
    if value is None:
        return None
    if isinstance(value, str):
        # category=weight:plan,category=weight:plan  or allocation-style pairs
        mapping = coerce_allocation_to_mapping(value)
        return [
            {"category": key, "weight_pct": weight, "plan": "regular", "kind": "mutual_fund"}
            for key, weight in mapping.items()
        ]
    if isinstance(value, dict):
        if all(isinstance(item, (int, float)) for item in value.values()):
            return [
                {
                    "category": key,
                    "weight_pct": weight,
                    "plan": "regular",
                    "kind": "mutual_fund",
                }
                for key, weight in value.items()
            ]
        value = [value]
    if isinstance(value, list):
        out: list[Any] = []
        for item in value:
            if isinstance(item, HoldingLine):
                out.append(item)
            elif isinstance(item, dict):
                category = (
                    item.get("category")
                    or item.get("key")
                    or item.get("name")
                    or item.get("product")
                )
                weight = (
                    item.get("weight_pct")
                    if item.get("weight_pct") is not None
                    else item.get("weight")
                )
                if category is None or weight is None:
                    raise ValueError(
                        f"Could not read holding {item!r}. Pass "
                        '[{"category": "equity_large_cap", "weight_pct": 40, '
                        '"plan": "regular"}].'
                    )
                out.append(
                    {
                        **item,
                        "category": category,
                        "weight_pct": weight,
                        "plan": str(item.get("plan") or "regular").lower(),
                        "kind": item.get("kind") or "mutual_fund",
                    }
                )
            else:
                raise ValueError(f"Could not read holding {item!r}.")
        return out
    return value


class DragCalcInput(BaseModel):
    holdings: list[HoldingLine] = Field(
        description=(
            "Current portfolio as a list of "
            '{category, weight_pct, plan, kind?} objects. Weights are percent of '
            "the whole portfolio and should sum to ~100."
        )
    )
    portfolio_value: float = Field(
        gt=0, description="Total portfolio value in rupees."
    )

    @field_validator("holdings", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return coerce_holdings(value)


class HoldingDrag(BaseModel):
    category: str
    weight_pct: float
    plan: str
    kind: str
    ter_paid: float | None
    ter_direct: float | None
    annual_drag_pct: float
    annual_drag_rupees: float
    priced: bool
    note: str


class DragCalcResult(BaseModel):
    portfolio_value: float
    mf_weight_pct: float = Field(description="Share of the portfolio that is mutual funds.")
    regular_mf_weight_pct: float
    annual_drag_pct_of_portfolio: float = Field(
        description="Regular-vs-Direct drag as a fraction of the whole portfolio."
    )
    annual_drag_pct_of_mf: float = Field(
        description="Same drag expressed against the MF sleeve alone."
    )
    annual_drag_rupees: float
    five_year_drag_rupees_simple: float = Field(
        description="Five years of the annual rupee drag, no compounding. A floor."
    )
    lines: list[HoldingDrag]
    unpriced: list[str]
    assumptions: list[str]


class DragCalcTool(BaseTool):
    name: str = "drag_calc"
    description: str = (
        "Calculate the annualised expense drag of holding Regular-plan mutual "
        "funds instead of their Direct twins. Give it the portfolio as "
        "{category, weight_pct, plan} objects and the portfolio_value in rupees. "
        "Only mutual_fund lines on plan='regular' contribute; Direct lines and "
        "non-MF holdings add zero. Returns the drag as a percent of the whole "
        "portfolio, as a percent of the MF sleeve, and in rupees a year. Rates "
        "are decimals."
    )
    args_schema: Type[BaseModel] = DragCalcInput

    def _run(
        self, holdings: list[HoldingLine], portfolio_value: float
    ) -> DragCalcResult:
        table = expense_ratios()["categories"]
        lines: list[HoldingDrag] = []
        unpriced: list[str] = []
        mf_weight = 0.0
        regular_mf_weight = 0.0
        drag_weight_points = 0.0  # sum of weight_pct * ter_gap

        for entry in holdings or []:
            category = str(
                entry.category if hasattr(entry, "category") else entry["category"]
            )
            weight = float(
                entry.weight_pct if hasattr(entry, "weight_pct") else entry["weight_pct"]
            )
            plan = str(entry.plan if hasattr(entry, "plan") else entry.get("plan", "regular"))
            kind = str(entry.kind if hasattr(entry, "kind") else entry.get("kind", "mutual_fund"))
            plan = plan.lower()
            kind = kind.lower()

            if kind != "mutual_fund":
                lines.append(
                    HoldingDrag(
                        category=category,
                        weight_pct=weight,
                        plan=plan,
                        kind=kind,
                        ter_paid=None,
                        ter_direct=None,
                        annual_drag_pct=0.0,
                        annual_drag_rupees=0.0,
                        priced=False,
                        note="Not a mutual fund; excluded from TER drag.",
                    )
                )
                unpriced.append(category)
                continue

            mf_weight += weight
            row = table.get(category)
            if row is None:
                lines.append(
                    HoldingDrag(
                        category=category,
                        weight_pct=weight,
                        plan=plan,
                        kind=kind,
                        ter_paid=None,
                        ter_direct=None,
                        annual_drag_pct=0.0,
                        annual_drag_rupees=0.0,
                        priced=False,
                        note="No TER on file for this category.",
                    )
                )
                unpriced.append(category)
                continue

            direct = float(row["direct_ter"])
            regular = float(row["regular_ter"])
            paid = regular if plan == "regular" else direct
            gap = (regular - direct) if plan == "regular" else 0.0
            if plan == "regular":
                regular_mf_weight += weight
            drag_weight_points += weight * gap
            rupees = portfolio_value * (weight / 100.0) * gap

            lines.append(
                HoldingDrag(
                    category=category,
                    weight_pct=weight,
                    plan=plan,
                    kind=kind,
                    ter_paid=paid,
                    ter_direct=direct,
                    annual_drag_pct=round(gap, 6),
                    annual_drag_rupees=round(rupees, 2),
                    priced=True,
                    note=(
                        "Already Direct; no Regular-vs-Direct drag."
                        if plan == "direct"
                        else f"Regular pays {gap * 100:.2f} ppt more than Direct a year."
                    ),
                )
            )

        drag_of_portfolio = drag_weight_points / 100.0
        drag_of_mf = (drag_weight_points / mf_weight) if mf_weight > 0 else 0.0
        annual_rupees = portfolio_value * drag_of_portfolio

        return DragCalcResult(
            portfolio_value=round(portfolio_value, 2),
            mf_weight_pct=round(mf_weight, 4),
            regular_mf_weight_pct=round(regular_mf_weight, 4),
            annual_drag_pct_of_portfolio=round(drag_of_portfolio, 6),
            annual_drag_pct_of_mf=round(drag_of_mf, 6),
            annual_drag_rupees=round(annual_rupees, 2),
            five_year_drag_rupees_simple=round(annual_rupees * 5.0, 2),
            lines=lines,
            unpriced=sorted(set(unpriced)),
            assumptions=[
                "Drag is Regular TER minus Direct TER on each Regular MF line.",
                "Non-MF holdings and Direct lines contribute zero to the drag.",
                "Five-year figure is five times the annual rupee drag, without compounding.",
            ],
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        result = DragCalcResult.model_validate(raw_result)
        lines = [
            f"Annual Regular-vs-Direct drag on a portfolio of INR {result.portfolio_value:,.0f}",
            f"  MF sleeve             {result.mf_weight_pct:g}% of portfolio",
            f"  of which Regular      {result.regular_mf_weight_pct:g}%",
            f"  Drag / portfolio      {result.annual_drag_pct_of_portfolio * 100:.3f}% a year",
            f"  Drag / MF sleeve      {result.annual_drag_pct_of_mf * 100:.3f}% a year",
            f"  ANNUAL DRAG           INR {result.annual_drag_rupees:,.0f}",
            f"  Five-year floor       INR {result.five_year_drag_rupees_simple:,.0f}",
            "",
            "Per holding:",
        ]
        for line in result.lines:
            if not line.priced:
                lines.append(f"  {line.category}: unpriced -- {line.note}")
                continue
            lines.append(
                f"  {line.category} ({line.plan}): "
                f"INR {line.annual_drag_rupees:,.0f}/yr "
                f"({line.annual_drag_pct * 100:.2f} ppt on the line)"
            )
        if result.unpriced:
            lines += ["", "Send these to scope_guard:"] + [
                f"  - {key}" for key in result.unpriced
            ]
        return "\n".join(lines)
