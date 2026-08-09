"""The statute engine the five Statute tools share.

Every rate, threshold and section string is read from `data/tax_rules.json`
rather than written into the code, so a Budget is a data change and the tools
can always quote the section they priced under. Nothing here rounds a rule into
a rule of thumb: an exemption that applies once a year is modelled as applying
once a year, which is the whole reason `fy_stager` has anything to find.

A disposal crosses the tool boundary as a list of declared objects for the same
reason an allocation does -- see `common.py`. Direct Python callers may still
pass dicts or a compact `category=value` string.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any, Iterable, Literal

from pydantic import BaseModel, Field

from ..config import DEFAULT_EMBEDDED_GAIN_PCT, DEFAULT_HOLDING_MONTHS
from ..datasets import tax_rules

Regime = Literal["new", "old"]
AgeBand = Literal["below_60", "60_to_80", "80_plus"]

EQUITY_ORIENTED = "equity_oriented"
SPECIFIED_MUTUAL_FUND = "specified_mutual_fund"
OTHER_ASSET = "other_asset"

# Sections whose tax carries the capped surcharge rate rather than the full one.
SPECIAL_RATE_SECTIONS = frozenset({"111A", "112A", "112"})

DISPOSAL_FORMAT_HINT = (
    "Pass disposals as a list of objects, e.g. "
    '[{"category": "debt_liquid", "redemption_value": 180000, '
    '"holding_months": 40}]. `category` is a nav_history key and '
    "`redemption_value` is the rupee amount being sold."
)

_CATEGORY_KEYS = ("category", "key", "name", "asset", "asset_class", "from_category")
_VALUE_KEYS = ("redemption_value", "value", "amount", "rupees", "proceeds", "sale_value")


class Disposal(BaseModel):
    """One sale leg of a proposed switch."""

    category: str = Field(
        description="The nav_history category key being sold, e.g. 'debt_liquid'."
    )
    redemption_value: float = Field(
        ge=0, description="Rupees being redeemed from this category."
    )
    cost_basis: float | None = Field(
        default=None,
        description=(
            "What those units cost. Omit it and the gain is taken from "
            "embedded_gain_pct instead."
        ),
    )
    embedded_gain_pct: float | None = Field(
        default=None,
        description=(
            "Percent of redemption_value that is unrealised gain. Used only when "
            f"cost_basis is absent; defaults to {DEFAULT_EMBEDDED_GAIN_PCT:g}%."
        ),
    )
    holding_months: float | None = Field(
        default=None,
        ge=0,
        description=(
            "How long the units have been held. This decides long versus short "
            f"term, so supply it when known; defaults to {DEFAULT_HOLDING_MONTHS:g}."
        ),
    )
    acquired_before_apr_2023: bool = Field(
        default=False,
        description=(
            "True for debt units bought before 1 April 2023, which sit outside "
            "section 50AA and can still be long-term."
        ),
    )


class TaxComponent(BaseModel):
    """One line of tax, already computed, waiting for surcharge and cess."""

    section: str = Field(
        description="The section it was charged under: '112A', '111A', '112' or 'slab'."
    )
    amount: float = Field(ge=0, description="Tax in rupees, before surcharge and cess.")


def _pick(record: dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if name in record:
            return record[name]
    return None


def _parse_pairs_string(text: str) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for chunk in re.split(r"[,;\n]+", text):
        if not chunk.strip():
            continue
        key, separator, value = chunk.partition("=")
        if not separator:
            key, separator, value = chunk.partition(":")
        if not separator:
            raise ValueError(
                f"Could not read '{chunk.strip()}' as a disposal. " + DISPOSAL_FORMAT_HINT
            )
        parsed.append(
            {
                "category": key.strip().strip("\"'"),
                "redemption_value": float(value.strip().replace(",", "")),
            }
        )
    return parsed


def coerce_disposals(value: Any) -> Any:
    """Normalise any disposal shape into `list[{category, redemption_value, ...}]`."""
    if value is None:
        return None

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.startswith(("{", "[")):
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                value = _parse_pairs_string(text)
        else:
            value = _parse_pairs_string(text)

    if isinstance(value, dict):
        # A mapping of category -> rupees, which is how a model paraphrases it.
        if all(isinstance(item, (int, float)) for item in value.values()):
            return [
                {"category": key, "redemption_value": amount}
                for key, amount in value.items()
            ]
        value = [value]

    if isinstance(value, list):
        normalised: list[Any] = []
        for item in value:
            if isinstance(item, Disposal):
                normalised.append(item)
            elif isinstance(item, dict):
                category = _pick(item, _CATEGORY_KEYS)
                amount = _pick(item, _VALUE_KEYS)
                if category is None or amount is None:
                    raise ValueError(
                        f"Could not read the disposal {item!r}. " + DISPOSAL_FORMAT_HINT
                    )
                record = {**item, "category": category, "redemption_value": amount}
                normalised.append(record)
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                normalised.append({"category": item[0], "redemption_value": item[1]})
            else:
                raise ValueError(
                    f"Could not read the disposal {item!r}. " + DISPOSAL_FORMAT_HINT
                )
        return normalised

    return value


def _read(entry: Any, name: str, default: Any = None) -> Any:
    """Read a field whether the entry arrived as a model or as a plain dict.

    CrewAI validates against `args_schema` and then dumps the arguments back to
    primitives, so a declared `list[Disposal]` reaches `_run` as a list of dicts.
    """
    if isinstance(entry, dict):
        value = entry.get(name, default)
    else:
        value = getattr(entry, name, default)
    return default if value is None else value


class PricedDisposal(BaseModel):
    """A disposal after the statute has been applied to it."""

    category: str
    redemption_value: float
    gain: float
    holding_months: float
    long_term: bool
    section: str
    treatment: str
    basis: str
    assumptions: list[str] = Field(default_factory=list)


def _gain_of(entry: Any) -> tuple[float, list[str]]:
    redemption = float(_read(entry, "redemption_value", 0.0))
    cost_basis = _read(entry, "cost_basis")
    if cost_basis is not None:
        return redemption - float(cost_basis), []

    gain_pct = _read(entry, "embedded_gain_pct")
    if gain_pct is None:
        return (
            redemption * DEFAULT_EMBEDDED_GAIN_PCT / 100.0,
            [
                f"No cost basis given for {_read(entry, 'category', '?')}; assumed "
                f"{DEFAULT_EMBEDDED_GAIN_PCT:g}% of the redemption is gain."
            ],
        )
    return redemption * float(gain_pct) / 100.0, []


def classify(entry: Any) -> PricedDisposal:
    """Decide which section a disposal falls under, and what the gain is."""
    from ..datasets import tax_treatment

    rules = tax_rules()["capital_gains"]
    category = str(_read(entry, "category", ""))
    treatment = tax_treatment(category)
    gain, assumptions = _gain_of(entry)

    months = _read(entry, "holding_months")
    if months is None:
        months = DEFAULT_HOLDING_MONTHS
        assumptions.append(
            f"No holding period given for {category}; assumed "
            f"{DEFAULT_HOLDING_MONTHS:g} months."
        )
    months = float(months)

    if treatment == EQUITY_ORIENTED:
        threshold = rules["equity_ltcg_112a"]["min_holding_months"]
        long_term = months > threshold
        rule = rules["equity_ltcg_112a"] if long_term else rules["equity_stcg_111a"]
    elif treatment == SPECIFIED_MUTUAL_FUND:
        legacy = rules["legacy_debt_ltcg"]
        long_term = bool(_read(entry, "acquired_before_apr_2023", False)) and (
            months > legacy["min_holding_months"]
        )
        rule = legacy if long_term else rules["specified_mutual_fund"]
    else:
        other = rules["other_asset_ltcg"]
        long_term = months > other["min_holding_months"]
        rule = other if long_term else rules["specified_mutual_fund"]

    section = rule["section"] if rule.get("treatment") != "slab" else "slab"

    caveat = tax_rules().get("category_caveats", {}).get(category)
    if caveat:
        assumptions.append(f"{category}: {caveat}")

    return PricedDisposal(
        category=category,
        redemption_value=float(_read(entry, "redemption_value", 0.0)),
        gain=round(gain, 2),
        holding_months=months,
        long_term=long_term,
        section=section,
        treatment=treatment,
        basis=rule["basis"],
        assumptions=assumptions,
    )


def price_all(disposals: Iterable[Any]) -> list[PricedDisposal]:
    return [classify(entry) for entry in disposals or []]


def _basic_exemption(regime: str, age_band: str) -> float:
    slabs = tax_rules()["slabs"][regime]
    if slabs.get("age_bands"):
        return float(slabs["basic_exemption_by_age"][age_band])
    return float(slabs["basic_exemption"])


def _effective_bands(regime: str, age_band: str) -> list[tuple[float, float, float]]:
    """Slab bands as (lower, upper, rate), with the basic exemption applied.

    The old regime raises the exemption with age rather than restating the
    whole table, so the boundaries are clamped upward instead of hard-coded per
    age band.
    """
    exemption = _basic_exemption(regime, age_band)
    bands: list[tuple[float, float, float]] = []
    lower = 0.0
    for band in tax_rules()["slabs"][regime]["bands"]:
        upper = math.inf if band["upto"] is None else float(band["upto"])
        low, high = max(lower, exemption), max(upper, exemption)
        if high > low:
            bands.append((low, high, float(band["rate"])))
        lower = upper
    return bands


def slab_tax(income: float, regime: Regime = "new", age_band: AgeBand = "below_60") -> float:
    """Income tax on slab-rate income, before rebate, surcharge and cess."""
    if income <= 0:
        return 0.0
    total = 0.0
    for low, high, rate in _effective_bands(regime, age_band):
        if income <= low:
            break
        total += (min(income, high) - low) * rate
    return total


def rebate_87a(tax_on_slab_income: float, total_income: float, regime: Regime) -> float:
    """Section 87A rebate. Nil once total income clears the ceiling.

    The rebate is set against tax on ordinary income only, which is why it is
    applied here and never to the 111A/112A charge.
    """
    rule = tax_rules()["rebate_87a"][regime]
    if total_income > float(rule["income_ceiling"]):
        return 0.0
    return min(tax_on_slab_income, float(rule["max_rebate"]))


def slab_tax_after_rebate(
    slab_income: float,
    total_income: float,
    regime: Regime = "new",
    age_band: AgeBand = "below_60",
) -> float:
    gross = slab_tax(slab_income, regime, age_band)
    return max(0.0, gross - rebate_87a(gross, total_income, regime))


def marginal_slab_tax(
    extra_income: float,
    other_income: float,
    special_rate_income: float = 0.0,
    regime: Regime = "new",
    age_band: AgeBand = "below_60",
) -> float:
    """What adding `extra_income` to slab income actually costs.

    Computed as the difference between two full assessments rather than by
    reading off a marginal rate, so a gain that straddles two bands -- or that
    pushes total income past the 87A ceiling and forfeits the rebate -- is
    priced correctly.
    """
    if extra_income <= 0:
        return 0.0
    before = slab_tax_after_rebate(
        other_income, other_income + special_rate_income, regime, age_band
    )
    after = slab_tax_after_rebate(
        other_income + extra_income,
        other_income + extra_income + special_rate_income,
        regime,
        age_band,
    )
    return max(0.0, after - before)


def basic_exemption_headroom(
    other_income: float, regime: Regime = "new", age_band: AgeBand = "below_60"
) -> float:
    """Unused basic exemption a resident may set against 111A/112A gains."""
    if not tax_rules().get("basic_exemption_absorption", {}).get("available"):
        return 0.0
    return max(0.0, _basic_exemption(regime, age_band) - max(0.0, other_income))


def surcharge_rate(total_income: float, regime: Regime) -> tuple[float, float | None, str]:
    """(rate, band threshold, label) for a total income."""
    for band in tax_rules()["surcharge"]["bands"][regime]:
        above = float(band["above"])
        upto = math.inf if band["upto"] is None else float(band["upto"])
        if above < total_income <= upto:
            ceiling = "" if band["upto"] is None else f" and up to Rs {upto:,.0f}"
            return (
                float(band["rate"]),
                above,
                f"Income above Rs {above:,.0f}{ceiling}: surcharge at "
                f"{float(band['rate']) * 100:g}%.",
            )
    return 0.0, None, "Total income is below the surcharge threshold of Rs 50,00,000."


def is_special_rate(section: str) -> bool:
    return section.upper().replace(" ", "") in SPECIAL_RATE_SECTIONS


class SurchargeResult(BaseModel):
    total_income: float
    regime: str
    band: str
    surcharge_rate: float = Field(description="Rate on ordinary tax, as a decimal.")
    surcharge_rate_on_special_income: float = Field(
        description="Capped rate applied to tax under sections 111A, 112A and 112."
    )
    tax_before_surcharge: float
    surcharge: float
    marginal_relief: float
    cess: float
    total_tax: float
    effective_rate_on_income: float
    notes: list[str]


def apply_surcharge_and_cess(
    total_income: float,
    components: Iterable[Any],
    regime: Regime = "new",
    age_band: AgeBand = "below_60",
    special_rate_income: float = 0.0,
) -> SurchargeResult:
    """Add surcharge, marginal relief and cess to a set of tax components."""
    rules = tax_rules()
    cap = float(rules["surcharge"]["special_rate_cap"])
    cess_rate = float(rules["cess"]["rate"])

    special_tax = 0.0
    ordinary_tax = 0.0
    for component in components or []:
        section = str(_read(component, "section", "slab"))
        amount = float(_read(component, "amount", 0.0))
        if is_special_rate(section):
            special_tax += amount
        else:
            ordinary_tax += amount

    tax_before = special_tax + ordinary_tax
    rate, threshold, band = surcharge_rate(total_income, regime)
    capped = min(rate, cap)
    surcharge = ordinary_tax * rate + special_tax * capped

    notes: list[str] = [band]
    if rate > cap and special_tax > 0:
        notes.append(
            f"Surcharge on the {', '.join(sorted(SPECIAL_RATE_SECTIONS))} charge is "
            f"held at {cap * 100:g}% under the proviso, against {rate * 100:g}% on "
            "the rest."
        )

    # Marginal relief: crossing a surcharge threshold must never cost more than
    # the income that crossed it. The excess is taken out of ordinary income
    # first, because the last rupee earned is the one that crossed.
    relief = 0.0
    if threshold is not None and surcharge > 0:
        excess = total_income - threshold
        ordinary_income = max(0.0, total_income - special_rate_income)
        tax_at_threshold = (
            slab_tax_after_rebate(
                max(0.0, ordinary_income - excess), threshold, regime, age_band
            )
            + special_tax
        )
        relief = max(0.0, (tax_before + surcharge) - (tax_at_threshold + excess))
        if relief > 0:
            surcharge = max(0.0, surcharge - relief)
            notes.append(
                f"Marginal relief of Rs {relief:,.0f} applied: the surcharge cannot "
                f"exceed the income above Rs {threshold:,.0f}."
            )

    cess = (tax_before + surcharge) * cess_rate
    total = tax_before + surcharge + cess

    return SurchargeResult(
        total_income=round(total_income, 2),
        regime=regime,
        band=band,
        surcharge_rate=rate,
        surcharge_rate_on_special_income=capped,
        tax_before_surcharge=round(tax_before, 2),
        surcharge=round(surcharge, 2),
        marginal_relief=round(relief, 2),
        cess=round(cess, 2),
        total_tax=round(total, 2),
        effective_rate_on_income=(
            round(total / total_income, 6) if total_income > 0 else 0.0
        ),
        notes=notes + [f"{rules['cess']['name']} at {cess_rate * 100:g}% on tax plus surcharge."],
    )


class Charge(BaseModel):
    """One section's charge, priced."""

    section: str
    label: str
    gain: float
    exemption_applied: float = 0.0
    taxable_gain: float
    rate: float | None = Field(
        default=None, description="Flat rate, or null when the charge is at slab rates."
    )
    tax: float
    basis: str
    notes: list[str] = Field(default_factory=list)


