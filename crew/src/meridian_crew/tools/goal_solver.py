"""`goal_solver` -- projects wealth to the target year and solves the gap.

Three questions, one tool: what will this plan be worth, how far short is it,
and what return (or contribution) would close the difference. The projection
maths lives here rather than in the prompt so the numbers are reproducible.
"""

from __future__ import annotations

import math
from typing import Any, Type

import numpy_financial as npf
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator, model_validator

from .common import (
    CategoryWeight,
    blended_return,
    blended_volatility_upper_bound,
    coerce_allocation,
    validate_allocation,
    weights_to_mapping,
)

MONTHS_PER_YEAR = 12

# Bisection bounds for the required-return solve. Nothing outside this band is a
# planning answer; it is a signal that the goal needs a different lever.
RATE_SEARCH_LOW = -0.90
RATE_SEARCH_HIGH = 2.00
RATE_SEARCH_ITERATIONS = 200
SOLVE_TOLERANCE = 1e-6

# Within this fraction of the target the plan is called on track rather than
# short by a rounding error.
ON_TRACK_TOLERANCE = 1e-4


def monthly_rate(annual_rate: float) -> float:
    """Monthly rate that compounds to `annual_rate` over twelve months."""
    return (1.0 + annual_rate) ** (1.0 / MONTHS_PER_YEAR) - 1.0


def project_corpus(
    annual_rate: float,
    months: int,
    current_corpus: float,
    monthly_contribution: float,
    annual_step_up_pct: float = 0.0,
) -> float:
    """Future value of a lump sum plus a monthly contribution stream.

    With no step-up this is `numpy_financial.fv`. With a step-up the stream is a
    growing annuity, which `fv` cannot express, so the months are walked
    directly and the contribution is raised on each anniversary.
    """
    rate = monthly_rate(annual_rate)

    if annual_step_up_pct == 0.0:
        if rate == 0.0:
            # numpy_financial evaluates its annuity factor before selecting the
            # zero-rate branch, which divides by zero and warns. The answer at a
            # flat zero return is just the money paid in.
            return current_corpus + monthly_contribution * months
        return float(npf.fv(rate, months, -monthly_contribution, -current_corpus))

    balance = current_corpus
    contribution = monthly_contribution
    for month in range(months):
        if month > 0 and month % MONTHS_PER_YEAR == 0:
            contribution *= 1.0 + annual_step_up_pct / 100.0
        balance = balance * (1.0 + rate) + contribution
    return balance


def total_contributed(
    months: int, monthly_contribution: float, annual_step_up_pct: float = 0.0
) -> float:
    if annual_step_up_pct == 0.0:
        return monthly_contribution * months
    total = 0.0
    contribution = monthly_contribution
    for month in range(months):
        if month > 0 and month % MONTHS_PER_YEAR == 0:
            contribution *= 1.0 + annual_step_up_pct / 100.0
        total += contribution
    return total


def _bisect(fn, low: float, high: float) -> float | None:
    """Root of a monotonically increasing `fn` on [low, high]."""
    f_low, f_high = fn(low), fn(high)
    if f_low > 0 or f_high < 0:
        return None
    for _ in range(RATE_SEARCH_ITERATIONS):
        mid = (low + high) / 2.0
        value = fn(mid)
        if abs(value) < SOLVE_TOLERANCE:
            return mid
        if value < 0:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def solve_required_return(
    target_amount: float,
    months: int,
    current_corpus: float,
    monthly_contribution: float,
    annual_step_up_pct: float = 0.0,
) -> float | None:
    """Annual return at which the plan lands exactly on the target.

    `numpy_financial.rate` answers this directly for a level contribution, but
    it is a Newton solve that can return NaN, so the answer is always checked by
    re-projecting and falls back to bisection when it does not hold up.
    """
    if current_corpus <= 0 and monthly_contribution <= 0:
        return None

    def error(annual_rate: float) -> float:
        return (
            project_corpus(
                annual_rate,
                months,
                current_corpus,
                monthly_contribution,
                annual_step_up_pct,
            )
            - target_amount
        )

    if annual_step_up_pct == 0.0:
        candidate = npf.rate(
            months, -monthly_contribution, -current_corpus, target_amount
        )
        if candidate is not None and not math.isnan(float(candidate)):
            annual = (1.0 + float(candidate)) ** MONTHS_PER_YEAR - 1.0
            if abs(error(annual)) <= max(1.0, target_amount * ON_TRACK_TOLERANCE):
                return annual

    return _bisect(error, RATE_SEARCH_LOW, RATE_SEARCH_HIGH)


