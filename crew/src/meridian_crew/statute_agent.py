"""The Statute agent: prices the capital-gains bill on a proposed switch."""

from __future__ import annotations

import json
import re
from typing import Any

from crewai import Agent, Task
from pydantic import BaseModel, Field, field_validator

from .agent import build_llm
from .config import DEFAULT_EMBEDDED_GAIN_PCT, DEFAULT_HOLDING_MONTHS
from .tools import statute_tools
from .tools.tax import AgeBand, Disposal, Regime, coerce_disposals

ROLE = "Capital Gains Statute Analyst"

GOAL = (
    "Price the Indian capital-gains tax on a proposed fund switch in rupees, "
    "name every section that applies, and test whether staging the switch "
    "across financial years is worth the wait."
)

BACKSTORY = (
    "You price switches the way a tax counsel prices them: section by section, "
    "never by a blended rule of thumb. Equity held over a year is 112A. Equity "
    "held a year or less is 111A at twenty percent with no annual exemption. "
    "Debt bought after 1 April 2023 is section 50AA and joins the slab. "
    "Surcharge and cess come last, once, on every charge together.\n\n"
    "You never do the arithmetic yourself. Each rupee you quote came back from "
    "a tool. When a leg belongs to a different section you route it instead of "
    "forcing it through the wrong rate. And when the 112A exemption is the "
    "difference between a painful bill and a small one, you check whether "
    "splitting the switch across 31 March pays -- then say what that wait costs "
    "in market risk, which the tool cannot price."
)


class SwitchBrief(BaseModel):
    """Everything the Statute agent needs to price one proposed switch."""

    purpose: str = Field(
        default="Proposed reallocation",
        description="Why the switch is being made.",
    )
    disposals: list[Disposal] = Field(
        description="Sale legs of the switch, as category/redemption_value objects."
    )
    other_taxable_income: float = Field(
        default=1_200_000.0,
        ge=0,
        description="Client taxable income before these gains.",
    )
    regime: Regime = Field(default="new")
    age_band: AgeBand = Field(default="below_60")
    exemption_already_used: float = Field(default=0.0, ge=0)
    currency: str = Field(default="INR")
    notes: str | None = Field(default=None)

    @field_validator("disposals", mode="before")
    @classmethod
    def _coerce(cls, value: Any) -> Any:
        return coerce_disposals(value)

    def disposals_argument(self) -> str:
        return json.dumps(
            [
                d.model_dump() if hasattr(d, "model_dump") else d
                for d in self.disposals
            ]
        )

    def as_prompt_block(self) -> str:
        lines = [
            f"Purpose: {self.purpose}",
            f"Other taxable income: {self.currency} {self.other_taxable_income:,.0f}",
            f"Tax regime: {self.regime}",
            f"Age band: {self.age_band}",
            f"Section 112A exemption already used this FY: "
            f"{self.currency} {self.exemption_already_used:,.0f}",
            "Disposals to pass verbatim as the `disposals` argument:",
            self.disposals_argument(),
            (
                f"Where cost basis or holding period is missing, the tools assume "
                f"{DEFAULT_EMBEDDED_GAIN_PCT:g}% embedded gain and "
                f"{DEFAULT_HOLDING_MONTHS:g} months held -- quote those as "
                "assumptions, not facts."
            ),
        ]
        if self.notes:
            lines.append(f"Adviser notes: {self.notes}")
        return "\n".join(lines)


class StatuteVerdict(BaseModel):
    """Structured tax answer. Every rupee must have come from a tool."""

    headline: str = Field(description="One sentence a client would understand.")
    total_tax: float = Field(description="Tax payable including surcharge and cess.")
    tax_before_surcharge: float | None = Field(default=None)
    sections_applied: list[str] = Field(default_factory=list)
    equity_ltcg_112a: float | None = Field(default=None)
    equity_stcg_111a: float | None = Field(default=None)
    debt_slab_tax: float | None = Field(default=None)
    staging_saves: float | None = Field(
        default=None,
        description="Rupees saved by splitting across financial years; 0 if none.",
    )
    recommend_staging: bool = Field(default=False)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    reasoning: str


TASK_DESCRIPTION = """\
Price the capital-gains tax on this proposed switch.

{brief}

Work in this order and use the tools for every number:

1. Classify the legs. Call `ltcg_112a` with every disposal. Read which legs it
   priced under 112A and which it refused (`not_priced_here`).
2. Route the refused equity short-term legs to `stcg_111a`, and the debt legs to
   `debt_slab` with `other_taxable_income` from the brief.
3. Call `surcharge_band` once with every charge together and the client's total
   income including these gains. That number is what the client pays.
4. Call `fy_stager` on the whole switch to see whether splitting across two
   financial years saves real money. If it does, say so -- and name the market
   risk of leaving the untraded tranche in place.

Rules:
- Every rupee you report came from a tool. Do not blend rates yourself.
- Quote the section string the tool returned (112A, 111A, 50AA/slab, 112).
- Rates in tool output are decimals; amounts are rupees.
- If there are no disposals, say the tax is zero and stop.
"""

EXPECTED_OUTPUT = """\
A StatuteVerdict. `total_tax` is the surcharge-and-cess figure from
surcharge_band. `staging_saves` is the rupee difference from fy_stager (0 when
staging does not help). `recommend_staging` is true only when the saving is
material and you have named the market-risk trade-off. `reasoning` traces each
number back to a tool result.
"""


_MOVE_RE = re.compile(
    r"(?P<source>[A-Za-z0-9_]+)\s*->\s*(?P<dest>[A-Za-z0-9_]+)\s*:\s*"
    r"(?P<pct>-?[0-9]+(?:\.[0-9]+)?)\s*%?"
)


def disposals_from_moves(
    moves: list[str],
    portfolio_value: float,
    holding_months: float = DEFAULT_HOLDING_MONTHS,
    embedded_gain_pct: float = DEFAULT_EMBEDDED_GAIN_PCT,
) -> list[dict[str, Any]]:
    """Turn Feasibility's 'from -> to: N%' moves into Statute disposals."""
    disposals: list[dict[str, Any]] = []
    for move in moves or []:
        match = _MOVE_RE.search(move)
        if not match:
            continue
        pct = abs(float(match.group("pct")))
        if pct <= 0 or portfolio_value <= 0:
            continue
        disposals.append(
            {
                "category": match.group("source"),
                "redemption_value": round(portfolio_value * pct / 100.0, 2),
                "holding_months": holding_months,
                "embedded_gain_pct": embedded_gain_pct,
            }
        )
    return disposals


def build_statute_agent(
    llm=None, verbose: bool = False, max_iter: int = 14
) -> Agent:
    return Agent(
        role=ROLE,
        goal=GOAL,
        backstory=BACKSTORY,
        tools=statute_tools(),
        llm=llm or build_llm(),
        allow_delegation=False,
        reasoning=False,
        max_iter=max_iter,
        verbose=verbose,
    )


def build_statute_task(brief: SwitchBrief, agent: Agent) -> Task:
    return Task(
        description=TASK_DESCRIPTION.replace("{brief}", brief.as_prompt_block()),
        expected_output=EXPECTED_OUTPUT,
        agent=agent,
        output_pydantic=StatuteVerdict,
    )
