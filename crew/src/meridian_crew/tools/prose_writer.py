"""`prose_writer` -- one LLM call to four stance + ranked + cross-reference JSON.

Uses the same LiteLLM-backed model as the rest of the desk (OpenRouter / gpt-mini
by default). Structured JSON out; no free-form markdown.
"""

from __future__ import annotations

import json
import re
from typing import Any, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field, ValidationError, field_validator


class ProseWriterInput(BaseModel):
    goal: str = Field(description="Client goal in one line.")
    best_path: str = Field(description="Winning path id from ledger.")
    ledger_summary: str = Field(
        description="Compact summary of ranked paths and net rupee claims."
    )
    feasibility_headline: str | None = None
    statute_headline: str | None = None
    channel_headline: str | None = None
    reframe_headline: str | None = None
    eligibility_note: str | None = None
    cross_references: list[str] = Field(
        default_factory=list,
        description="Keys the prose must cite, e.g. 'statute.total_tax', 'reframe.slip_year'.",
    )

    @field_validator("cross_references", mode="before")
    @classmethod
    def _coerce_refs(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(item) for item in parsed]
            except json.JSONDecodeError:
                return [part.strip() for part in re.split(r"[,;\n]+", text) if part.strip()]
        return value


class Stance(BaseModel):
    path: str
    posture: str = Field(description="One of: recommend, accept, caution, reject.")
    line: str = Field(description="One client-ready sentence.")


class ProseWriterResult(BaseModel):
    stances: list[Stance] = Field(
        description="Exactly four stance objects covering the open paths."
    )
    ranked_recommendation: str
    cross_reference_objects: list[dict[str, str]]
    adviser_blurb: str


_SYSTEM = """\
You are the Shared desk writer for a wealth platform.
Return ONLY valid JSON matching this schema:
{
  "stances": [
    {"path": "...", "posture": "recommend|accept|caution|reject", "line": "..."},
    ... exactly four objects ...
  ],
  "ranked_recommendation": "one paragraph naming the best path and why",
  "cross_reference_objects": [
    {"ref": "statute.total_tax", "cite": "how the number is used in the prose"}
  ],
  "adviser_blurb": "two sentences an adviser can read aloud"
}
Rules:
- Every rupee figure you mention must already appear in the inputs.
- Do not invent tax, drag, or SIP numbers.
- Prefer plain INR phrasing a client understands.
"""


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


class ProseWriterTool(BaseTool):
    name: str = "prose_writer"
    description: str = (
        "One LLM call that turns the ranked ledger into four stance objects, a "
        "ranked recommendation, and cross-reference objects (structured JSON). "
        "Pass the goal, best_path, ledger_summary, stage headlines, and the "
        "cross_references keys you need cited. Call this last."
    )
    args_schema: Type[BaseModel] = ProseWriterInput

    def _run(
        self,
        goal: str,
        best_path: str,
        ledger_summary: str,
        feasibility_headline: str | None = None,
        statute_headline: str | None = None,
        channel_headline: str | None = None,
        reframe_headline: str | None = None,
        eligibility_note: str | None = None,
        cross_references: list[str] | None = None,
    ) -> ProseWriterResult:
        # Lazy import: agent.py imports tool packs, so build_llm cannot sit at
        # module import time without a circular dependency.
        from ..agent import build_llm

        refs = cross_references or []
        user_payload = {
            "goal": goal,
            "best_path": best_path,
            "ledger_summary": ledger_summary,
            "headlines": {
                "feasibility": feasibility_headline,
                "statute": statute_headline,
                "channel": channel_headline,
                "reframe": reframe_headline,
            },
            "eligibility_note": eligibility_note,
            "cross_references": refs,
        }
        llm = build_llm(temperature=0.0)
        prompt = (
            _SYSTEM
            + "\n\nINPUTS:\n"
            + json.dumps(user_payload, indent=2)
            + "\n\nJSON:"
        )
        raw = llm.call(prompt)
        try:
            data = _extract_json(str(raw))
            result = ProseWriterResult.model_validate(data)
        except (json.JSONDecodeError, ValidationError, ValueError) as error:
            # Deterministic fallback so the Shared stage still closes.
            paths = ["status_quo", "slip_year", "shrink_target", "monthly_topup"]
            stances = []
            for path in paths:
                posture = "recommend" if path == best_path else "caution"
                stances.append(
                    Stance(
                        path=path,
                        posture=posture,
                        line=(
                            f"{path.replace('_', ' ').title()} is the lead path."
                            if path == best_path
                            else f"{path.replace('_', ' ').title()} stays open but is not first."
                        ),
                    )
                )
            result = ProseWriterResult(
                stances=stances,
                ranked_recommendation=(
                    f"For '{goal}', the ledger picks {best_path}. "
                    f"{ledger_summary}"
                ),
                cross_reference_objects=[
                    {"ref": ref, "cite": "Carried from the upstream stage."}
                    for ref in refs[:6]
                ],
                adviser_blurb=(
                    f"Lead with {best_path}. "
                    "Every figure below traces to a tool, not to prose."
                ),
            )
            result.adviser_blurb += f" (writer fallback: {error})"
        # Ensure four stances.
        if len(result.stances) < 4:
            while len(result.stances) < 4:
                result.stances.append(
                    Stance(
                        path=f"open_{len(result.stances)+1}",
                        posture="caution",
                        line="Path reserved; insufficient detail upstream.",
                    )
                )
        result.stances = result.stances[:4]
        return result

    def format_output_for_agent(self, raw_result: object) -> str:
        result = ProseWriterResult.model_validate(raw_result)
        lines = ["Four stances:", ""]
        for stance in result.stances:
            lines.append(f"- [{stance.posture}] {stance.path}: {stance.line}")
        lines += [
            "",
            "Ranked recommendation:",
            result.ranked_recommendation,
            "",
            "Adviser blurb:",
            result.adviser_blurb,
        ]
        if result.cross_reference_objects:
            lines += ["", "Cross-references:"]
            for item in result.cross_reference_objects:
                lines.append(f"- {item.get('ref')}: {item.get('cite')}")
        return "\n".join(lines)
