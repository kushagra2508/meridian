"""`horizon_filter` -- rules out products whose lock-in outlives the goal year.

The hard test is contractual: if capital cannot be withdrawn before the client
needs it, the product is out, however good its return looks. Two softer signals
are reported separately rather than folded into the exclusion, because they cost
money or comfort without making the product unusable: exit loads, and a
volatility profile that wants a longer runway than the goal allows.
"""

from __future__ import annotations

from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from ..datasets import products

MONTHS_PER_YEAR = 12


class HorizonFilterInput(BaseModel):
    years_to_goal: float = Field(
        gt=0, description="Years until the money is needed. Fractions are fine."
    )
    client_age: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Needed to evaluate age-locked products such as NPS Tier I or EPF. "
            "Without it those products are excluded as unevaluable."
        ),
    )
    product_ids: list[str] | None = Field(
        default=None,
        description="Restrict the check to these product ids. Omit to screen the catalogue.",
    )

    @field_validator("product_ids", mode="before")
    @classmethod
    def _split_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


class ProductVerdict(BaseModel):
    id: str
    name: str
    kind: str
    category: str | None = Field(
        description="nav_history category key, when the product maps to one."
    )
    lockup_years: float | None
    reason: str


class HorizonFilterResult(BaseModel):
    years_to_goal: float
    eligible: list[ProductVerdict]
    excluded: list[ProductVerdict]
    advisories: list[str] = Field(
        description="Soft warnings: exit loads and suitability, not disqualifications."
    )
    eligible_categories: list[str] = Field(
        description="Pass straight into reallocation_search's eligible_categories."
    )


def effective_lockup(product: dict[str, Any], client_age: int | None) -> float | None:
    """Years of hard lock-in for this client. None when it cannot be determined."""
    unlock_age = product.get("unlock_age")
    if unlock_age is not None:
        if client_age is None:
            return None
        return max(0.0, float(unlock_age - client_age))
    return float(product.get("lockup_years") or 0.0)


class HorizonFilterTool(BaseTool):
    name: str = "horizon_filter"
    description: str = (
        "Screen the product catalogue against a goal date and rule out anything "
        "whose lock-in outlives it -- ELSS at 3 years, a tax-saving FD at 5, PPF at "
        "15, and age-locked products like NPS Tier I. Give it years_to_goal and, "
        "for the age-locked products, client_age. Returns eligible products, "
        "excluded products with the reason, soft advisories about exit loads and "
        "suitability, and an `eligible_categories` list to feed straight into "
        "reallocation_search. Run this before recommending any product."
    )
    args_schema: Type[BaseModel] = HorizonFilterInput

    def _run(
        self,
        years_to_goal: float,
        client_age: int | None = None,
        product_ids: list[str] | None = None,
    ) -> HorizonFilterResult:
        catalogue = products()
        if product_ids:
            index = {product["id"]: product for product in catalogue}
            unknown = [pid for pid in product_ids if pid not in index]
            if unknown:
                raise ValueError(
                    f"Unknown product ids {unknown}. Valid ids are: "
                    f"{', '.join(sorted(index))}."
                )
            catalogue = [index[pid] for pid in product_ids]

        eligible: list[ProductVerdict] = []
        excluded: list[ProductVerdict] = []
        advisories: list[str] = []

        for product in catalogue:
            lockup = effective_lockup(product, client_age)
            base = {
                "id": product["id"],
                "name": product["name"],
                "kind": product["kind"],
                "category": product.get("category"),
                "lockup_years": lockup,
            }

            if lockup is None:
                excluded.append(
                    ProductVerdict(
                        **base,
                        reason=(
                            f"Unlocks at age {product['unlock_age']}; client_age was "
                            "not supplied so eligibility cannot be established."
                        ),
                    )
                )
                continue

            if lockup > years_to_goal:
                unlock_age = product.get("unlock_age")
                detail = (
                    f"unlocks at age {unlock_age}, which is {lockup:g} years away"
                    if unlock_age is not None
                    else f"{lockup:g}-year lock-in"
                )
                excluded.append(
                    ProductVerdict(
                        **base,
                        reason=(
                            f"{detail} outlives the {years_to_goal:g}-year goal. "
                            f"{product['basis']}"
                        ),
                    )
                )
                continue

            eligible.append(
                ProductVerdict(
                    **base,
                    reason=(
                        f"{lockup:g}-year lock-in clears the {years_to_goal:g}-year goal."
                        if lockup
                        else "No lock-in."
                    ),
                )
            )

            exit_load_years = float(product.get("exit_load_months") or 0) / MONTHS_PER_YEAR
            if exit_load_years > years_to_goal:
                advisories.append(
                    f"{product['name']}: exit load applies for "
                    f"{product['exit_load_months']:g} months, longer than the goal "
                    "itself, so redemption will cost a fee."
                )
            minimum = float(product.get("min_recommended_years") or 0)
            if minimum > years_to_goal:
                advisories.append(
                    f"{product['name']}: withdrawable in time, but suits a "
                    f"{minimum:g}-year horizon. Over {years_to_goal:g} years a bad "
                    "sequence of returns may not have recovered."
                )

        # Only categories that are both eligible and suitable are worth handing to
        # the reallocation search; a fund that can lose 20% two years before the
        # goal is eligible on paper and wrong in practice.
        suitable_categories = {
            product["category"]
            for product in catalogue
            if product.get("category")
            and any(verdict.id == product["id"] for verdict in eligible)
            and float(product.get("min_recommended_years") or 0) <= years_to_goal
        }

        return HorizonFilterResult(
            years_to_goal=years_to_goal,
            eligible=eligible,
            excluded=excluded,
            advisories=advisories,
            eligible_categories=sorted(suitable_categories),
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        result = HorizonFilterResult.model_validate(raw_result)
        lines = [f"Horizon screen for a {result.years_to_goal:g}-year goal.", "", "ELIGIBLE:"]
        lines += [f"  {v.name} ({v.id}) - {v.reason}" for v in result.eligible] or [
            "  none"
        ]
        lines += ["", "EXCLUDED:"]
        lines += [f"  {v.name} ({v.id}) - {v.reason}" for v in result.excluded] or [
            "  none"
        ]
        if result.advisories:
            lines += ["", "ADVISORIES (not disqualifying):"]
            lines += [f"  {note}" for note in result.advisories]
        lines += [
            "",
            "eligible_categories (pass to reallocation_search): "
            + (", ".join(result.eligible_categories) or "none"),
        ]
        return "\n".join(lines)