def equity_ltcg_charge(
    gain: float,
    exemption_already_used: float = 0.0,
    basic_exemption_absorbed: float = 0.0,
) -> Charge:
    """Section 112A. The annual exemption is why timing a switch matters."""
    rule = tax_rules()["capital_gains"]["equity_ltcg_112a"]
    annual = float(rule["annual_exemption"])
    remaining = max(0.0, annual - max(0.0, exemption_already_used))
    absorbed = min(max(0.0, gain), max(0.0, basic_exemption_absorbed))
    exemption = min(gain - absorbed, remaining)
    taxable = max(0.0, gain - absorbed - exemption)
    rate = float(rule["rate"])

    notes = [
        f"Rs {annual:,.0f} of section 112A gains are exempt each financial year; "
        f"Rs {remaining:,.0f} of that was still available."
    ]
    if absorbed > 0:
        notes.append(
            f"Rs {absorbed:,.0f} of unused basic exemption was set against these "
            "gains first."
        )
    if gain > 0 and taxable == 0:
        notes.append("The whole gain falls inside the exemptions, so nothing is payable.")

    return Charge(
        section=rule["section"],
        label=rule["label"],
        gain=round(gain, 2),
        exemption_applied=round(absorbed + exemption, 2),
        taxable_gain=round(taxable, 2),
        rate=rate,
        tax=round(taxable * rate, 2),
        basis=rule["basis"],
        notes=notes,
    )


