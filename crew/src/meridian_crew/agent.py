"""The Feasibility agent: its brief, its instructions, and its answer shape."""

from __future__ import annotations

import json
from typing import Any, Literal

from crewai import LLM, Agent, Task
from pydantic import BaseModel, Field, field_validator

from .config import llm_model
from .tools import feasibility_tools
from .tools.common import coerce_allocation_to_mapping, validate_allocation

ROLE = "Goal Feasibility Analyst"

GOAL = (
    "Decide whether a client's stated goal is reachable on their current plan, "
    "and if it is not, name the smallest change that makes it reachable."
)

BACKSTORY = (
    "You spent a decade building goal plans on a retail wealth desk, where the "
    "clients who lost money were rarely the ones who picked the wrong fund. They "
    "were the ones who put school fees in a product they could not sell in time, "
    "or who were quietly sold a return assumption nobody would defend out loud.\n\n"
    "So you work in a fixed order. Find out what the asset classes actually "
    "returned. Project the plan and measure the gap before proposing anything. "
    "Check what the goal date allows before naming a product. Only then look for "
    "the smallest reallocation that closes the gap.\n\n"
    "You never do arithmetic in your head: every number you state came back from "
    "a tool, because a projection you cannot reproduce is a guess with a decimal "
    "point. When no allocation can close the gap you say so plainly and turn to "
    "the contribution or the timeline instead of reaching for a riskier fund. A "
    "shortfall named early is a plan; a shortfall discovered late is a loss."
)


