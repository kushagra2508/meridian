"""CLI for the Meridian agent desk.

Default command runs the full pipeline
(Planner → Tax → Fees → Rethink → Verdict):

    uv run meridian \
      --goal "Daughter's undergraduate tuition" \
      --target-amount 5000000 --years 7 \
      --current-corpus 900000 --monthly-contribution 25000 \
      --allocation equity_large_cap=30,hybrid_aggressive=20,debt_short_duration=30,debt_liquid=20

Single-agent modes: `--agent feasibility|statute|channel|reframe|shared`.
"""

from __future__ import annotations

import argparse
import json
import sys

from .agent import FeasibilityVerdict, GoalBrief
from .channel_agent import ChannelVerdict
from .config import llm_model
from .crew import (
    MissingCredentialsError,
    default_channel_brief,
    default_reframe_brief,
    default_shared_brief,
    default_switch_brief,
    run_channel,
    run_feasibility,
    run_pipeline,
    run_reframe,
    run_shared,
    run_statute,
)
from .reframe_agent import ReframeVerdict
from .shared_agent import SharedVerdict
from .statute_agent import StatuteVerdict, SwitchBrief
from .stream import (
    emit,
    stream_channel,
    stream_feasibility,
    stream_pipeline,
    stream_reframe,
    stream_shared,
    stream_statute,
)
from .tools.nav_history import category_keys

DEFAULT_ALLOCATION = (
    "equity_large_cap=30,hybrid_aggressive=20,debt_short_duration=30,debt_liquid=20"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meridian",
        description="Run the Meridian agent desk (Planner through Verdict).",
    )
    parser.add_argument(
        "--agent",
        choices=("pipeline", "planner", "tax", "fees", "rethink", "verdict"),
        default="pipeline",
        help="Which agent (or the full pipeline) to run. Default: pipeline.",
    )
    parser.add_argument("--goal", default="Unnamed goal", help="What the money is for.")
    parser.add_argument("--target-amount", type=float, default=5_000_000.0)
    parser.add_argument("--years", type=float, default=7.0, dest="years_to_goal")
    parser.add_argument("--current-corpus", type=float, default=900_000.0)
    parser.add_argument("--monthly-contribution", type=float, default=25_000.0)
    parser.add_argument(
        "--allocation",
        default=DEFAULT_ALLOCATION,
        help="category=weight pairs in percent, comma separated. Must sum to 100.",
    )
    parser.add_argument("--client-age", type=int, default=42)
    parser.add_argument("--currency", default="INR")
    parser.add_argument("--step-up", type=float, default=0.0, dest="annual_step_up_pct")
    parser.add_argument("--max-equity-pct", type=float, default=None)
    parser.add_argument("--notes", default=None)
    parser.add_argument(
        "--other-income",
        type=float,
        default=1_200_000.0,
        dest="other_taxable_income",
        help="Taxable income before switch gains (Tax).",
    )
    parser.add_argument("--regime", choices=("new", "old"), default="new")
    parser.add_argument(
        "--age-band",
        choices=("below_60", "60_to_80", "80_plus"),
        default="below_60",
    )
    parser.add_argument(
        "--channel-plan",
        choices=("regular", "direct"),
        default="regular",
        help="Assumed plan type for Fees holdings.",
    )
    parser.add_argument(
        "--disposals",
        default=None,
        help="Override Tax disposals as category=rupees pairs.",
    )
    parser.add_argument("--model", default=None, help=f"Default: {llm_model()}")
    parser.add_argument(
        "--trace", action="store_true", help="Echo each tool call as it happens."
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Full CrewAI reasoning output."
    )
    parser.add_argument("--json", action="store_true", help="Print verdicts as JSON.")
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Emit newline-delimited JSON events as they happen, for the API bridge.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved brief(s) and exit without calling the model.",
    )
    parser.add_argument(
        "--list-categories", action="store_true", help="Print valid category keys and exit."
    )
    return parser


