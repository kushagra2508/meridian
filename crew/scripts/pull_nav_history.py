#!/usr/bin/env python3
"""Rebuild `data/nav_history.json` from the public mfapi.in NAV archive.

Selection is deliberately strict, because a mis-bucketed scheme silently
poisons every downstream projection. For each category we:

  1. filter the full AMFI scheme list by a name pattern,
  2. download each candidate's NAV series,
  3. keep it only if mfapi's own ``scheme_category`` confirms the bucket,
  4. stop at three schemes from three different fund houses,
  5. report the median metric across those schemes.

    python scripts/pull_nav_history.py                          # all categories
    python scripts/pull_nav_history.py --only equity_mid_cap    # patch one

The output is committed. Tools never touch the network at run time.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from meridian_crew.config import NAV_HISTORY_PATH, assumed_forward_return  # noqa: E402

API_ROOT = "https://api.mfapi.in"
TRADING_DAYS_PER_YEAR = 252
DAYS_PER_YEAR = 365.25

# How far from the exact anniversary date we accept a NAV observation.
ANNIVERSARY_TOLERANCE_DAYS = 20

# Minimum NAV observations before a scheme is worth measuring (~1 trading year).
MIN_OBSERVATIONS = 250

SCHEMES_PER_CATEGORY = 3
MAX_CANDIDATE_FETCHES = 15

# Stops one AMC's index-fund range from consuming the whole fetch budget.
MAX_CANDIDATES_PER_HOUSE = 3

# A scheme whose newest NAV is older than this has been merged or wound up.
# Without the check, defunct funds (IDBI, Sahara) contribute frozen returns.
STALE_AFTER_DAYS = 45

# Roughly five years of trading days. Schemes above this can produce a 5y CAGR,
# so they are preferred, but a shorter series is accepted rather than dropping a
# whole category.
PREFERRED_OBSERVATIONS = 1250

# Ranked so that candidate fetches go to large, long-running fund houses first.
# The universe has ~37k schemes and most of the tail is tiny or defunct; the
# alternative is measuring a category from whichever fund has the shortest name.
PREFERRED_HOUSES = (
    "hdfc",
    "icici",
    "sbi",
    "nippon",
    "kotak",
    "aditya birla",
    "axis",
    "uti",
    "mirae",
    "dsp",
    "parag parikh",
    "ppfas",
    "motilal",
    "tata",
    "canara",
    "franklin",
    "edelweiss",
    "invesco",
    "bandhan",
    "sundaram",
)

# Plan variants that are not the plain growth option a planner would buy.
GLOBAL_EXCLUDE = re.compile(
    r"idcw|dividend|payout|reinvest|bonus|institutional|segregated|unclaimed"
    r"|quarterly|half\s*yearly|monthly|weekly|daily|annual|series|fixed\s*period"
    r"|interval|retail",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CategorySpec:
    label: str
    asset_class: str
    # Hard gate: must appear in mfapi's own scheme_category for the scheme.
    expect_category: str
    name_pattern: str
    name_exclude: str = ""
    notes: str = ""
    _compiled: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def matches_name(self, name: str) -> bool:
        if GLOBAL_EXCLUDE.search(name):
            return False
        lowered = name.lower()
        if "growth" not in lowered:
            return False
        # Direct plans only. Regular plans carry distribution commission, so
        # mixing the two would compare returns net of different expense ratios.
        if "direct" not in lowered:
            return False
        if not re.search(self.name_pattern, name, re.IGNORECASE):
            return False
        if self.name_exclude and re.search(self.name_exclude, name, re.IGNORECASE):
            return False
        return True

    def confirms(self, scheme_category: str) -> bool:
        return self.expect_category.lower() in scheme_category.lower()


CATEGORY_SPECS: dict[str, CategorySpec] = {
    "equity_large_cap": CategorySpec(
        label="Equity - Large Cap",
        asset_class="equity",
        expect_category="Large Cap Fund",
        name_pattern=r"large\s*cap|bluechip|blue\s*chip",
        name_exclude=r"\bus\b|global|international|nasdaq|emerging",
    ),
    "equity_flexi_cap": CategorySpec(
        label="Equity - Flexi Cap",
        asset_class="equity",
        expect_category="Flexi Cap Fund",
        name_pattern=r"flexi\s*cap",
    ),
    "equity_mid_cap": CategorySpec(
        label="Equity - Mid Cap",
        asset_class="equity",
        expect_category="Mid Cap Fund",
        name_pattern=r"mid\s*cap|midcap|emerging\s+equity",
        name_exclude=r"large\s*(&|and)?\s*mid|small",
    ),
    "equity_small_cap": CategorySpec(
        label="Equity - Small Cap",
        asset_class="equity",
        expect_category="Small Cap Fund",
        name_pattern=r"small\s*cap|smallcap",
    ),
    "equity_elss": CategorySpec(
        label="Equity - ELSS",
        asset_class="equity",
        expect_category="ELSS",
        name_pattern=r"elss|tax\s*saver|long\s*term\s*equity",
    ),
    "index_nifty50": CategorySpec(
        label="Index - Nifty 50",
        asset_class="equity",
        expect_category="Index Fund",
        # (?!0) keeps "Nifty 500" out of a Nifty 50 bucket.
        name_pattern=r"nifty\s*50(?!0)",
        name_exclude=r"next\s*50|equal\s*weight|value\s*20|arbitrage|midcap|bank",
        notes="Nifty 50 only; Next 50, Nifty 500 and factor variants are excluded.",
    ),
    "hybrid_aggressive": CategorySpec(
        label="Hybrid - Aggressive",
        asset_class="hybrid",
        expect_category="Aggressive Hybrid Fund",
        name_pattern=r"hybrid|equity\s*(&|and)\s*debt|prudence|balanced",
        name_exclude=r"advantage|conservative|arbitrage|multi\s*asset",
    ),
    "hybrid_balanced_advantage": CategorySpec(
        label="Hybrid - Balanced Advantage",
        asset_class="hybrid",
        expect_category="Balanced Advantage",
        name_pattern=r"balanced\s*advantage|dynamic\s*asset",
    ),
    "debt_corporate_bond": CategorySpec(
        label="Debt - Corporate Bond",
        asset_class="debt",
        expect_category="Corporate Bond Fund",
        name_pattern=r"corporate\s*bond",
    ),
    "debt_short_duration": CategorySpec(
        label="Debt - Short Duration",
        asset_class="debt",
        expect_category="Short Duration Fund",
        name_pattern=r"short\s*(term|duration)",
        name_exclude=r"gilt|ultra|low\s*duration",
    ),
    "debt_gilt": CategorySpec(
        label="Debt - Gilt",
        asset_class="debt",
        expect_category="Gilt Fund",
        name_pattern=r"gilt|g-?sec|government\s*securit",
        name_exclude=r"short|10\s*year|constant\s*maturity",
    ),
    "debt_liquid": CategorySpec(
        label="Debt - Liquid",
        asset_class="debt",
        expect_category="Liquid Fund",
        name_pattern=r"liquid",
        name_exclude=r"overnight|ultra",
    ),
    "commodity_gold": CategorySpec(
        label="Commodity - Gold",
        asset_class="commodity",
        expect_category="FoF",
        name_pattern=r"gold",
        name_exclude=r"silver|multi\s*asset|goldman",
        notes="Gold fund-of-funds; AMFI files these under 'Other Scheme - FoF Domestic'.",
    ),
}


def _session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = "meridian-crew/0.1 (nav_history builder)"
    return session


def fetch_scheme_list(session: requests.Session) -> list[dict[str, Any]]:
    response = session.get(f"{API_ROOT}/mf", timeout=120)
    response.raise_for_status()
    return response.json()


def fetch_series(session: requests.Session, code: int) -> dict[str, Any]:
    response = session.get(f"{API_ROOT}/mf/{code}", timeout=120)
    response.raise_for_status()
    return response.json()


def _house_of(name: str) -> tuple[int, str]:
    """(preference rank, house key) for a scheme name."""
    lowered = name.lower()
    for index, house in enumerate(PREFERRED_HOUSES):
        if house in lowered:
            return index, house
    return len(PREFERRED_HOUSES), lowered.split()[0] if lowered.split() else lowered


def rank_candidates(
    schemes: list[dict[str, Any]], spec: CategorySpec
) -> list[dict[str, Any]]:
    """Name-matched schemes ordered by fund house, then by brevity.

    A shorter name is a good proxy for the plain vanilla plan: the exotic
    variants earn their length from the qualifiers bolted onto the end. Each
    house is capped so one AMC's index-fund range cannot eat the whole fetch
    budget before a second house is tried.
    """
    matched = [s for s in schemes if spec.matches_name(s["schemeName"])]
    matched.sort(key=lambda s: (_house_of(s["schemeName"]), len(s["schemeName"])))

    per_house: dict[str, int] = {}
    capped: list[dict[str, Any]] = []
    for scheme in matched:
        house = _house_of(scheme["schemeName"])[1]
        if per_house.get(house, 0) >= MAX_CANDIDATES_PER_HOUSE:
            continue
        per_house[house] = per_house.get(house, 0) + 1
        capped.append(scheme)
    return capped


def parse_points(raw: list[dict[str, str]]) -> list[tuple[date, float]]:
    """mfapi returns newest-first dd-mm-yyyy strings; normalise to oldest-first."""
    points: list[tuple[date, float]] = []
    for row in raw:
        try:
            nav = float(row["nav"])
        except (TypeError, ValueError):
            continue
        if nav <= 0:
            continue
        points.append((datetime.strptime(row["date"], "%d-%m-%Y").date(), nav))
    points.sort(key=lambda item: item[0])
    return points


def _years_ago(anchor: date, years: float) -> date:
    return anchor - timedelta(days=round(years * DAYS_PER_YEAR))


def nav_near(points: list[tuple[date, float]], target: date) -> float | None:
    """NAV observed closest to `target`, if one exists within tolerance."""
    best: tuple[int, float] | None = None
    for observed, nav in points:
        gap = abs((observed - target).days)
        if best is None or gap < best[0]:
            best = (gap, nav)
    if best is None or best[0] > ANNIVERSARY_TOLERANCE_DAYS:
        return None
    return best[1]


def cagr(points: list[tuple[date, float]], years: int) -> float | None:
    latest_date, latest_nav = points[-1]
    target = _years_ago(latest_date, years)
    if target < points[0][0]:
        return None
    past_nav = nav_near(points, target)
    if past_nav is None:
        return None
    return (latest_nav / past_nav) ** (1.0 / years) - 1.0


def annualised_volatility(points: list[tuple[date, float]], years: int = 3) -> float | None:
    cutoff = _years_ago(points[-1][0], years)
    window = [nav for observed, nav in points if observed >= cutoff]
    if len(window) < 60:
        return None
    log_returns = [math.log(window[i] / window[i - 1]) for i in range(1, len(window))]
    if len(log_returns) < 30:
        return None
    return statistics.stdev(log_returns) * math.sqrt(TRADING_DAYS_PER_YEAR)


def max_drawdown(points: list[tuple[date, float]], years: int = 5) -> float | None:
    cutoff = _years_ago(points[-1][0], years)
    window = [nav for observed, nav in points if observed >= cutoff]
    if len(window) < 60:
        return None
    peak = window[0]
    worst = 0.0
    for nav in window:
        peak = max(peak, nav)
        worst = min(worst, nav / peak - 1.0)
    return worst


def scheme_metrics(payload: dict[str, Any]) -> dict[str, Any] | None:
    points = parse_points(payload.get("data") or [])
    if len(points) < MIN_OBSERVATIONS:
        return None
    meta = payload.get("meta", {})
    return {
        "code": int(meta.get("scheme_code", 0)),
        "name": " ".join((meta.get("scheme_name") or "").split()),
        "fund_house": (meta.get("fund_house") or "").strip(),
        "scheme_category": (meta.get("scheme_category") or "").strip(),
        "as_of": points[-1][0].isoformat(),
        "observations": len(points),
        "cagr_1y": cagr(points, 1),
        "cagr_3y": cagr(points, 3),
        "cagr_5y": cagr(points, 5),
        "volatility_annualised": annualised_volatility(points),
        "max_drawdown_5y": max_drawdown(points),
    }


def _median(values: list[float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(statistics.median(present), 6)


def build_category(
    session: requests.Session,
    key: str,
    spec: CategorySpec,
    all_schemes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = rank_candidates(all_schemes, spec)
    print(f"  {key}: {len(candidates)} name matches")

    stale_before = (date.today() - timedelta(days=STALE_AFTER_DAYS)).isoformat()
    passing: list[dict[str, Any]] = []
    for candidate in candidates[:MAX_CANDIDATE_FETCHES]:
        # Enough long-history schemes in hand; stop spending requests.
        if sum(1 for s in passing if s["observations"] >= PREFERRED_OBSERVATIONS) >= (
            SCHEMES_PER_CATEGORY
        ):
            break
        try:
            metrics = scheme_metrics(fetch_series(session, candidate["schemeCode"]))
        except requests.RequestException as error:
            print(f"    ! {candidate['schemeCode']} failed: {error}")
            continue
        time.sleep(0.2)
        if metrics is None:
            continue
        if not spec.confirms(metrics["scheme_category"]):
            print(
                f"    - rejected {metrics['name']}: filed as "
                f"{metrics['scheme_category']!r}"
            )
            continue
        if metrics["as_of"] < stale_before:
            print(f"    - rejected {metrics['name']}: last NAV {metrics['as_of']}")
            continue
        passing.append(metrics)

    # Longest history wins, one scheme per fund house.
    accepted: list[dict[str, Any]] = []
    seen_houses: set[str] = set()
    for metrics in sorted(passing, key=lambda s: -s["observations"]):
        if len(accepted) >= SCHEMES_PER_CATEGORY:
            break
        if metrics["fund_house"] in seen_houses:
            continue
        seen_houses.add(metrics["fund_house"])
        print(f"    + {metrics['name']} ({metrics['observations']} NAVs)")
        accepted.append(metrics)

    if not accepted:
        return None

    trailing_5y = _median([s["cagr_5y"] for s in accepted])
    trailing_3y = _median([s["cagr_3y"] for s in accepted])
    basis_window = "5y" if trailing_5y is not None else "3y"
    basis_cagr = trailing_5y if trailing_5y is not None else trailing_3y
    if basis_cagr is None:
        return None

    return {
        "label": spec.label,
        "asset_class": spec.asset_class,
        "as_of": max(s["as_of"] for s in accepted),
        "cagr_1y": _median([s["cagr_1y"] for s in accepted]),
        "cagr_3y": trailing_3y,
        "cagr_5y": trailing_5y,
        "volatility_annualised": _median([s["volatility_annualised"] for s in accepted]),
        "max_drawdown_5y": _median([s["max_drawdown_5y"] for s in accepted]),
        "assumed_forward_return": assumed_forward_return(basis_cagr, spec.asset_class),
        "forward_return_basis": (
            f"median trailing {basis_window} CAGR of {len(accepted)} scheme(s), "
            f"less the {spec.asset_class} haircut"
        ),
        "notes": spec.notes or None,
        "schemes": [
            {
                "code": s["code"],
                "name": s["name"],
                "fund_house": s["fund_house"],
                "scheme_category": s["scheme_category"],
            }
            for s in accepted
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", nargs="*", choices=sorted(CATEGORY_SPECS), default=None)
    parser.add_argument("--out", type=Path, default=NAV_HISTORY_PATH)
    args = parser.parse_args()

    selected = args.only or sorted(CATEGORY_SPECS)
    session = _session()

    print("fetching AMFI scheme list ...")
    all_schemes = fetch_scheme_list(session)
    print(f"  {len(all_schemes)} schemes\n")

    categories: dict[str, Any] = {}
    if args.only and args.out.exists():
        categories = json.loads(args.out.read_text(encoding="utf-8")).get("categories", {})

    failed: list[str] = []
    for key in selected:
        built = build_category(session, key, CATEGORY_SPECS[key], all_schemes)
        if built is None:
            print(f"    ! skipped {key}: no scheme passed the category check")
            failed.append(key)
            continue
        categories[key] = built

    if not categories:
        print("nothing built; refusing to write an empty dataset", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "source": "https://api.mfapi.in (AMFI daily NAV archive)",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "method": {
            "selection": (
                "name-matched, then confirmed against mfapi's own scheme_category; "
                "up to 3 schemes from 3 different fund houses per category"
            ),
            "cagr": "point-to-point on NAV, anniversary matched within 20 days",
            "volatility_annualised": "stdev of daily log returns over 3y * sqrt(252)",
            "max_drawdown_5y": "worst peak-to-trough on NAV over 5y",
            "aggregation": "median across the accepted schemes per category",
        },
        "categories": dict(sorted(categories.items())),
    }
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote {len(categories)} categories to {args.out}")
    if failed:
        print(f"failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
