"""`nav_history` -- reads the pre-fetched category CAGR + volatility snapshot."""

from __future__ import annotations

from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from ..datasets import categories, nav_history
from .common import as_pct


class NavHistoryInput(BaseModel):
    categories: list[str] | None = Field(
        default=None,
        description=(
            "Category keys to report, e.g. ['equity_large_cap','debt_liquid']. "
            "Omit to get every category."
        ),
    )

    @field_validator("categories", mode="before")
    @classmethod
    def _split_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


class CategoryStats(BaseModel):
    category: str
    label: str
    asset_class: str
    as_of: str = Field(description="Date of the most recent NAV observation.")
    cagr_1y: float | None
    cagr_3y: float | None
    cagr_5y: float | None
    volatility_annualised: float | None = Field(
        description="Stdev of daily log returns over 3y, annualised."
    )
    max_drawdown_5y: float | None
    assumed_forward_return: float = Field(
        description="Trailing CAGR less an asset-class haircut. Use this for projections."
    )
    forward_return_basis: str
    schemes: list[str] = Field(description="Schemes the medians were taken across.")


class NavHistoryResult(BaseModel):
    source: str
    generated_at: str
    available_categories: list[str]
    categories: list[CategoryStats]


class NavHistoryTool(BaseTool):
    name: str = "nav_history"
    description: str = (
        "Read trailing performance for the investable asset categories: 1y/3y/5y "
        "CAGR, annualised volatility, 5-year max drawdown, and the "
        "haircut-adjusted forward return assumption used for projections. "
        "All figures are decimals (0.12 means 12%) drawn from a committed "
        "snapshot of the AMFI/mfapi.in NAV archive, so results are stable and "
        "offline. Pass a list of category keys, or omit it to see everything. "
        "Call this first when you need to know what a portfolio can plausibly earn."
    )
    args_schema: Type[BaseModel] = NavHistoryInput

    def _run(self, categories: list[str] | None = None) -> NavHistoryResult:
        snapshot = nav_history()
        table = snapshot["categories"]

        keys = list(table) if not categories else categories
        unknown = [key for key in keys if key not in table]
        if unknown:
            raise ValueError(
                f"Unknown categories {unknown}. Valid keys are: "
                f"{', '.join(sorted(table))}."
            )

        return NavHistoryResult(
            source=snapshot["source"],
            generated_at=snapshot["generated_at"],
            available_categories=sorted(table),
            categories=[
                CategoryStats(
                    category=key,
                    label=table[key]["label"],
                    asset_class=table[key]["asset_class"],
                    as_of=table[key]["as_of"],
                    cagr_1y=table[key]["cagr_1y"],
                    cagr_3y=table[key]["cagr_3y"],
                    cagr_5y=table[key]["cagr_5y"],
                    volatility_annualised=table[key]["volatility_annualised"],
                    max_drawdown_5y=table[key]["max_drawdown_5y"],
                    assumed_forward_return=table[key]["assumed_forward_return"],
                    forward_return_basis=table[key]["forward_return_basis"],
                    schemes=[scheme["name"] for scheme in table[key]["schemes"]],
                )
                for key in keys
            ],
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        """A compact table. The full JSON would be ~13x more tokens for no gain."""
        result = NavHistoryResult.model_validate(raw_result)
        lines = [
            f"Category returns (snapshot {result.generated_at[:10]}, source: {result.source})",
            "key | asset class | 1y | 3y | 5y | volatility | max drawdown 5y | forward return",
        ]
        for stats in result.categories:
            lines.append(
                " | ".join(
                    (
                        stats.category,
                        stats.asset_class,
                        as_pct(stats.cagr_1y),
                        as_pct(stats.cagr_3y),
                        as_pct(stats.cagr_5y),
                        as_pct(stats.volatility_annualised),
                        as_pct(stats.max_drawdown_5y),
                        as_pct(stats.assumed_forward_return),
                    )
                )
            )
        lines.append(
            "Forward return = trailing CAGR less an asset-class haircut; it is the "
            "figure to project with. Pass allocations to goal_solver by category key "
            "and it will blend these returns itself."
        )
        return "\n".join(lines)


def category_keys() -> list[str]:
    return sorted(categories())
