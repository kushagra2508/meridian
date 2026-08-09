"""`slip_year` -- how many months past the original date make the target reachable.

Uses `numpy_financial.nper` so the delay is a solved number of periods, not a
guess from the prompt.
"""

from __future__ import annotations

import math
from typing import Any, Type

import numpy_financial as npf
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, field_validator

from .common import (
    CategoryWeight,
    blended_return,
    coerce_allocation,
    validate_allocation,
    weights_to_mapping,
)
from .goal_solver import MONTHS_PER_YEAR, monthly_rate

NPER_SEARCH_CAP_MONTHS = 1200  # 100 years; beyond that the goal is unreachable


class SlipYearInput(BaseModel):
    target_amount: float = Field(gt=0, description="Original corpus needed.")
    years_to_goal: float = Field(gt=0, description="Originally stated years to the goal.")
    current_corpus: float = Field(default=0.0, ge=0)
    monthly_contribution: float = Field(default=0.0, ge=0)
    allocation: list[CategoryWeight] | None = Field(
        default=None,
        description=(
            "Portfolio as [{category, weight_pct}, ...]. Preferred over "
            "expected_annual_return so the tool blends category returns itself."
        ),
    )
    expected_annual_return: float | None = Field(
        default=None,
        description="Fallback decimal return when no allocation is supplied.",
    )

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


class SlipYearResult(BaseModel):
    reachable: bool
    original_months: int
    months_needed: int | None
    delay_months: int = Field(
        description="Months past the original date. 0 when already reachable on time."
    )
    delay_years: float
    new_years_to_goal: float | None
    expected_annual_return: float
    assumptions: list[str]


class SlipYearTool(BaseTool):
    name: str = "slip_year"
    description: str = (
        "Solve how many months the goal date must slip for the original target "
        "to become reachable at today's contribution and expected return. Uses "
        "numpy-financial nper. Pass target_amount, years_to_goal, current_corpus, "
        "monthly_contribution, and allocation (preferred) or expected_annual_return. "
        "Returns delay_months / delay_years; delay is 0 when the plan already lands "
        "on time."
    )
    args_schema: Type[BaseModel] = SlipYearInput

    def _run(
        self,
        target_amount: float,
        years_to_goal: float,
        current_corpus: float = 0.0,
        monthly_contribution: float = 0.0,
        allocation: list[CategoryWeight] | None = None,
        expected_annual_return: float | None = None,
    ) -> SlipYearResult:
        original_months = int(round(years_to_goal * MONTHS_PER_YEAR))
        if original_months < 1:
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

        assumptions = [
            "Monthly compounding; contributions at month end.",
            f"Return basis: {basis}.",
            "Delay is ceil(nper) minus the originally stated months.",
        ]

        # Already funded today -- no periods needed, regardless of nper edge cases.
        if current_corpus >= target_amount:
            return SlipYearResult(
                reachable=True,
                original_months=original_months,
                months_needed=0,
                delay_months=0,
                delay_years=0.0,
                new_years_to_goal=round(original_months / MONTHS_PER_YEAR, 2),
                expected_annual_return=round(expected_return, 6),
                assumptions=assumptions + ["Corpus already meets the target today."],
            )

        if current_corpus <= 0 and monthly_contribution <= 0:
            return SlipYearResult(
                reachable=False,
                original_months=original_months,
                months_needed=None,
                delay_months=NPER_SEARCH_CAP_MONTHS,
                delay_years=round(NPER_SEARCH_CAP_MONTHS / MONTHS_PER_YEAR, 2),
                new_years_to_goal=None,
                expected_annual_return=round(expected_return, 6),
                assumptions=assumptions
                + ["No corpus and no contribution: the target never compounds into reach."],
            )

        rate = monthly_rate(expected_return)
        if monthly_contribution <= 0:
            # nper divides by pmt; with a zero SIP solve from pv * (1+r)^n = fv.
            if current_corpus <= 0:
                months_needed = None
            elif rate <= 0.0:
                months_needed = None
            else:
                raw = math.log(target_amount / current_corpus) / math.log(1.0 + rate)
                months_needed = (
                    None
                    if math.isnan(raw) or math.isinf(raw) or raw < 0
                    else int(math.ceil(raw - 1e-9))
                )
        else:
            try:
                raw = float(
                    npf.nper(rate, -monthly_contribution, -current_corpus, target_amount)
                )
            except (ValueError, FloatingPointError, ZeroDivisionError):
                raw = float("nan")
            if math.isnan(raw) or math.isinf(raw) or raw < 0:
                months_needed = None
            else:
                months_needed = int(math.ceil(raw - 1e-9))

        if months_needed is None or months_needed > NPER_SEARCH_CAP_MONTHS:
            return SlipYearResult(
                reachable=False,
                original_months=original_months,
                months_needed=months_needed,
                delay_months=NPER_SEARCH_CAP_MONTHS,
                delay_years=round(NPER_SEARCH_CAP_MONTHS / MONTHS_PER_YEAR, 2),
                new_years_to_goal=None,
                expected_annual_return=round(expected_return, 6),
                assumptions=assumptions
                + ["nper did not converge inside a 100-year planning horizon."],
            )

        delay = max(0, months_needed - original_months)
        new_years = months_needed / MONTHS_PER_YEAR
        return SlipYearResult(
            reachable=True,
            original_months=original_months,
            months_needed=months_needed,
            delay_months=delay,
            delay_years=round(delay / MONTHS_PER_YEAR, 2),
            new_years_to_goal=round(new_years, 2),
            expected_annual_return=round(expected_return, 6),
            assumptions=assumptions,
        )

    def format_output_for_agent(self, raw_result: object) -> str:
        result = SlipYearResult.model_validate(raw_result)
        if not result.reachable or result.months_needed is None:
            return (
                "Target is not reachable by slipping the date within a 100-year "
                "horizon at the current contribution and return."
            )
        if result.delay_months == 0:
            return (
                f"Already reachable in the original {result.original_months} months "
                f"({result.original_months / MONTHS_PER_YEAR:g} years). Delay: 0."
            )
        return "\n".join(
            [
                f"Original horizon        {result.original_months} months",
                f"Months needed (nper)    {result.months_needed}",
                f"DELAY                   {result.delay_months} months "
                f"({result.delay_years:g} years)",
                f"New years to goal       {result.new_years_to_goal:g}",
                f"Expected return         {result.expected_annual_return * 100:.2f}%",
            ]
        )