def _goal_brief(args: argparse.Namespace) -> GoalBrief:
    return GoalBrief(
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


def _render_feasibility(verdict: FeasibilityVerdict) -> list[str]:
    lines = [
        f"FEASIBILITY: {verdict.verdict.upper().replace('_', ' ')}",
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
    if verdict.recommended_moves:
        lines += ["", "RECOMMENDED MOVES:"] + [
            f"  - {move}" for move in verdict.recommended_moves
        ]
    lines += ["", "REASONING:", verdict.reasoning]
    return lines


def _render_statute(verdict: StatuteVerdict) -> list[str]:
    lines = [
        "EDGE",
        "",
        verdict.headline,
        "",
        f"  Total tax            {verdict.total_tax:,.0f}",
    ]
    if verdict.sections_applied:
        lines.append(f"  Sections             {', '.join(verdict.sections_applied)}")
    if verdict.staging_saves is not None:
        lines.append(f"  Staging saves        {verdict.staging_saves:,.0f}")
        lines.append(f"  Recommend staging    {verdict.recommend_staging}")
    lines += ["", "REASONING:", verdict.reasoning]
    return lines


def _render_channel(verdict: ChannelVerdict) -> list[str]:
    lines = [
        "CHANNEL",
        "",
        verdict.headline,
        "",
        f"  Annual drag          {verdict.annual_drag_rupees:,.0f}",
        f"  Drag / portfolio     {verdict.annual_drag_pct_of_portfolio * 100:.3f}%",
    ]
    if verdict.five_year_drag_rupees is not None:
        lines.append(f"  Five-year floor      {verdict.five_year_drag_rupees:,.0f}")
    if verdict.out_of_scope:
        lines += ["", "OUT OF SCOPE:"] + [f"  - {item}" for item in verdict.out_of_scope]
    if verdict.recommendations:
        lines += ["", "RECOMMENDATIONS:"] + [
            f"  - {item}" for item in verdict.recommendations
        ]
    lines += ["", "REASONING:", verdict.reasoning]
    return lines


def _render_reframe(verdict: ReframeVerdict) -> list[str]:
    lines = [
        "REFRAME",
        "",
        verdict.headline,
        "",
        f"  Preferred lever      {verdict.preferred_lever}",
    ]
    if verdict.slip_delay_months is not None:
        lines.append(f"  Slip delay           {verdict.slip_delay_months} months")
    if verdict.shrink_reachable_target is not None:
        lines.append(f"  Reachable target     {verdict.shrink_reachable_target:,.0f}")
    if verdict.topup_additional_monthly is not None:
        lines.append(f"  Top-up / month       {verdict.topup_additional_monthly:,.0f}")
    if verdict.levers:
        lines += ["", "LEVERS:"] + [f"  - {lever.summary}" for lever in verdict.levers]
    lines += ["", "REASONING:", verdict.reasoning]
    return lines


def _render_shared(verdict: SharedVerdict) -> list[str]:
    lines = [
        "SHARED",
        "",
        verdict.headline,
        "",
        f"  Best path            {verdict.best_path}",
        f"  Eligible lane        {verdict.highest_eligible_lane}",
        "",
        verdict.ranked_recommendation,
        "",
        verdict.adviser_blurb,
    ]
    if verdict.stances:
        lines += ["", "STANCES:"] + [
            f"  - [{s.posture}] {s.path}: {s.line}" for s in verdict.stances
        ]
    lines += ["", "REASONING:", verdict.reasoning]
    return lines


def _print_agent_json(run) -> None:
    print(
        json.dumps(
            {
                "agent": run.agent,
                "model": run.model,
                "tools_used": run.tools_used,
                "verdict": run.verdict.model_dump() if run.verdict else None,
                "raw": None if run.verdict else run.raw,
            },
            indent=2,
        )
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_categories:
        print("\n".join(category_keys()))
        return 0

    try:
        goal = _goal_brief(args)
    except ValueError as error:
        if args.stream:
            emit({"type": "error", "message": f"Invalid brief: {error}"})
            emit({"type": "status", "state": "halted", "label": "Invalid brief"})
            return 2
        print(f"Invalid brief: {error}", file=sys.stderr)
        return 2

    if args.stream:
        if args.agent == "planner":
            return stream_feasibility(goal, model=args.model)
        if args.agent == "tax":
            switch = SwitchBrief(
                purpose=f"Switch for: {goal.goal}",
                disposals=args.disposals
                or "debt_liquid=180000,equity_large_cap=120000",
                other_taxable_income=args.other_taxable_income,
                regime=args.regime,
                age_band=args.age_band,
                notes=args.notes,
            )
            return stream_statute(switch, model=args.model)
        if args.agent == "fees":
            return stream_channel(
                default_channel_brief(goal, plan=args.channel_plan), model=args.model
            )
        if args.agent == "rethink":
            return stream_reframe(
                default_reframe_brief(goal, None, None, None), model=args.model
            )
        if args.agent == "verdict":
            return stream_shared(
                default_shared_brief(goal, None, None, None, None), model=args.model
            )
        return stream_pipeline(
            goal,
            model=args.model,
            other_taxable_income=args.other_taxable_income,
            regime=args.regime,
            age_band=args.age_band,
            channel_plan=args.channel_plan,
        )

    if args.dry_run:
        print("=== Planner brief ===")
        print(goal.as_prompt_block())
        if args.agent in {"pipeline", "tax"}:
            preview = default_switch_brief(
                goal,
                None,
                other_taxable_income=args.other_taxable_income,
                regime=args.regime,
                age_band=args.age_band,
            )
            if args.disposals:
                preview = SwitchBrief(
                    purpose=preview.purpose,
                    disposals=args.disposals,
                    other_taxable_income=args.other_taxable_income,
                    regime=args.regime,
                    age_band=args.age_band,
                )
            print("\n=== Tax brief (pre-feasibility preview) ===")
            print(preview.as_prompt_block())
        if args.agent in {"pipeline", "fees"}:
            print("\n=== Fees brief ===")
            print(default_channel_brief(goal, plan=args.channel_plan).as_prompt_block())
        if args.agent in {"pipeline", "rethink"}:
            print("\n=== Rethink brief (pre-upstream preview) ===")
            print(default_reframe_brief(goal, None, None, None).as_prompt_block())
        if args.agent in {"pipeline", "verdict"}:
            print("\n=== Verdict brief (pre-upstream preview) ===")
            print(default_shared_brief(goal, None, None, None, None).as_prompt_block())
        print(f"\nModel that would run: {args.model or llm_model()}")
        return 0

    try:
        if args.agent == "planner":
            run = run_feasibility(
                goal, model=args.model, verbose=args.verbose, trace=args.trace
            )
            if args.json:
                _print_agent_json(run)
            else:
                print()
                if isinstance(run.verdict, FeasibilityVerdict):
                    print("\n".join(_render_feasibility(run.verdict)))
                else:
                    print(run.raw)
                print(f"\nTools called: {', '.join(run.tools_used) or 'none'}")
            return 0 if run.verdict else 1

        if args.agent == "tax":
            switch = SwitchBrief(
                purpose=f"Switch for: {goal.goal}",
                disposals=args.disposals
                or "debt_liquid=180000,equity_large_cap=270000",
                other_taxable_income=args.other_taxable_income,
                regime=args.regime,
                age_band=args.age_band,
                notes=args.notes,
            )
            run = run_statute(
                switch, model=args.model, verbose=args.verbose, trace=args.trace
            )
            if args.json:
                _print_agent_json(run)
            else:
                print()
                if isinstance(run.verdict, StatuteVerdict):
                    print("\n".join(_render_statute(run.verdict)))
                else:
                    print(run.raw)
                print(f"\nTools called: {', '.join(run.tools_used) or 'none'}")
            return 0 if run.verdict else 1

        if args.agent == "fees":
            run = run_channel(
                default_channel_brief(goal, plan=args.channel_plan),
                model=args.model,
                verbose=args.verbose,
                trace=args.trace,
            )
            if args.json:
                _print_agent_json(run)
            else:
                print()
                if isinstance(run.verdict, ChannelVerdict):
                    print("\n".join(_render_channel(run.verdict)))
                else:
                    print(run.raw)
                print(f"\nTools called: {', '.join(run.tools_used) or 'none'}")
            return 0 if run.verdict else 1

        if args.agent == "rethink":
            run = run_reframe(
                default_reframe_brief(goal, None, None, None),
                model=args.model,
                verbose=args.verbose,
                trace=args.trace,
            )
            if args.json:
                _print_agent_json(run)
            else:
                print()
                if isinstance(run.verdict, ReframeVerdict):
                    print("\n".join(_render_reframe(run.verdict)))
                else:
                    print(run.raw)
                print(f"\nTools called: {', '.join(run.tools_used) or 'none'}")
            return 0 if run.verdict else 1

        if args.agent == "verdict":
            run = run_shared(
                default_shared_brief(goal, None, None, None, None),
                model=args.model,
                verbose=args.verbose,
                trace=args.trace,
            )
            if args.json:
                _print_agent_json(run)
            else:
                print()
                if isinstance(run.verdict, SharedVerdict):
                    print("\n".join(_render_shared(run.verdict)))
                else:
                    print(run.raw)
                print(f"\nTools called: {', '.join(run.tools_used) or 'none'}")
            return 0 if run.verdict else 1

        pipeline = run_pipeline(
            goal,
            other_taxable_income=args.other_taxable_income,
            regime=args.regime,
            age_band=args.age_band,
            channel_plan=args.channel_plan,
            model=args.model,
            verbose=args.verbose,
            trace=args.trace,
        )
    except MissingCredentialsError as error:
        print(str(error), file=sys.stderr)
        return 3

    if args.json:
        payload = {
            "model": pipeline.model,
            "planner": {
                "tools_used": pipeline.feasibility.tools_used,
                "verdict": (
                    pipeline.feasibility.verdict.model_dump()
                    if pipeline.feasibility.verdict
                    else None
                ),
            },
            "tax": {
                "tools_used": pipeline.statute.tools_used if pipeline.statute else [],
                "verdict": (
                    pipeline.statute.verdict.model_dump()
                    if pipeline.statute and pipeline.statute.verdict
                    else None
                ),
            },
            "fees": {
                "tools_used": pipeline.channel.tools_used if pipeline.channel else [],
                "verdict": (
                    pipeline.channel.verdict.model_dump()
                    if pipeline.channel and pipeline.channel.verdict
                    else None
                ),
            },
            "rethink": {
                "tools_used": pipeline.reframe.tools_used if pipeline.reframe else [],
                "verdict": (
                    pipeline.reframe.verdict.model_dump()
                    if pipeline.reframe and pipeline.reframe.verdict
                    else None
                ),
            },
            "verdict": {
                "tools_used": pipeline.shared.tools_used if pipeline.shared else [],
                "verdict": (
                    pipeline.shared.verdict.model_dump()
                    if pipeline.shared and pipeline.shared.verdict
                    else None
                ),
            },
        }
        print(json.dumps(payload, indent=2))
    else:
        print()
        if isinstance(pipeline.feasibility.verdict, FeasibilityVerdict):
            print("\n".join(_render_feasibility(pipeline.feasibility.verdict)))
        else:
            print("FEASIBILITY failed:\n", pipeline.feasibility.raw)
        print("\n" + "=" * 60 + "\n")
        if pipeline.statute and isinstance(pipeline.statute.verdict, StatuteVerdict):
            print("\n".join(_render_statute(pipeline.statute.verdict)))
        else:
            print("EDGE failed:\n", pipeline.statute.raw if pipeline.statute else "")
        print("\n" + "=" * 60 + "\n")
        if pipeline.channel and isinstance(pipeline.channel.verdict, ChannelVerdict):
            print("\n".join(_render_channel(pipeline.channel.verdict)))
        else:
            print("CHANNEL failed:\n", pipeline.channel.raw if pipeline.channel else "")
        print("\n" + "=" * 60 + "\n")
        if pipeline.reframe and isinstance(pipeline.reframe.verdict, ReframeVerdict):
            print("\n".join(_render_reframe(pipeline.reframe.verdict)))
        else:
            print("REFRAME failed:\n", pipeline.reframe.raw if pipeline.reframe else "")
        print("\n" + "=" * 60 + "\n")
        if pipeline.shared and isinstance(pipeline.shared.verdict, SharedVerdict):
            print("\n".join(_render_shared(pipeline.shared.verdict)))
        else:
            print("SHARED failed:\n", pipeline.shared.raw if pipeline.shared else "")
        tools = ", ".join(c.name for c in pipeline.tool_calls) or "none"
        print(f"\nTools called: {tools}")

    return 0 if pipeline.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