def solve_required_contribution(
    target_amount: float,
    months: int,
    current_corpus: float,
    annual_rate: float,
    annual_step_up_pct: float = 0.0,
) -> float | None:
    """Monthly contribution that reaches the target at the given return."""
    if annual_step_up_pct == 0.0:
        rate = monthly_rate(annual_rate)
        payment = float(npf.pmt(rate, months, -current_corpus, target_amount))
        return max(0.0, -payment)

    def error(contribution: float) -> float:
        return (
            project_corpus(
                annual_rate, months, current_corpus, contribution, annual_step_up_pct
            )
            - target_amount
        )

    if error(0.0) >= 0:
        return 0.0
    high = max(target_amount / months, 1.0)
    while error(high) < 0 and high < target_amount * 10:
        high *= 2.0
    return _bisect(error, 0.0, high)


class GoalSolverInput(BaseModel):
    target_amount: float = Field(gt=0, description="Corpus needed at the goal date.")
    years_to_goal: float = Field(gt=0, description="Years until the money is needed.")
    current_corpus: float = Field(default=0.0, ge=0, description="Invested today.")
    monthly_contribution: float = Field(
        default=0.0, ge=0, description="Recurring monthly investment."
    )
    allocation: list[CategoryWeight] | None = Field(
        default=None,
        description=(
            "The portfolio as a list of {category, weight_pct} objects, e.g. "
            '[{"category": "equity_large_cap", "weight_pct": 60}, '
            '{"category": "debt_short_duration", "weight_pct": 40}]. Weights are '
            "percentages and must sum to 100. Preferred over "
            "expected_annual_return: the blended return is computed here from the "
            "NAV snapshot, so you do not have to do the arithmetic."
        ),
    )
    expected_annual_return: float | None = Field(
        default=None,
        description=(
            "Fallback when no allocation is known. Decimal, so 0.11 means 11%."
        ),
    )
    annual_step_up_pct: float = Field(
        default=0.0,
        ge=0,
        description="Annual increase in the monthly contribution, in percent.",
    )

    @field_validator("allocation", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return coerce_allocation(value)

    @field_validator("expected_annual_return", mode="before")
    @classmethod
    def _as_decimal(cls, value: Any) -> Any:
        # A return above 1.0 was meant as a percentage. 100%+ is not a planning input.
        if isinstance(value, (int, float)) and value > 1.0:
            return float(value) / 100.0
        return value

    @model_validator(mode="after")
    def _need_a_return(self) -> GoalSolverInput:
        if not self.allocation and self.expected_annual_return is None:
            raise ValueError(
                "Provide either `allocation` (preferred) or `expected_annual_return`."
            )
        return self


class GoalSolverResult(BaseModel):
    on_track: bool
    months: int
    expected_annual_return: float
    return_basis: str
    projected_corpus: float
    target_amount: float
    funded_ratio: float = Field(description="projected_corpus / target_amount")
    shortfall: float = Field(description="0 when the plan already reaches the target.")
    surplus: float = Field(description="0 when the plan falls short.")
    total_contributions: float
    growth_component: float = Field(
        description="projected_corpus less corpus and contributions."
    )
    required_annual_return: float | None = Field(
        description="Return that lands exactly on target. None when already on track."
    )
    required_return_gap: float | None = Field(
        description="required_annual_return less expected_annual_return."
    )
    required_monthly_contribution: float | None = Field(
        description="Monthly investment that reaches the target at the expected return."
    )
    additional_monthly_contribution: float | None = Field(
        description="How much more per month than the client contributes today."
    )
    portfolio_volatility_upper_bound: float | None = None
    assumptions: list[str]


class GoalSolverTool(BaseTool):
    name: str = "goal_solver"
    description: str = (
        "Project a client's wealth to the goal year, measure the shortfall, and "
        "solve for the return (and the contribution) that would close it. Give it "
        "the target amount, years to the goal, current corpus, monthly "
        "contribution, and the portfolio `allocation` by category key -- it looks "
        "up and blends the category returns itself, so never pre-compute a blended "
        "return by hand. Returns decimals for rates (0.11 means 11%). Use this "
        "before reallocation_search: its `required_annual_return` is that tool's input."
    )
    args_schema: Type[BaseModel] = GoalSolverInput

    def _run(
        self,
        target_amount: float,
        years_to_goal: float,
        current_corpus: float = 0.0,
        monthly_contribution: float = 0.0,
        allocation: list[CategoryWeight] | None = None,
        expected_annual_return: float | None = None,
        annual_step_up_pct: float = 0.0,
    ) -> GoalSolverResult:
        months = int(round(years_to_goal * MONTHS_PER_YEAR))
        if months < 1:
            raise ValueError("years_to_goal must be at least one month.")

        assumptions = [
            "Monthly compounding; contributions invested at the end of each month.",
            "Returns are nominal and gross of tax and exit loads.",
        ]

        volatility: float | None = None
        if allocation is not None:
            weights = validate_allocation(weights_to_mapping(allocation))
            expected_return = blended_return(weights)
            volatility = blended_volatility_upper_bound(weights)
            basis = (
                "weight-average of the haircut-adjusted forward returns for "
                + ", ".join(f"{key} {weight:g}%" for key, weight in weights.items())
            )
        else:
            expected_return = float(expected_annual_return)  # type: ignore[arg-type]
            basis = "caller-supplied expected_annual_return"

        if annual_step_up_pct:
            assumptions.append(
                f"Monthly contribution rises {annual_step_up_pct:g}% every 12 months."
            )

        projected = project_corpus(
            expected_return,
            months,
            current_corpus,
            monthly_contribution,
            annual_step_up_pct,
        )
        contributions = total_contributed(
            months, monthly_contribution, annual_step_up_pct
        )
        difference = projected - target_amount
        on_track = difference >= -target_amount * ON_TRACK_TOLERANCE

        required_return: float | None = None
        required_gap: float | None = None
        if not on_track:
            required_return = solve_required_return(
                target_amount,
                months,
                current_corpus,
                monthly_contribution,
                annual_step_up_pct,
            )
            if required_return is not None:
                required_gap = required_return - expected_return
            else:
                assumptions.append(
                    "No return closes this gap: there is no corpus and no "
                    "contribution to compound."
                )

        required_contribution = solve_required_contribution(
            target_amount, months, current_corpus, expected_return, annual_step_up_pct
        )
        additional = (
            None
            if required_contribution is None
            else max(0.0, required_contribution - monthly_contribution)
        )

        return GoalSolverResult(
            on_track=on_track,
            months=months,
            expected_annual_return=round(expected_return, 6),
            return_basis=basis,
            projected_corpus=round(projected, 2),
            target_amount=round(target_amount, 2),
            funded_ratio=round(projected / target_amount, 4),
            shortfall=round(max(0.0, -difference), 2),
            surplus=round(max(0.0, difference), 2),
            total_contributions=round(contributions, 2),
            growth_component=round(projected - current_corpus - contributions, 2),
            required_annual_return=(
                None if required_return is None else round(required_return, 6)
            ),
            required_return_gap=(
                None if required_gap is None else round(required_gap, 6)
            ),
            required_monthly_contribution=(
                None if required_contribution is None else round(required_contribution, 2)
            ),
            additional_monthly_contribution=(
                None if additional is None else round(additional, 2)
            ),
            portfolio_volatility_upper_bound=(
                None if volatility is None else round(volatility, 6)
            ),
            assumptions=assumptions,
        )
