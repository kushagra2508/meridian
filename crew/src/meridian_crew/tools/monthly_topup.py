"""`monthly_topup` -- extra SIP that restores the original target and date.

Uses `numpy_financial.pmt` (via goal_solver's contribution solve) so the top-up
matches the same projection maths as feasibility.
"""

from __future__ import annotations

from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from .common import (
    CategoryWeight,
    blended_return,
    coerce_allocation,
    validate_allocation,
    weights_to_mapping,
)
from .goal_solver import MONTHS_PER_YEAR, solve_required_contribution


class MonthlyTopupInput(BaseModel):
    target_amount: float = Field(gt=0)
    years_to_goal: float = Field(gt=0)
    current_corpus: float = Field(default=0.0, ge=0)
    monthly_contribution: float = Field(
        default=0.0, ge=0, description="What the client already contributes."
    )
    allocation: list[CategoryWeight] | None = Field(default=None)
    expected_annual_return: float | None = Field(default=None)
    annual_step_up_pct: float = Field(default=0.0, ge=0)

    @field_validator("allocation", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return coerce_allocation(value)

    @field_validator("expected_annual_return", mode="before")
    @classmethod
    def _as_decimal(cls, value: Any) -> Any:
        if isinstance(value, (int, float)) and value > 1.0:
            return float(value) / 100.0
        return value


class MonthlyTopupResult(BaseModel):
    current_monthly_contribution: float
    required_monthly_contribution: float | None
    additional_monthly_contribution: float | None = Field(
        description="Extra rupees per month on top of today's SIP. 0 when funded."
    )
    months: int
    expected_annual_return: float
    already_funded: bool
    assumptions: list[str]


class MonthlyTopupTool(BaseTool):
    name: str = "monthly_topup"
    description: str = (
        "Solve the additional monthly contribution needed to hit both the "
        "original target amount and the original target date at the expected "
        "return (numpy-financial pmt). Returns additional_monthly_contribution "
        "-- how much more per month than the client pays today."
    )
    args_schema: Type[BaseModel] = MonthlyTopupInput

    def _run(
        self,
        target_amount: float,
        years_to_goal: float,
        current_corpus: float = 0.0,
        monthly_contribution: float = 0.0,
        allocation: list[CategoryWeight] | None = None,
        expected_annual_return: float | None = None,
        annual_step_up_pct: float = 0.0,
    ) -> MonthlyTopupResult:
        months = int(round(years_to_goal * MONTHS_PER_YEAR))
        if months < 1:
            raise ValueError("years_to_goal must be at least one month.")

        if allocation is not None:
            weights = validate_allocation(weights_to_mapping(allocation))
            expected_return = blended_return(weights)
            basis = "allocation-blended forward return"
        else:
            if expected_annual_return is None:
                raise ValueError(
                    "Provide either `allocation` or `expected_annual_return`."
                )
            expected_return = float(expected_annual_return)
            basis = "caller-supplied expected_annual_return"

        required = solve_required_contribution(
            target_amount,
            months,
            current_corpus,
            expected_return,
            annual_step_up_pct,
        )
        if required is None:
            return MonthlyTopupResult(
                current_monthly_contribution=round(monthly_contribution, 2),
                required_monthly_contribution=None,
                additional_monthly_contribution=None,
                months=months,
                expected_annual_return=round(expected_return, 6),
                already_funded=False,
                assumptions=[
                    f"Return basis: {basis}.",
                    "Contribution solve failed; no finite SIP closes this gap.",
                ],
            )

        additional = max(0.0, required - monthly_contribution)
        return MonthlyTopupResult(
            current_monthly_contribution=round(monthly_contribution, 2),
            required_monthly_contribution=round(required, 2),
            additional_monthly_contribution=round(additional, 2),
            months=months,
            expected_annual_return=round(expected_return, 6),
            already_funded=additional <= 0.0,
            assumptions=[
                f"Return basis: {basis}.",
                "Uses numpy-financial pmt when the contribution has no step-up.",
                "Additional is required monthly minus the client's current SIP.",
            ],
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        result = MonthlyTopupResult.model_validate(raw_result)
        if result.additional_monthly_contribution is None:
            return "No finite monthly contribution closes this gap at the expected return."
        if result.already_funded:
            return (
                f"Already funded at INR {result.current_monthly_contribution:,.0f}/mo. "
                "Top-up needed: INR 0."
            )
        return "\n".join(
            [
                f"Current SIP             INR {result.current_monthly_contribution:,.0f}/mo",
                f"Required SIP (pmt)      INR {result.required_monthly_contribution:,.0f}/mo",
                f"ADDITIONAL TOP-UP       INR {result.additional_monthly_contribution:,.0f}/mo",
                f"Horizon                 {result.months} months",
                f"Expected return         {result.expected_annual_return * 100:.2f}%",
            ]
        )
