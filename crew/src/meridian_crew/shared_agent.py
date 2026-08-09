"""The Shared agent: eligibility, ledger ranking, and the final prose package."""

from __future__ import annotations

from typing import Any, Literal

from crewai import Agent, Task
from pydantic import BaseModel, Field

from .agent import build_llm
from .tools import shared_tools

ROLE = "Shared Desk Synthesizer"

GOAL = (
    "Gate the client on the SEBI product ladder, rank every open path by signed "
    "rupee claims, and write one structured prose package an adviser can use."
)

BACKSTORY = (
    "You close the desk. Upstream agents have already done the maths; your job "
    "is to refuse products the corpus cannot buy, put every signed rupee claim "
    "on one ledger, and speak once -- four stances, a ranked recommendation, "
    "and cross-references back to the numbers. You never re-run a projection. "
    "If a figure is missing upstream you say so rather than invent it."
)


class SharedBrief(BaseModel):
    """Everything Shared needs from the prior stages."""

    goal: str
    investable_corpus: float = Field(gt=0)
    currency: str = "INR"
    feasibility_headline: str | None = None
    feasibility_verdict: str | None = None
    shortfall: float | None = None
    statute_headline: str | None = None
    statute_tax: float | None = None
    channel_headline: str | None = None
    channel_annual_drag: float | None = None
    reframe_headline: str | None = None
    preferred_lever: str | None = None
    slip_delay_months: int | None = None
    shrink_rupees: float | None = None
    topup_additional_monthly: float | None = None
    priced_options: list[dict[str, Any]] = Field(default_factory=list)
    proposed_product: str | None = Field(
        default=None,
        description="Optional product lane to test through eligibility_gate.",
    )
    notes: str | None = None

    def as_prompt_block(self) -> str:
        lines = [
            f"Goal: {self.goal}",
            f"Investable corpus: {self.currency} {self.investable_corpus:,.0f}",
        ]
        if self.feasibility_headline:
            lines.append(f"Feasibility: {self.feasibility_headline}")
        if self.feasibility_verdict:
            lines.append(f"Feasibility verdict: {self.feasibility_verdict}")
        if self.shortfall is not None:
            lines.append(f"Shortfall: {self.currency} {self.shortfall:,.0f}")
        if self.statute_headline:
            lines.append(f"Statute: {self.statute_headline}")
        if self.statute_tax is not None:
            lines.append(f"Statute tax: {self.currency} {self.statute_tax:,.0f}")
        if self.channel_headline:
            lines.append(f"Channel: {self.channel_headline}")
        if self.channel_annual_drag is not None:
            lines.append(
                f"Channel annual drag: {self.currency} {self.channel_annual_drag:,.0f}"
            )
        if self.reframe_headline:
            lines.append(f"Reframe: {self.reframe_headline}")
        if self.preferred_lever:
            lines.append(f"Reframe preferred lever: {self.preferred_lever}")
        if self.slip_delay_months is not None:
            lines.append(f"Slip delay months: {self.slip_delay_months}")
        if self.shrink_rupees is not None:
            lines.append(f"Shrink rupees: {self.currency} {self.shrink_rupees:,.0f}")
        if self.topup_additional_monthly is not None:
            lines.append(
                f"Top-up additional monthly: {self.currency} "
                f"{self.topup_additional_monthly:,.0f}"
            )
        if self.priced_options:
            lines.append(f"Priced options: {self.priced_options!r}")
        if self.proposed_product:
            lines.append(f"Proposed product lane to test: {self.proposed_product}")
        if self.notes:
            lines.append(f"Adviser notes: {self.notes}")
        return "\n".join(lines)


class StanceOut(BaseModel):
    path: str
    posture: Literal["recommend", "accept", "caution", "reject"]
    line: str


class SharedVerdict(BaseModel):
    headline: str
    highest_eligible_lane: str
    best_path: str
    stances: list[StanceOut] = Field(default_factory=list)
    ranked_recommendation: str
    cross_references: list[str] = Field(default_factory=list)
    adviser_blurb: str
    reasoning: str


TASK_DESCRIPTION = """\
Close the desk: gate eligibility, rank the ledger, write the prose package.

{brief}

Work in this order and use the tools for every structured output:

1. `eligibility_gate` -- pass investable_corpus from the brief. If a proposed
   product lane is present, pass it too. Read highest_eligible and blocked_lanes.
2. `ledger` -- build signed rupee claims from the upstream numbers. At minimum:
   - shortfall as a cost on path `status_quo` (if any)
   - statute_tax as a cost on each reframe path that still switches
   - channel annual drag (or horizon drag from priced_options) as a cost
   - shrink_rupees as a cost on `shrink_target` (target given up)
   - for benefits, prefer lower all_in_friction vs the worst option
   Use the priced_options list when present so friction figures stay consistent.
   Read best_path.
3. `prose_writer` -- pass goal, best_path, a compact ledger_summary, the stage
   headlines, eligibility_note, and cross_references such as
   statute.total_tax, channel.annual_drag, reframe.preferred_lever,
   eligibility.highest_eligible. Read the four stances and ranked_recommendation.

Rules:
- Do not invent rupee figures. Every claim amount came from the brief or a tool.
- If eligibility blocks a proposed product, say so in the headline.
- `stances` must be four objects.
"""

EXPECTED_OUTPUT = """\
A SharedVerdict. `highest_eligible_lane` from eligibility_gate, `best_path` from
ledger, `stances` / `ranked_recommendation` / `adviser_blurb` from prose_writer.
`cross_references` lists the keys the prose cited. `reasoning` ties the close
back to those tools.
"""


def build_shared_agent(llm=None, verbose: bool = False, max_iter: int = 10) -> Agent:
    return Agent(
        role=ROLE,
        goal=GOAL,
        backstory=BACKSTORY,
        tools=shared_tools(),
        llm=llm or build_llm(),
        allow_delegation=False,
        reasoning=False,
        max_iter=max_iter,
        verbose=verbose,
    )


def build_shared_task(brief: SharedBrief, agent: Agent) -> Task:
    return Task(
        description=TASK_DESCRIPTION.replace("{brief}", brief.as_prompt_block()),
        expected_output=EXPECTED_OUTPUT,
        agent=agent,
        output_pydantic=SharedVerdict,
    )