def equity_stcg_charge(gain: float, basic_exemption_absorbed: float = 0.0) -> Charge:
    """Section 111A. A flat rate with no annual exemption of its own."""
    rule = tax_rules()["capital_gains"]["equity_stcg_111a"]
    taxable = max(0.0, gain - max(0.0, basic_exemption_absorbed))
    rate = float(rule["rate"])
    notes = ["Section 111A carries no annual exemption; the first rupee of gain is taxed."]
    if basic_exemption_absorbed > 0:
        notes.append(
            f"Rs {basic_exemption_absorbed:,.0f} of unused basic exemption was set "
            "against these gains."
        )
    return Charge(
        section=rule["section"],
        label=rule["label"],
        gain=round(gain, 2),
        exemption_applied=round(min(gain, max(0.0, basic_exemption_absorbed)), 2),
        taxable_gain=round(taxable, 2),
        rate=rate,
        tax=round(taxable * rate, 2),
        basis=rule["basis"],
        notes=notes,
    )


def legacy_ltcg_charge(gain: float) -> Charge:
    """Section 112 at 12.5% without indexation, for pre-April-2023 debt units."""
    rule = tax_rules()["capital_gains"]["legacy_debt_ltcg"]
    rate = float(rule["rate"])
    return Charge(
        section=rule["section"],
        label=rule["label"],
        gain=round(gain, 2),
        taxable_gain=round(max(0.0, gain), 2),
        rate=rate,
        tax=round(max(0.0, gain) * rate, 2),
        basis=rule["basis"],
        notes=["Indexation was withdrawn for transfers on or after 23 July 2024."],
    )


