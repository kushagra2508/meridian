"""The Channel agent: prices Regular-vs-Direct expense drag on the MF sleeve."""

from __future__ import annotations

import json
from typing import Any, Literal

from crewai import Agent, Task
from pydantic import BaseModel, Field, field_validator

from .agent import build_llm
from .tools import channel_tools
from .tools.drag_calc import HoldingLine, coerce_holdings

ROLE = "Fund Channel Cost Analyst"

GOAL = (
    "Measure what the client pays for staying in Regular-plan mutual funds "
    "instead of Direct, and say out loud which holdings this figure does not cover."
)

BACKSTORY = (
    "You grew up on a distribution desk, so you know the Regular plan is not a "
    "different fund -- it is the same portfolio with a trail commission baked "
    "into the expense ratio. The gap looks small in basis points and large in "
    "rupees once it compounds, which is why you always convert it.\n\n"
    "You work in a fixed order. Look up the TERs. Multiply them by the money "
    "that is actually in Regular mutual funds. Then name everything you could "
    "not price -- PPF, NPS, ULIP, deposits, PMS -- so nobody mistakes a Mutual "
    "Fund drag figure for a whole-portfolio cost. You never invent a TER. If "
    "AMFI has no number, you say so."
)

Plan = Literal["regular", "direct"]


class ChannelBrief(BaseModel):
    """Portfolio the Channel agent prices for Regular-vs-Direct drag."""

    portfolio_value: float = Field(gt=0)
    holdings: list[HoldingLine] = Field(
        description="Current holdings with plan type for each MF line."
    )
    currency: str = Field(default="INR")
    notes: str | None = Field(default=None)

    @field_validator("holdings", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return coerce_holdings(value)

    def holdings_argument(self) -> str:
        return json.dumps(
            [
                h.model_dump() if hasattr(h, "model_dump") else h
                for h in self.holdings
            ]
        )

    def as_prompt_block(self) -> str:
        lines = [
            f"Portfolio value: {self.currency} {self.portfolio_value:,.0f}",
            "Holdings to pass verbatim as the `holdings` argument:",
            self.holdings_argument(),
        ]
        if self.notes:
            lines.append(f"Adviser notes: {self.notes}")
        return "\n".join(lines)


class ChannelVerdict(BaseModel):
    """Structured channel-cost answer. Every figure from a tool."""

    headline: str
    annual_drag_rupees: float
    annual_drag_pct_of_portfolio: float = Field(description="Decimal.")
    annual_drag_pct_of_mf: float | None = Field(
        default=None, description="Decimal, against the MF sleeve only."
    )
    five_year_drag_rupees: float | None = Field(default=None)
    regular_mf_weight_pct: float | None = Field(default=None)
    largest_gap_categories: list[str] = Field(
        default_factory=list,
        description="Categories with the widest Regular-vs-Direct TER gap in this book.",
    )
    out_of_scope: list[str] = Field(
        default_factory=list,
        description="Holdings the tools could not price -- must be said aloud.",
    )
    recommendations: list[str] = Field(default_factory=list)
    reasoning: str


TASK_DESCRIPTION = """\
Price the Regular-versus-Direct expense drag on this portfolio.

{brief}

Work in this order and use the tools for every number:

1. `scope_guard` -- pass every holding id/category (and kind when you have it).
   Read `out_of_scope` and plan to say those items aloud in the verdict.
2. `ter_lookup` -- look up Regular and Direct TERs for the mutual-fund
   categories that are in scope.
3. `drag_calc` -- pass the holdings and portfolio_value from the brief
   verbatim. Read the annual rupee drag, the drag as a percent of the portfolio,
   and the drag as a percent of the MF sleeve.

Rules:
- Every figure you report came from a tool. Do not invent a TER.
- Rates are decimals (0.012 means 1.2%).
- The drag figure covers Regular mutual funds only. Anything in
  scope_guard.out_of_scope must appear in your `out_of_scope` list and in the
  headline or reasoning so it is said aloud.
- If every MF line is already Direct, the drag is zero -- say that plainly.
"""

EXPECTED_OUTPUT = """\
A ChannelVerdict. `annual_drag_rupees` and the percentage fields come from
drag_calc. `out_of_scope` lists every holding scope_guard could not price.
`largest_gap_categories` names the categories whose TER gap dominates the bill.
`reasoning` traces the conclusion back to specific tool results.
"""


def holdings_from_allocation(
    allocation: dict[str, float],
    plan: Plan = "regular",
    extra: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build Channel holdings from a Feasibility allocation mapping."""
    holdings = [
        {
            "category": key,
            "weight_pct": weight,
            "plan": plan,
            "kind": "mutual_fund",
        }
        for key, weight in allocation.items()
    ]
    if extra:
        holdings.extend(extra)
    return holdings


def build_channel_agent(
    llm=None, verbose: bool = False, max_iter: int = 10
) -> Agent:
    return Agent(
        role=ROLE,
        goal=GOAL,
        backstory=BACKSTORY,
        tools=channel_tools(),
        llm=llm or build_llm(),
        allow_delegation=False,
        reasoning=False,
        max_iter=max_iter,
        verbose=verbose,
    )


def build_channel_task(brief: ChannelBrief, agent: Agent) -> Task:
    return Task(
        description=TASK_DESCRIPTION.replace("{brief}", brief.as_prompt_block()),
        expected_output=EXPECTED_OUTPUT,
        agent=agent,
        output_pydantic=ChannelVerdict,
    )
