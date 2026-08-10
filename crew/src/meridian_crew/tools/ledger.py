"""`ledger` -- collect signed rupee claims and rank the open paths.

Claims are signed: costs (tax, drag, shortfall) are negative; funded surplus and
savings are positive. Paths are ranked by net claim, then by lower friction.
"""

from __future__ import annotations

import json
from typing import Any, Literal, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

ClaimSign = Literal["cost", "benefit"]


class LedgerClaim(BaseModel):
    path: str = Field(description="Path id, e.g. slip_year / shrink_target / monthly_topup.")
    label: str
    amount: float = Field(
        description=(
            "Signed rupees. Pass costs as negative (or set sign='cost') and "
            "benefits as positive."
        )
    )
    sign: ClaimSign = Field(
        default="cost",
        description="'cost' forces a negative amount; 'benefit' forces positive.",
    )
    source: str = Field(
        default="desk",
        description="Which stage produced the claim: Planner, Tax, Fees, Rethink.",
    )
    note: str | None = None


def coerce_claims(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError(
                "Pass claims as a JSON list of "
                '{path, label, amount, sign?, source?}.'
            ) from error
        return coerce_claims(parsed)
    if isinstance(value, dict):
        return [value]
    return value


class LedgerInput(BaseModel):
    claims: list[LedgerClaim] = Field(
        description="Every signed rupee claim across the open paths."
    )

    @field_validator("claims", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return coerce_claims(value)


class PathRank(BaseModel):
    path: str
    label: str
    net_rupees: float
    claim_count: int
    rank: int
    notes: list[str]


class LedgerResult(BaseModel):
    paths: list[PathRank]
    best_path: str | None
    total_claims: int
    assumptions: list[str]


class LedgerTool(BaseTool):
    name: str = "ledger"
    description: str = (
        "Collect signed rupee claims from Planner / Tax / Fees / "
        "Rethink and rank the open paths. Pass claims as "
        "[{path, label, amount, sign, source}] where costs are negative (or "
        "sign='cost') and benefits are positive. Returns paths ordered best "
        "first by net_rupees."
    )
    args_schema: Type[BaseModel] = LedgerInput

    def _run(self, claims: list[LedgerClaim]) -> LedgerResult:
        buckets: dict[str, dict[str, Any]] = {}
        for raw in claims or []:
            claim = (
                raw if isinstance(raw, LedgerClaim) else LedgerClaim.model_validate(raw)
            )
            amount = float(claim.amount)
            if claim.sign == "cost":
                amount = -abs(amount)
            else:
                amount = abs(amount)
            bucket = buckets.setdefault(
                claim.path,
                {
                    "path": claim.path,
                    "label": claim.label,
                    "net": 0.0,
                    "count": 0,
                    "notes": [],
                },
            )
            bucket["net"] += amount
            bucket["count"] += 1
            if claim.note:
                bucket["notes"].append(f"{claim.source}: {claim.note}")
            else:
                bucket["notes"].append(
                    f"{claim.source}: {claim.label} = INR {amount:,.0f}"
                )

        ordered = sorted(
            buckets.values(),
            key=lambda row: (-row["net"], row["path"]),
        )
        ranks = [
            PathRank(
                path=row["path"],
                label=row["label"],
                net_rupees=round(row["net"], 2),
                claim_count=row["count"],
                rank=index + 1,
                notes=row["notes"][:6],
            )
            for index, row in enumerate(ordered)
        ]
        return LedgerResult(
            paths=ranks,
            best_path=ranks[0].path if ranks else None,
            total_claims=len(claims or []),
            assumptions=[
                "Costs are stored as negative rupees; benefits as positive.",
                "Paths rank by highest net_rupees, then by path id.",
            ],
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        result = LedgerResult.model_validate(raw_result)
        if not result.paths:
            return "Ledger is empty -- no claims to rank."
        lines = ["Ranked paths (best first):", ""]
        for row in result.paths:
            lines.append(
                f"#{row.rank} {row.path} — {row.label}: net INR {row.net_rupees:,.0f} "
                f"({row.claim_count} claims)"
            )
        lines += ["", f"Best path: {result.best_path}"]
        return "\n".join(lines)
