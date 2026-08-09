"""`shrink_target` -- what corpus is actually reachable by the original year.

Uses the same projection as goal_solver (`numpy_financial.fv` when the SIP is
level), so shrink and the feasibility shortfall stay consistent.
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
from .goal_solver import MONTHS_PER_YEAR, project_corpus


class ShrinkTargetInput(BaseModel):
    target_amount: float = Field(gt=0, description="Originally stated target.")
    years_to_goal: float = Field(gt=0)
    current_corpus: float = Field(default=0.0, ge=0)
    monthly_contribution: float = Field(default=0.0, ge=0)
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


class ShrinkTargetResult(BaseModel):
    original_target: float
    reachable_target: float = Field(
        description="Corpus the current plan funds by the original date (fv)."
    )
    shrink_rupees: float = Field(
        description="How much the target must fall. 0 when already funded."
    )
    shrink_pct_of_target: float = Field(description="Decimal of the original target.")
    funded_ratio: float
    months: int
    expected_annual_return: float
    assumptions: list[str]


class ShrinkTargetTool(BaseTool):
    name: str = "shrink_target"
    description: str = (
        "Compute the corpus actually reachable by the originally stated target "
        "year at today's contribution and expected return (numpy-financial fv). "
        "Returns reachable_target and how many rupees the goal must shrink by. "
        "Pass the same plan inputs as goal_solver / slip_year."
    )
    args_schema: Type[BaseModel] = ShrinkTargetInput

    def _run(
        self,
        target_amount: float,
        years_to_goal: float,
        current_corpus: float = 0.0,
        monthly_contribution: float = 0.0,
        allocation: list[CategoryWeight] | None = None,
        expected_annual_return: float | None = None,
        annual_step_up_pct: float = 0.0,
    ) -> ShrinkTargetResult:
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

        reachable = project_corpus(
            expected_return,
            months,
            current_corpus,
            monthly_contribution,
            annual_step_up_pct,
        )
        shrink = max(0.0, target_amount - reachable)
        return ShrinkTargetResult(
            original_target=round(target_amount, 2),
            reachable_target=round(reachable, 2),
            shrink_rupees=round(shrink, 2),
            shrink_pct_of_target=round(shrink / target_amount, 6),
            funded_ratio=round(reachable / target_amount, 4),
            months=months,
            expected_annual_return=round(expected_return, 6),
            assumptions=[
                "Reachable target is the plan's projected corpus at the original date.",
                f"Return basis: {basis}.",
                "Uses numpy-financial fv when the contribution has no step-up.",
            ],
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        result = ShrinkTargetResult.model_validate(raw_result)
        return "\n".join(
            [
                f"Original target         INR {result.original_target:,.0f}",
                f"REACHABLE BY DATE       INR {result.reachable_target:,.0f}",
                f"Must shrink by          INR {result.shrink_rupees:,.0f} "
                f"({result.shrink_pct_of_target * 100:.1f}% of target)",
                f"Funded ratio            {result.funded_ratio * 100:.1f}%",
                f"Horizon                 {result.months} months",
            ]
        )
