"""`reallocation_search` -- the smallest allocation shift that closes the gap.

"Smallest" is measured as total percentage points of the portfolio moved. The
search is greedy: repeatedly move a small slice from the lowest-returning holding
into the highest-returning eligible category. Because each step buys the most
return per point moved, the greedy path is also the cheapest one.
"""

from __future__ import annotations

from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from ..datasets import categories, forward_returns
from .common import (
    AssetClassCap,
    CategoryWeight,
    asset_class_weights,
    blended_return,
    blended_volatility_upper_bound,
    caps_to_mapping,
    coerce_allocation,
    coerce_caps,
    validate_allocation,
    weights_to_mapping,
)

# Guardrail so the search cannot answer "put everything in whatever ran hottest".
DEFAULT_MAX_WEIGHT_PER_CATEGORY = 40.0
DEFAULT_STEP_PCT = 1.0
RETURN_TOLERANCE = 1e-9

# Asset-class ceilings, in percent of the portfolio.
#
# Commodity is capped because a greedy return search would otherwise load up on
# gold: its trailing five-year CAGR is the highest number in the dataset, and no
# return haircut large enough to change that would be honest about the data.
# Capping the weight is the truthful version of the same judgement -- gold is a
# diversifier held in single digits, not a growth engine -- and it leaves the
# measured returns untouched. Override per call when a mandate says otherwise.
DEFAULT_ASSET_CLASS_CAPS: dict[str, float] = {"commodity": 10.0}


