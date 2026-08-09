"""The Reframe agent: three levers when the original plan misses the target."""

from __future__ import annotations

import json
from typing import Any, Literal

from crewai import Agent, Task
from pydantic import BaseModel, Field, field_validator

from .agent import build_llm
from .tools import reframe_tools
from .tools.common import coerce_allocation_to_mapping, validate_allocation
from .tools.drag_calc import HoldingLine, coerce_holdings

ROLE = "Goal Reframe Analyst"

GOAL = (
    "When the original target and date do not clear, quantify the three honest "
    "levers -- slip the year, shrink the target, or top up the monthly -- and "
    "price each path through Statute and Channel before recommending one."
)

BACKSTORY = (
    "You sit after Feasibility has named a shortfall. Clients hate being told "
    "'try harder' without numbers, so you never paraphrase a lever: you solve "
    "it. Slip the date with nper. Shrink the target with fv. Top up the SIP "
    "with pmt. Then you hand each option back through the same tax and TER "
    "stack Statute and Channel already ran, because a cheaper-looking SIP that "
    "ignores friction is a fiction.\n\n"
    "You work in a fixed order. Solve the three levers. Price them. Prefer the "
    "path whose all-in friction the client can actually live with. You never "
    "invent a month or a rupee -- every figure came from a tool."
)

PreferredLever = Literal["slip_year", "shrink_target", "monthly_topup", "none"]


class ReframeBrief(BaseModel):
    """Plan inputs plus upstream context the Reframe agent needs."""

    goal: str
    target_amount: float = Field(gt=0)
    years_to_goal: float = Field(gt=0)
    current_corpus: float = Field(default=0.0, ge=0)
    monthly_contribution: float = Field(default=0.0, ge=0)
    allocation: dict[str, float]
    portfolio_value: float = Field(gt=0)
    holdings: list[HoldingLine] = Field(default_factory=list)
    disposals: list[dict[str, Any]] = Field(default_factory=list)
    other_taxable_income: float = Field(default=1_200_000.0, ge=0)
    regime: Literal["new", "old"] = "new"
    age_band: Literal["below_60", "60_to_80", "80_plus"] = "below_60"
    shortfall: float | None = Field(default=None)
    feasibility_verdict: str | None = None
    statute_tax: float | None = None
    channel_annual_drag: float | None = None
    currency: str = "INR"
    annual_step_up_pct: float = 0.0
    notes: str | None = None

    @field_validator("allocation", mode="before")
    @classmethod
    def _coerce_alloc(cls, value: Any) -> Any:
        return coerce_allocation_to_mapping(value)

    @field_validator("allocation")
    @classmethod
    def _validate_alloc(cls, value: dict[str, float]) -> dict[str, float]:
        return validate_allocation(value)

    @field_validator("holdings", mode="before")
    @classmethod
    def _coerce_holdings(cls, value: Any) -> Any:
        return coerce_holdings(value) or []

    def allocation_argument(self) -> str:
        return json.dumps(
            [
                {"category": key, "weight_pct": weight}
                for key, weight in self.allocation.items()
            ]
        )

    def holdings_argument(self) -> str:
        return json.dumps(
            [
                h.model_dump() if hasattr(h, "model_dump") else h
                for h in self.holdings
            ]
        )

    def disposals_argument(self) -> str:
        return json.dumps(self.disposals)

    def as_prompt_block(self) -> str:
        lines = [
            f"Goal: {self.goal}",
            f"Original target: {self.currency} {self.target_amount:,.0f}",
            f"Original years: {self.years_to_goal:g}",
            f"Invested today: {self.currency} {self.current_corpus:,.0f}",
            f"Monthly contribution: {self.currency} {self.monthly_contribution:,.0f}",
            f"Portfolio value for Channel: {self.currency} {self.portfolio_value:,.0f}",
            "Allocation to pass verbatim:\n" + self.allocation_argument(),
            "Holdings to pass verbatim:\n" + self.holdings_argument(),
            "Disposals to pass verbatim into price_options:\n"
            + self.disposals_argument(),
            f"other_taxable_income: {self.other_taxable_income:,.0f}",
            f"regime: {self.regime}; age_band: {self.age_band}",
        ]
        if self.shortfall is not None:
            lines.append(f"Feasibility shortfall: {self.currency} {self.shortfall:,.0f}")
        if self.feasibility_verdict:
            lines.append(f"Feasibility verdict: {self.feasibility_verdict}")
        if self.statute_tax is not None:
            lines.append(f"Upstream Statute tax: {self.currency} {self.statute_tax:,.0f}")
        if self.channel_annual_drag is not None:
            lines.append(
                f"Upstream Channel annual drag: {self.currency} "
                f"{self.channel_annual_drag:,.0f}"
            )
        if self.notes:
            lines.append(f"Adviser notes: {self.notes}")
        return "\n".join(lines)