class GoalBrief(BaseModel):
    """Everything the agent needs to know about one client goal."""

    goal: str = Field(description="What the money is for.")
    target_amount: float = Field(gt=0)
    years_to_goal: float = Field(gt=0)
    current_corpus: float = Field(default=0.0, ge=0)
    monthly_contribution: float = Field(default=0.0, ge=0)
    allocation: dict[str, float] = Field(
        description="Current weights in percent by nav_history category key."
    )
    client_age: int | None = Field(default=None, ge=0)
    currency: str = Field(default="INR")
    annual_step_up_pct: float = Field(default=0.0, ge=0)
    max_equity_pct: float | None = Field(default=None)
    notes: str | None = Field(default=None)

    @field_validator("allocation", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return coerce_allocation_to_mapping(value)

    @field_validator("allocation")
    @classmethod
    def _validate(cls, value: dict[str, float]) -> dict[str, float]:
        # Fail here rather than three tool calls into a paid run.
        return validate_allocation(value)

    def allocation_argument(self) -> str:
        """The allocation already in tool-argument form.

        Handing the model a ready-to-paste argument is more reliable than asking
        it to build one from prose.
        """
        return json.dumps(
            [
                {"category": key, "weight_pct": weight}
                for key, weight in self.allocation.items()
            ]
        )

    def as_prompt_block(self) -> str:
        lines = [
            f"Goal: {self.goal}",
            f"Target amount: {self.currency} {self.target_amount:,.0f}",
            f"Years until the money is needed: {self.years_to_goal:g}",
            f"Invested today: {self.currency} {self.current_corpus:,.0f}",
            f"Monthly contribution: {self.currency} {self.monthly_contribution:,.0f}",
            "Current allocation, to pass verbatim as the `allocation` and "
            f"`current_allocation` arguments:\n{self.allocation_argument()}",
        ]
        if self.client_age is not None:
            lines.append(f"Client age: {self.client_age}")
        if self.annual_step_up_pct:
            lines.append(
                f"Contribution step-up: {self.annual_step_up_pct:g}% a year"
            )
        if self.max_equity_pct is not None:
            lines.append(f"Equity must stay at or below {self.max_equity_pct:g}%")
        if self.notes:
            lines.append(f"Adviser notes: {self.notes}")
        return "\n".join(lines)


class FeasibilityVerdict(BaseModel):
    """The structured answer. Every number here must have come from a tool."""

    verdict: Literal["on_track", "reachable_with_changes", "not_reachable"]
    headline: str = Field(description="One sentence a client would understand.")
    projected_corpus: float = Field(description="Corpus at the goal date on today's plan.")
    target_amount: float
    shortfall: float = Field(description="0 when the plan already reaches the target.")
    expected_annual_return: float = Field(description="Decimal, from the current allocation.")
    required_annual_return: float | None = Field(
        default=None, description="Decimal. Null when the plan is already on track."
    )
    recommended_shift_pct: float | None = Field(
        default=None, description="Percentage points of the portfolio to move."
    )
    recommended_moves: list[str] = Field(
        default_factory=list,
        description="Each move as 'from_category -> to_category: N%'.",
    )
    ruled_out_products: list[str] = Field(
        default_factory=list,
        description="Products the goal date excludes, each with the reason.",
    )
    other_levers: list[str] = Field(
        default_factory=list,
        description="Contribution or timeline changes that would also close the gap.",
    )
    risks: list[str] = Field(
        default_factory=list, description="What could still go wrong with this plan."
    )
    reasoning: str = Field(description="How the conclusion follows from the tool output.")


TASK_DESCRIPTION = """\
Assess whether this client reaches their goal, and if not, what the smallest fix is.

{brief}

Work in this order and use the tools for every number:

1. `nav_history` -- see what the categories in the client's allocation have
   returned and how volatile they are.
2. `goal_solver` -- project the plan to the goal date. Pass the allocation from
   the brief verbatim as the `allocation` argument, a list of
   {"category": ..., "weight_pct": ...} objects, so the tool blends the returns
   itself. Never compute a blended return yourself and never send an empty list.
   Read the shortfall and `required_annual_return`.
3. `horizon_filter` -- if there is a shortfall, find out which products the goal
   date allows. Pass `client_age` when you have it.
4. `reallocation_search` -- pass the `required_annual_return` from step 2 and the
   `eligible_categories` from step 3, plus any equity ceiling in the brief. This
   gives you the smallest shift that closes the gap.

If step 2 shows the plan is already on track, say so and stop; do not manufacture
a change. If step 4 comes back `feasible: false`, then no allocation reaches this
goal: say that plainly and use `goal_solver`'s
`required_monthly_contribution` to quantify the contribution lever instead.

Rules:
- Every figure you report must appear in a tool result. Do not round a shortfall
  into a rounder story, and do not invent a return you did not read.
- Report rates as decimals, matching the tools.
- Name the trade-off of any shift you recommend, using the volatility figures.
- Treat gold's trailing return with suspicion: it reflects one exceptional run.
"""

EXPECTED_OUTPUT = """\
A FeasibilityVerdict. `verdict` is `on_track` when the current plan already meets
the target, `reachable_with_changes` when a reallocation within the constraints
closes the gap, and `not_reachable` when the reallocation search came back
infeasible. Amounts in the brief's currency, rates as decimals. `reasoning` must
trace the conclusion back to specific tool results.
"""


def build_llm(model: str | None = None, temperature: float = 0.0) -> LLM:
    """A deterministic-as-possible LLM. Planning maths should not be creative."""
    return LLM(model=model or llm_model(), temperature=temperature)


def build_feasibility_agent(
    llm: LLM | None = None, verbose: bool = False, max_iter: int = 12
) -> Agent:
    return Agent(
        role=ROLE,
        goal=GOAL,
        backstory=BACKSTORY,
        tools=feasibility_tools(),
        llm=llm or build_llm(),
        allow_delegation=False,
        reasoning=False,
        max_iter=max_iter,
        verbose=verbose,
    )


def build_feasibility_task(brief: GoalBrief, agent: Agent) -> Task:
    return Task(
        # replace, not format: the template contains literal JSON braces.
        description=TASK_DESCRIPTION.replace("{brief}", brief.as_prompt_block()),
        expected_output=EXPECTED_OUTPUT,
        agent=agent,
        output_pydantic=FeasibilityVerdict,
    )
