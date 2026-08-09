"""`scope_guard` -- names what the Channel tools cannot price.

Silence here is the failure mode: an agent that quietly skips a ULIP, a PMS
mandate or an offshore fund leaves the client thinking the drag figure covers
everything. This tool returns the unpriced items so the agent can say so aloud.
"""

from __future__ import annotations

from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from ..datasets import expense_ratios, products

# Product kinds Meridian's TER tools do not cover. Mutual funds are in scope;
# everything else must be named.
OUT_OF_SCOPE_KINDS = frozenset(
    {
        "small_savings",
        "deposit",
        "bond",
        "insurance",
        "retirement",
        "pms",
        "aif",
        "equity_direct",
        "real_estate",
        "offshore",
        "crypto",
        "other",
    }
)

KIND_REASONS = {
    "small_savings": "Small-savings schemes have no AMFI TER and no Regular/Direct split.",
    "deposit": "Bank deposits are not mutual funds; expense ratio does not apply.",
    "bond": "Sovereign and listed bonds are outside the AMFI TER table.",
    "insurance": "ULIPs and other insurance products use IRDAI charge schedules, not AMFI TER.",
    "retirement": "NPS/EPF fee structures are set by PFRDA/EPFO, not AMFI TER.",
    "pms": "Portfolio Management Services quote a negotiated fee, not a scheme TER.",
    "aif": "Alternative Investment Funds sit outside the mutual-fund TER regime.",
    "equity_direct": "Direct equity holdings have brokerage, not a fund expense ratio.",
    "real_estate": "Property and REITs are outside this Channel scope.",
    "offshore": "Foreign-domiciled funds are not in the AMFI TER disclosure.",
    "crypto": "Digital assets are out of scope for AMFI TER pricing.",
    "other": "No TER mapping is on file for this product kind.",
}


class ScopeItem(BaseModel):
    id: str = Field(description="A product id, category key, or free-text label.")
    kind: str | None = Field(
        default=None,
        description="Product kind when known: mutual_fund, ulip, pms, deposit, ...",
    )
    label: str | None = Field(default=None, description="Human name, if available.")


class ScopeGuardInput(BaseModel):
    items: list[ScopeItem] = Field(
        description=(
            "Holdings or products to screen, as a list of {id, kind?, label?} "
            "objects. Pass everything the client holds; the tool sorts priced "
            "from unpriced."
        )
    )

    @field_validator("items", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return [
                {"id": part.strip()}
                for part in value.replace(";", ",").split(",")
                if part.strip()
            ]
        if isinstance(value, dict):
            value = [value]
        if isinstance(value, list):
            out: list[Any] = []
            for item in value:
                if isinstance(item, ScopeItem):
                    out.append(item)
                elif isinstance(item, str):
                    out.append({"id": item})
                elif isinstance(item, dict):
                    ident = item.get("id") or item.get("category") or item.get("name")
                    if ident is None:
                        raise ValueError(
                            f"Could not read scope item {item!r}. Pass "
                            '[{"id": "ppf", "kind": "small_savings"}].'
                        )
                    out.append({**item, "id": ident})
                else:
                    raise ValueError(f"Could not read scope item {item!r}.")
            return out
        return value


class ScopeVerdict(BaseModel):
    id: str
    label: str
    kind: str
    in_scope: bool
    reason: str


class ScopeGuardResult(BaseModel):
    in_scope: list[ScopeVerdict]
    out_of_scope: list[ScopeVerdict]
    aloud: list[str] = Field(
        description="One-line statements the agent should say out loud."
    )


def _product_index() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in products()}


class ScopeGuardTool(BaseTool):
    name: str = "scope_guard"
    description: str = (
        "Identify which holdings the Channel tools can price and which they "
        "cannot. Give it a list of {id, kind?, label?} objects covering "
        "everything the client holds. Mutual-fund categories with an AMFI TER "
        "record are in scope; PPF, NPS, ULIP, deposits, PMS, direct equity and "
        "anything else come back in `out_of_scope` with a reason. Always call "
        "this when the portfolio is not pure open-ended Indian MFs, and report "
        "the out-of-scope list aloud so the drag figure is not mistaken for a "
        "whole-portfolio cost."
    )
    args_schema: Type[BaseModel] = ScopeGuardInput

    def _run(self, items: list[ScopeItem]) -> ScopeGuardResult:
        ter_keys = set(expense_ratios()["categories"])
        catalogue = _product_index()
        in_scope: list[ScopeVerdict] = []
        out_of_scope: list[ScopeVerdict] = []

        for entry in items or []:
            ident = str(entry.id if hasattr(entry, "id") else entry["id"])
            kind = entry.kind if hasattr(entry, "kind") else entry.get("kind")
            label = entry.label if hasattr(entry, "label") else entry.get("label")

            product = catalogue.get(ident)
            if product is not None:
                kind = kind or product.get("kind")
                label = label or product.get("name")
                category = product.get("category")
            else:
                category = ident if ident in ter_keys else None

            kind = (kind or ("mutual_fund" if category in ter_keys else "other")).lower()
            label = label or ident

            if kind == "mutual_fund" and category in ter_keys:
                in_scope.append(
                    ScopeVerdict(
                        id=ident,
                        label=label,
                        kind=kind,
                        in_scope=True,
                        reason=f"AMFI TER on file under category '{category}'.",
                    )
                )
            elif kind == "mutual_fund" and ident in ter_keys:
                in_scope.append(
                    ScopeVerdict(
                        id=ident,
                        label=label,
                        kind=kind,
                        in_scope=True,
                        reason=f"AMFI TER on file under category '{ident}'.",
                    )
                )
            else:
                reason = KIND_REASONS.get(
                    kind,
                    "No AMFI TER mapping is on file for this holding.",
                )
                if kind == "mutual_fund":
                    reason = (
                        f"'{ident}' looks like a mutual fund but has no TER "
                        "record in the committed AMFI snapshot."
                    )
                out_of_scope.append(
                    ScopeVerdict(
                        id=ident,
                        label=label,
                        kind=kind if kind in OUT_OF_SCOPE_KINDS or kind == "mutual_fund" else kind,
                        in_scope=False,
                        reason=reason,
                    )
                )

        aloud = [
            f"Cannot price {item.label} ({item.kind}): {item.reason}"
            for item in out_of_scope
        ]
        if not out_of_scope:
            aloud.append(
                "Every holding passed in is inside the AMFI TER scope; the drag "
                "figure covers the full list."
            )

        return ScopeGuardResult(
            in_scope=in_scope, out_of_scope=out_of_scope, aloud=aloud
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        result = ScopeGuardResult.model_validate(raw_result)
        lines = [
            f"In scope ({len(result.in_scope)}):",
        ]
        if result.in_scope:
            lines += [
                f"  - {item.label} [{item.id}]: {item.reason}" for item in result.in_scope
            ]
        else:
            lines.append("  (none)")
        lines += ["", f"Out of scope ({len(result.out_of_scope)}) -- say these aloud:"]
        if result.out_of_scope:
            lines += [
                f"  - {item.label} [{item.id}]: {item.reason}"
                for item in result.out_of_scope
            ]
        else:
            lines.append("  (none)")
        lines += ["", "Say aloud:"] + [f"  {line}" for line in result.aloud]
        return "\n".join(lines)
