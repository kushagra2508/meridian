"""`ter_lookup` -- Regular vs Direct expense ratios from the AMFI TER snapshot.

Direct and Regular plans of the same scheme hold the same portfolio. The only
structural difference is cost: Regular embeds a trail commission; Direct does
not. This tool reports both TERs and the gap, so the agent never has to invent a
basis-point figure.
"""

from __future__ import annotations

from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from ..datasets import expense_ratios


class TerLookupInput(BaseModel):
    categories: list[str] | None = Field(
        default=None,
        description=(
            "nav_history category keys to look up, e.g. "
            "['equity_large_cap', 'debt_liquid']. Omit to see every category."
        ),
    )

    @field_validator("categories", mode="before")
    @classmethod
    def _split_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


class CategoryTer(BaseModel):
    category: str
    label: str
    direct_ter: float = Field(description="Annual TER of the Direct plan, as a decimal.")
    regular_ter: float = Field(description="Annual TER of the Regular plan, as a decimal.")
    ter_gap: float = Field(
        description="regular_ter minus direct_ter. The annual drag of staying Regular."
    )
    representative_schemes: list[str]


class TerLookupResult(BaseModel):
    source: str
    generated_at: str
    available_categories: list[str]
    categories: list[CategoryTer]
    unknown: list[str] = Field(
        default_factory=list,
        description="Keys that have no TER record; send them to scope_guard.",
    )


class TerLookupTool(BaseTool):
    name: str = "ter_lookup"
    description: str = (
        "Look up the annual Total Expense Ratio for Regular and Direct plans of "
        "each mutual-fund category, drawn from a committed AMFI TER snapshot. "
        "Returns both TERs as decimals (0.018 means 1.8% a year) and the gap "
        "between them -- which is the annual drag of holding the Regular plan. "
        "Pass a list of category keys, or omit it to see everything. Categories "
        "with no record come back in `unknown`; those belong to scope_guard."
    )
    args_schema: Type[BaseModel] = TerLookupInput

    def _run(self, categories: list[str] | None = None) -> TerLookupResult:
        snapshot = expense_ratios()
        table = snapshot["categories"]

        keys = list(table) if not categories else categories
        known: list[CategoryTer] = []
        unknown: list[str] = []
        for key in keys:
            if key not in table:
                unknown.append(key)
                continue
            row = table[key]
            direct = float(row["direct_ter"])
            regular = float(row["regular_ter"])
            known.append(
                CategoryTer(
                    category=key,
                    label=row["label"],
                    direct_ter=direct,
                    regular_ter=regular,
                    ter_gap=round(regular - direct, 6),
                    representative_schemes=list(row.get("representative_schemes") or []),
                )
            )

        return TerLookupResult(
            source=snapshot["source"],
            generated_at=snapshot["generated_at"],
            available_categories=sorted(table),
            categories=known,
            unknown=unknown,
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        result = TerLookupResult.model_validate(raw_result)
        lines = [
            f"AMFI TER snapshot as of {result.generated_at}",
            f"Source: {result.source}",
            "",
        ]
        for row in result.categories:
            lines.append(
                f"  {row.category}: Direct {row.direct_ter * 100:.2f}% | "
                f"Regular {row.regular_ter * 100:.2f}% | "
                f"gap {row.ter_gap * 100:.2f} ppt"
            )
        if result.unknown:
            lines += ["", "No TER on file (send to scope_guard):"]
            lines += [f"  - {key}" for key in result.unknown]
        return "\n".join(lines)
