"""CLI for the Feasibility agent.

    uv run feasibility --target-amount 5000000 --years 7 \
      --current-corpus 900000 --monthly-contribution 25000 \
      --allocation equity_large_cap=30,hybrid_aggressive=20,debt_short_duration=30,debt_liquid=20
"""

from __future__ import annotations

import argparse
import json
import sys

from .agent import GoalBrief
from .config import llm_model
from .crew import MissingCredentialsError, run_feasibility
from .stream import emit, stream_feasibility
from .tools.nav_history import category_keys

DEFAULT_ALLOCATION = (
    "equity_large_cap=30,hybrid_aggressive=20,debt_short_duration=30,debt_liquid=20"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="feasibility", description="Assess whether a client goal is reachable."
    )
    parser.add_argument("--goal", default="Unnamed goal", help="What the money is for.")
    parser.add_argument("--target-amount", type=float, required=True)
    parser.add_argument("--years", type=float, required=True, dest="years_to_goal")
    parser.add_argument("--current-corpus", type=float, default=0.0)
    parser.add_argument("--monthly-contribution", type=float, default=0.0)
    parser.add_argument(
        "--allocation",
        default=DEFAULT_ALLOCATION,
        help="category=weight pairs in percent, comma separated. Must sum to 100.",
    )
    parser.add_argument("--client-age", type=int, default=None)
    parser.add_argument("--currency", default="INR")
    parser.add_argument("--step-up", type=float, default=0.0, dest="annual_step_up_pct")
    parser.add_argument("--max-equity-pct", type=float, default=None)
    parser.add_argument("--notes", default=None)
    parser.add_argument("--model", default=None, help=f"Default: {llm_model()}")
    parser.add_argument(
        "--trace", action="store_true", help="Echo each tool call as it happens."
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Full CrewAI reasoning output."
    )
    parser.add_argument("--json", action="store_true", help="Print the verdict as JSON.")
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Emit newline-delimited JSON events as they happen, for the API bridge.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved brief and exit without calling the model.",
    )
    parser.add_argument(
        "--list-categories", action="store_true", help="Print valid category keys and exit."
    )
    return parser


def _render(run) -> str:
    verdict = run.verdict
    if verdict is None:
        return f"Model returned an unparsable answer:\n\n{run.raw}"

    lines = [
        f"VERDICT: {verdict.verdict.upper().replace('_', ' ')}",
        "",
        verdict.headline,
        "",
        f"  Projected corpus     {verdict.projected_corpus:,.0f}",
        f"  Target               {verdict.target_amount:,.0f}",
        f"  Shortfall            {verdict.shortfall:,.0f}",
        f"  Expected return      {verdict.expected_annual_return * 100:.2f}%",
    ]
    if verdict.required_annual_return is not None:
        lines.append(
            f"  Required return      {verdict.required_annual_return * 100:.2f}%"
        )
    if verdict.recommended_shift_pct is not None:
        lines.append(f"  Portfolio to move    {verdict.recommended_shift_pct:g}%")

    for title, items in (
        ("RECOMMENDED MOVES", verdict.recommended_moves),
        ("RULED OUT BY THE GOAL DATE", verdict.ruled_out_products),
        ("OTHER LEVERS", verdict.other_levers),
        ("RISKS", verdict.risks),
    ):
        if items:
            lines += ["", f"{title}:"] + [f"  - {item}" for item in items]

    lines += ["", "REASONING:", verdict.reasoning]
    lines += ["", f"Tools called: {', '.join(run.tools_used) or 'none'}"]
    if run.usage:
        total = run.usage.get("total_tokens")
        if total:
            lines.append(f"Tokens: {total:,} ({run.model})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_categories:
        print("\n".join(category_keys()))
        return 0

    try:
        brief = GoalBrief(
            goal=args.goal,
            target_amount=args.target_amount,
            years_to_goal=args.years_to_goal,
            current_corpus=args.current_corpus,
            monthly_contribution=args.monthly_contribution,
            allocation=args.allocation,
            client_age=args.client_age,
            currency=args.currency,
            annual_step_up_pct=args.annual_step_up_pct,
            max_equity_pct=args.max_equity_pct,
            notes=args.notes,
        )
    except ValueError as error:
        if args.stream:
            # The consumer only reads stdout, so a rejected brief has to arrive
            # as an event rather than on stderr.
            emit({"type": "error", "message": f"Invalid brief: {error}"})
            emit({"type": "status", "state": "halted", "label": "Invalid brief"})
            return 2
        print(f"Invalid brief: {error}", file=sys.stderr)
        return 2

    if args.stream:
        return stream_feasibility(brief, model=args.model)

    if args.dry_run:
        print(brief.as_prompt_block())
        print(f"\nModel that would run: {args.model or llm_model()}")
        return 0

    try:
        run = run_feasibility(
            brief, model=args.model, verbose=args.verbose, trace=args.trace
        )
    except MissingCredentialsError as error:
        print(str(error), file=sys.stderr)
        return 3

    if args.json:
        payload = {
            "model": run.model,
            "tools_used": run.tools_used,
            "usage": run.usage,
            "verdict": run.verdict.model_dump() if run.verdict else None,
            "raw": None if run.verdict else run.raw,
        }
        print(json.dumps(payload, indent=2))
    else:
        print()
        print(_render(run))

    if run.tool_errors:
        print(
            f"\n{len(run.tool_errors)} tool call(s) failed: "
            + ", ".join(f"{c.name} ({c.error})" for c in run.tool_errors),
            file=sys.stderr,
        )
    return 0 if run.verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