class ReallocationSearchInput(BaseModel):
    current_allocation: list[CategoryWeight] = Field(
        description=(
            "Today's portfolio as a list of {category, weight_pct} objects, e.g. "
            '[{"category": "equity_large_cap", "weight_pct": 60}, '
            '{"category": "debt_liquid", "weight_pct": 40}]. Must sum to 100.'
        )
    )
    required_annual_return: float = Field(
        description="Target return as a decimal. Take this from goal_solver."
    )
    eligible_categories: list[str] | None = Field(
        default=None,
        description=(
            "Categories the money may move into. Pass horizon_filter's "
            "`eligible_categories` so the search cannot suggest something the goal "
            "date rules out. Omit to allow every category."
        ),
    )
    max_shift_pct: float = Field(
        default=100.0,
        gt=0,
        le=100,
        description="Cap on the total percentage points moved.",
    )
    max_equity_pct: float | None = Field(
        default=None,
        description="Optional ceiling on total equity weight, in percent.",
    )
    max_asset_class_pct: list[AssetClassCap] | None = Field(
        default=None,
        description=(
            "Ceilings per asset class as a list of {asset_class, max_pct} objects, "
            'e.g. [{"asset_class": "equity", "max_pct": 60}]. Merged over the '
            "default commodity cap of 10%."
        ),
    )
    locked_categories: list[str] | None = Field(
        default=None,
        description="Categories that must not be reduced, e.g. an ELSS position mid-lock-in.",
    )

    @field_validator("current_allocation", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return coerce_allocation(value)

    @field_validator("max_asset_class_pct", mode="before")
    @classmethod
    def _coerce_caps(cls, value: Any) -> Any:
        return coerce_caps(value)

    @field_validator("required_annual_return", mode="before")
    @classmethod
    def _as_decimal(cls, value: Any) -> Any:
        if isinstance(value, (int, float)) and value > 1.0:
            return float(value) / 100.0
        return value

    @field_validator("eligible_categories", "locked_categories", mode="before")
    @classmethod
    def _split_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


class Move(BaseModel):
    from_category: str
    to_category: str
    weight_pct: float


class ReallocationSearchResult(BaseModel):
    feasible: bool
    required_annual_return: float
    return_before: float
    return_after: float
    residual_return_gap: float = Field(
        description="required_annual_return less return_after; 0 when feasible."
    )
    total_shift_pct: float = Field(description="Percentage points of the portfolio moved.")
    moves: list[Move]
    allocation_before: dict[str, float]
    allocation_after: dict[str, float]
    volatility_before_upper_bound: float
    volatility_after_upper_bound: float
    equity_weight_before: float
    equity_weight_after: float
    asset_class_weights_after: dict[str, float]
    caps_applied: dict[str, float] = Field(
        description="Asset-class ceilings the search respected, in percent."
    )
    binding_constraint: str | None
    notes: list[str]


class ReallocationSearchTool(BaseTool):
    name: str = "reallocation_search"
    description: str = (
        "Find the smallest allocation change that lifts a portfolio's blended "
        "return up to a required return. Give it the current allocation (percent "
        "weights by category key) and the `required_annual_return` from "
        "goal_solver. Pass horizon_filter's `eligible_categories` to keep the "
        "search inside products the goal date allows, and use max_equity_pct, "
        "max_asset_class_pct or locked_categories for the client's own risk and "
        "lock-in constraints. Per-category concentration limits are house policy "
        "and are applied automatically. Returns the moves, the "
        "total percentage points shifted, and the resulting return and volatility. "
        "If it comes back infeasible, no allocation reaches the goal and the "
        "contribution or the timeline has to change instead."
    )
    args_schema: Type[BaseModel] = ReallocationSearchInput

    # Configuration, not arguments. A live run had gpt-5-mini pass
    # max_weight_per_category=100 as if that were the default, quietly switching
    # off the concentration limit. House policy is not the model's to choose, so
    # it is set when the tool is constructed and never advertised in the schema.
    max_weight_per_category: float = DEFAULT_MAX_WEIGHT_PER_CATEGORY
    step_pct: float = DEFAULT_STEP_PCT

    def _run(
        self,
        current_allocation: list[CategoryWeight],
        required_annual_return: float,
        eligible_categories: list[str] | None = None,
        max_shift_pct: float = 100.0,
        max_equity_pct: float | None = None,
        max_asset_class_pct: list[AssetClassCap] | None = None,
        locked_categories: list[str] | None = None,
    ) -> ReallocationSearchResult:
        max_weight_per_category = self.max_weight_per_category
        step_pct = self.step_pct
        table = categories()
        returns = forward_returns()
        before = validate_allocation(weights_to_mapping(current_allocation))

        universe = list(table) if not eligible_categories else list(eligible_categories)
        unknown = [key for key in universe if key not in table]
        if unknown:
            raise ValueError(
                f"Unknown categories {unknown}. Valid keys are: "
                f"{', '.join(sorted(table))}."
            )
        locked = set(locked_categories or [])

        notes: list[str] = []

        def cap_for(key: str) -> float:
            """Per-category ceiling.

            A category already held above the cap is grandfathered rather than
            forcibly trimmed -- the job is to close a return gap, not to
            rebalance uninvited. The allowance is per category, so a category
            that starts under the cap can never be topped up past it.
            """
            return max(max_weight_per_category, before.get(key, 0.0))

        over_cap = [key for key in before if before[key] > max_weight_per_category]
        if over_cap:
            notes.append(
                f"Already above the {max_weight_per_category:g}% per-category cap and "
                f"left untrimmed: {', '.join(sorted(over_cap))}."
            )

        class_caps = dict(DEFAULT_ASSET_CLASS_CAPS)
        class_caps.update(caps_to_mapping(max_asset_class_pct))
        if max_equity_pct is not None:
            class_caps["equity"] = max_equity_pct

        working = dict(before)
        for key in universe:
            working.setdefault(key, 0.0)

        return_before = blended_return(before)
        moves: dict[tuple[str, str], float] = {}
        moved_total = 0.0
        binding: str | None = None

        def held(allocation: dict[str, float]) -> dict[str, float]:
            return {key: value for key, value in allocation.items() if value > 0}

        def class_weight(allocation: dict[str, float], asset_class: str) -> float:
            return asset_class_weights(held(allocation)).get(asset_class, 0.0)

        while blended_return(working) < required_annual_return - RETURN_TOLERANCE:
            if moved_total >= max_shift_pct - RETURN_TOLERANCE:
                binding = f"max_shift_pct of {max_shift_pct:g}% reached"
                break

            donors = sorted(
                (key for key, weight in working.items() if weight > 0 and key not in locked),
                key=lambda key: returns[key],
            )
            chosen: tuple[str, str, float] | None = None
            blocked: str | None = None

            # Best receiver first, cheapest donor first: each step buys the most
            # return per percentage point moved, which is what makes the greedy
            # path also the smallest one.
            for receiver in sorted(universe, key=lambda key: -returns[key]):
                receiver_class = table[receiver]["asset_class"]
                category_headroom = cap_for(receiver) - working.get(receiver, 0.0)
                if category_headroom <= RETURN_TOLERANCE:
                    blocked = blocked or (
                        f"{receiver} is at its {cap_for(receiver):g}% per-category cap"
                    )
                    continue

                for donor in donors:
                    if returns[donor] >= returns[receiver]:
                        break  # donors ascend by return; none later will help either
                    headroom = min(category_headroom, working[donor])
                    # Moving inside an asset class leaves its weight untouched.
                    if table[donor]["asset_class"] != receiver_class:
                        cap = class_caps.get(receiver_class)
                        if cap is not None:
                            class_headroom = cap - class_weight(working, receiver_class)
                            if class_headroom <= RETURN_TOLERANCE:
                                blocked = blocked or (
                                    f"{receiver_class} is at its {cap:g}% cap"
                                )
                                headroom = 0.0
                            else:
                                headroom = min(headroom, class_headroom)
                    amount = min(step_pct, headroom, max_shift_pct - moved_total)
                    if amount > RETURN_TOLERANCE:
                        chosen = (donor, receiver, amount)
                        break
                if chosen:
                    break

            if chosen is None:
                binding = blocked or (
                    "every remaining holding already earns at least as much as any "
                    "eligible category it could move into"
                )
                break

            donor, receiver, amount = chosen
            working[donor] -= amount
            working[receiver] = working.get(receiver, 0.0) + amount
            moves[(donor, receiver)] = moves.get((donor, receiver), 0.0) + amount
            moved_total += amount

        after = {key: round(weight, 4) for key, weight in working.items() if weight > 0}
        return_after = blended_return(working)
        feasible = return_after >= required_annual_return - RETURN_TOLERANCE

        if feasible:
            binding = None
            if not moves:
                notes.append(
                    "The current allocation already meets the required return; no "
                    "change is needed."
                )
        else:
            notes.append(
                "No allocation within these constraints reaches the required return. "
                "The remaining levers are a higher contribution, a later goal date, "
                "or a smaller target."
            )

        return ReallocationSearchResult(
            feasible=feasible,
            required_annual_return=round(required_annual_return, 6),
            return_before=round(return_before, 6),
            return_after=round(return_after, 6),
            residual_return_gap=round(
                max(0.0, required_annual_return - return_after), 6
            ),
            total_shift_pct=round(moved_total, 4),
            moves=[
                Move(
                    from_category=donor,
                    to_category=receiver,
                    weight_pct=round(amount, 4),
                )
                for (donor, receiver), amount in sorted(
                    moves.items(), key=lambda item: -item[1]
                )
            ],
            allocation_before=before,
            allocation_after=after,
            volatility_before_upper_bound=round(
                blended_volatility_upper_bound(before), 6
            ),
            volatility_after_upper_bound=round(
                blended_volatility_upper_bound(after), 6
            ),
            equity_weight_before=round(class_weight(before, "equity"), 4),
            equity_weight_after=round(class_weight(after, "equity"), 4),
            asset_class_weights_after={
                key: round(value, 4)
                for key, value in asset_class_weights(held(after)).items()
            },
            caps_applied={key: float(value) for key, value in sorted(class_caps.items())},
            binding_constraint=binding,
            notes=notes
            + [
                "Volatility figures are upper bounds: they assume the categories "
                "move together. The real blended figure is lower."
            ],
        )