def slab_charge(
    gain: float,
    other_taxable_income: float,
    special_rate_income: float = 0.0,
    regime: Regime = "new",
    age_band: AgeBand = "below_60",
) -> Charge:
    """Section 50AA: the gain joins ordinary income and is taxed at the margin."""
    rule = tax_rules()["capital_gains"]["specified_mutual_fund"]
    tax = marginal_slab_tax(
        gain, other_taxable_income, special_rate_income, regime, age_band
    )
    notes = [
        "Priced as the difference between two full assessments, so a gain that "
        "straddles two slabs -- or that forfeits the section 87A rebate -- is "
        "costed correctly.",
    ]
    if gain > 0:
        notes.append(
            f"Effective rate on this gain: {tax / gain * 100:.2f}% under the "
            f"{regime} regime."
        )
    return Charge(
        section="slab",
        label=rule["label"],
        gain=round(gain, 2),
        taxable_gain=round(max(0.0, gain), 2),
        rate=None,
        tax=round(tax, 2),
        basis=rule["basis"],
        notes=notes,
    )


def assess(
    disposals: Iterable[Any],
    other_taxable_income: float = 0.0,
    regime: Regime = "new",
    age_band: AgeBand = "below_60",
    exemption_already_used: float = 0.0,
    absorb_basic_exemption: bool = True,
) -> tuple[list[Charge], list[PricedDisposal]]:
    """Price a whole switch across every section it touches.

    Ordering matters and is deliberate: any unused basic exemption goes against
    the 111A gains first, because 20% is the dearer of the two special rates.
    """
    priced = price_all(disposals)

    ltcg = sum(d.gain for d in priced if d.section == "112A")
    stcg = sum(d.gain for d in priced if d.section == "111A")
    legacy = sum(d.gain for d in priced if d.section == "112")
    slab_gains = sum(d.gain for d in priced if d.section == "slab")

    headroom = (
        basic_exemption_headroom(other_taxable_income + slab_gains, regime, age_band)
        if absorb_basic_exemption
        else 0.0
    )
    to_stcg = min(headroom, max(0.0, stcg))
    to_ltcg = min(headroom - to_stcg, max(0.0, ltcg))

    charges: list[Charge] = []
    if stcg > 0:
        charges.append(equity_stcg_charge(stcg, basic_exemption_absorbed=to_stcg))
    if ltcg > 0:
        charges.append(
            equity_ltcg_charge(
                ltcg,
                exemption_already_used=exemption_already_used,
                basic_exemption_absorbed=to_ltcg,
            )
        )
    if legacy > 0:
        charges.append(legacy_ltcg_charge(legacy))
    if slab_gains > 0:
        charges.append(
            slab_charge(
                slab_gains,
                other_taxable_income,
                special_rate_income=ltcg + stcg + legacy,
                regime=regime,
                age_band=age_band,
            )
        )
    return charges, priced


def money(amount: float, currency: str = "INR") -> str:
    return f"{currency} {amount:,.0f}"