class LeverQuote(BaseModel):
    kind: PreferredLever
    summary: str
    target_amount: float | None = None
    years_to_goal: float | None = None
    monthly_contribution: float | None = None
    delay_months: int | None = None
    additional_monthly: float | None = None
    statute_tax: float | None = None
    channel_horizon_drag: float | None = None
    all_in_friction: float | None = None


class ReframeVerdict(BaseModel):
    """Structured reframe answer. Every figure from a tool."""

    headline: str
    preferred_lever: PreferredLever
    slip_delay_months: int | None = None
    slip_new_years: float | None = None
    shrink_reachable_target: float | None = None
    shrink_rupees: float | None = None
    topup_additional_monthly: float | None = None
    levers: list[LeverQuote] = Field(default_factory=list)
    cheapest_friction_kind: str | None = None
    reasoning: str


TASK_DESCRIPTION = """\
The original plan may miss its target. Quantify the three reframes and price them.

{brief}

Work in this order and use the tools for every number:

1. `slip_year` -- pass target_amount, years_to_goal, current_corpus,
   monthly_contribution, and the allocation from the brief verbatim. Read
   delay_months and new_years_to_goal.
2. `shrink_target` -- same plan inputs. Read reachable_target and shrink_rupees.
3. `monthly_topup` -- same plan inputs. Read additional_monthly_contribution.
4. `price_options` -- build three options from the tool results:
   - slip_year: original target, years = new_years_to_goal, same SIP, delay_months
   - shrink_target: target = reachable_target, original years, same SIP
   - monthly_topup: original target and years, SIP = current + additional
   Pass the brief's holdings JSON and disposals JSON verbatim -- do not invent
   categories, do not pass an allocation string as holdings. Also pass
   other_taxable_income, regime, age_band, and portfolio_value from the brief.
   Read all_in_friction per option. If price_options errors, fix the arguments
   from the brief and retry once; do not invent new holdings.

If Feasibility already said on_track and every lever comes back zero, set
preferred_lever to `none` and say the plan needs no reframe.

Rules:
- Every figure you report came from a tool.
- Prefer the lever whose story a client can act on; cite all_in_friction when
  comparing cost, but do not let a slightly cheaper path override an unusable
  timeline or SIP without saying so.
- Rates are decimals; money is rupees.
"""

EXPECTED_OUTPUT = """\
A ReframeVerdict. Populate slip_*, shrink_*, and topup_* from the matching tools.
`levers` summarises each priced option. `preferred_lever` is one of slip_year,
shrink_target, monthly_topup, or none. `reasoning` traces the choice to tool output.
"""


def build_reframe_agent(llm=None, verbose: bool = False, max_iter: int = 12) -> Agent:
    return Agent(
        role=ROLE,
        goal=GOAL,
        backstory=BACKSTORY,
        tools=reframe_tools(),
        llm=llm or build_llm(),
        allow_delegation=False,
        reasoning=False,
        max_iter=max_iter,
        verbose=verbose,
    )


def build_reframe_task(brief: ReframeBrief, agent: Agent) -> Task:
    return Task(
        description=TASK_DESCRIPTION.replace("{brief}", brief.as_prompt_block()),
        expected_output=EXPECTED_OUTPUT,
        agent=agent,
        output_pydantic=ReframeVerdict,
    )
