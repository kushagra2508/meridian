"""Verdict parsing and blending helpers for the Planner tools.

Allocations cross the tool boundary as a **list of explicit objects**, not as a
mapping. A mapping keyed by category can only be described in JSON Schema through
`additionalProperties`, which strict function-calling does not support: the model
is handed an object with no declared keys, cannot name one, and sends `{}`. A list
of `{category, weight_pct}` records declares every field, so it survives the round
trip. Internally the maths still works on a plain dict, so the conversion happens
once at the edge.

Direct Python callers and tests can still pass a dict, a JSON string, or the
compact `key=weight,key=weight` form; all of them are normalised here first.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from pydantic import BaseModel, Field

from ..datasets import categories, forward_returns, volatilities

Allocation = dict[str, float]

WEIGHT_SUM_TOLERANCE = 0.5  # percentage points

ALLOCATION_FORMAT_HINT = (
    "Pass it as a list of objects, e.g. "
    '[{"category": "equity_large_cap", "weight_pct": 60}, '
    '{"category": "debt_short_duration", "weight_pct": 40}]. '
    "Use the category keys from nav_history and make the weights sum to 100."
)

# Alternative key names seen from models that paraphrase the schema.
_CATEGORY_KEYS = ("category", "key", "name", "asset", "asset_class")
_WEIGHT_KEYS = ("weight_pct", "weight", "pct", "percent", "percentage", "value")


class CategoryWeight(BaseModel):
    """One line of an allocation."""

    category: str = Field(
        description="A nav_history category key, e.g. 'equity_large_cap'."
    )
    weight_pct: float = Field(
        description="Percent of the portfolio held in this category."
    )


class AssetClassCap(BaseModel):
    """A ceiling on one asset class."""

    asset_class: str = Field(description="One of: equity, hybrid, debt, commodity.")
    max_pct: float = Field(description="Maximum percent of the portfolio.")


def _parse_pairs_string(text: str) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for chunk in re.split(r"[,;\n]+", text):
        if not chunk.strip():
            continue
        key, separator, weight = chunk.partition("=")
        if not separator:
            key, separator, weight = chunk.partition(":")
        if not separator:
            raise ValueError(
                f"Could not read '{chunk.strip()}' as an allocation entry. "
                + ALLOCATION_FORMAT_HINT
            )
        parsed[key.strip().strip("\"'")] = float(weight.strip().rstrip("%"))
    return parsed


def _pick(record: dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        if name in record:
            return record[name]
    return None


def coerce_allocation(value: Any) -> Any:
    """Normalise any allocation shape into `list[{category, weight_pct}]`."""
    if value is None:
        return None

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.startswith("{") or text.startswith("["):
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                value = _parse_pairs_string(text)
        else:
            value = _parse_pairs_string(text)

    if isinstance(value, dict):
        return [
            {"category": key, "weight_pct": weight} for key, weight in value.items()
        ]

    if isinstance(value, list):
        normalised: list[Any] = []
        for item in value:
            if isinstance(item, CategoryWeight):
                normalised.append(item)
            elif isinstance(item, dict):
                category = _pick(item, _CATEGORY_KEYS)
                weight = _pick(item, _WEIGHT_KEYS)
                if category is None or weight is None:
                    raise ValueError(
                        f"Could not read the allocation entry {item!r}. "
                        + ALLOCATION_FORMAT_HINT
                    )
                normalised.append({"category": category, "weight_pct": weight})
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                normalised.append({"category": item[0], "weight_pct": item[1]})
            else:
                raise ValueError(
                    f"Could not read the allocation entry {item!r}. "
                    + ALLOCATION_FORMAT_HINT
                )
        return normalised

    return value


def coerce_caps(value: Any) -> Any:
    """Normalise asset-class ceilings into `list[{asset_class, max_pct}]`."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        value = json.loads(text) if text.startswith(("{", "[")) else _parse_pairs_string(text)
    if isinstance(value, dict):
        return [
            {"asset_class": key, "max_pct": cap} for key, cap in value.items()
        ]
    if isinstance(value, list):
        out: list[Any] = []
        for item in value:
            if isinstance(item, (AssetClassCap, str)):
                out.append(item)
            elif isinstance(item, dict):
                asset_class = _pick(item, ("asset_class", "class", "key", "name"))
                cap = _pick(item, ("max_pct", "max", "cap", "pct", "value"))
                if asset_class is None or cap is None:
                    raise ValueError(f"Could not read the cap entry {item!r}.")
                out.append({"asset_class": asset_class, "max_pct": cap})
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                out.append({"asset_class": item[0], "max_pct": item[1]})
            else:
                raise ValueError(f"Could not read the cap entry {item!r}.")
        return out
    return value


def _field(entry: Any, name: str, alternatives: Iterable[str]) -> Any:
    """Read a field whether the entry arrived as a model or as a plain dict.

    CrewAI validates tool arguments against `args_schema` and then dumps them
    back to primitives before calling `_run`, so a declared `list[CategoryWeight]`
    arrives as a list of dicts. Both shapes have to work.
    """
    if isinstance(entry, dict):
        value = _pick(entry, (name, *alternatives))
        if value is None:
            raise ValueError(f"Missing '{name}' in {entry!r}.")
        return value
    return getattr(entry, name)


def weights_to_mapping(weights: list[CategoryWeight] | list[dict] | None) -> Allocation:
    """Collapse the wire format into the mapping the maths uses."""
    mapping: Allocation = {}
    for entry in weights or []:
        category = _field(entry, "category", _CATEGORY_KEYS)
        weight = _field(entry, "weight_pct", _WEIGHT_KEYS)
        mapping[category] = mapping.get(category, 0.0) + float(weight)
    return mapping


def caps_to_mapping(caps: list[AssetClassCap] | list[dict] | None) -> dict[str, float]:
    return {
        _field(entry, "asset_class", ("class", "key", "name")): float(
            _field(entry, "max_pct", ("max", "cap", "pct", "value"))
        )
        for entry in caps or []
    }


def coerce_allocation_to_mapping(value: Any) -> Allocation:
    """Normalise any allocation shape straight to a mapping.

    For callers that hold an allocation as data rather than as a tool argument,
    where the list-of-objects wire format buys nothing.
    """
    return weights_to_mapping(coerce_allocation(value))


def validate_allocation(allocation: Allocation) -> Allocation:
    """Check every key is a known category and the weights look like percentages."""
    if not allocation:
        raise ValueError("The allocation was empty. " + ALLOCATION_FORMAT_HINT)

    known = categories()
    unknown = [key for key in allocation if key not in known]
    if unknown:
        raise ValueError(
            f"Unknown categories {unknown}. Call nav_history first; valid keys are: "
            f"{', '.join(sorted(known))}."
        )
    if any(weight < 0 for weight in allocation.values()):
        raise ValueError("Allocation weights cannot be negative.")

    total = sum(allocation.values())
    if total <= 0:
        raise ValueError("Allocation weights sum to zero. " + ALLOCATION_FORMAT_HINT)
    if abs(total - 100.0) > WEIGHT_SUM_TOLERANCE:
        raise ValueError(
            f"Allocation weights sum to {total:.2f}, expected 100. Weights are "
            "percentages of the portfolio."
        )
    return {key: float(weight) for key, weight in allocation.items()}


def blended_return(allocation: Allocation) -> float:
    """Weight-average forward return of an allocation, as a decimal."""
    returns = forward_returns()
    total = sum(allocation.values())
    return sum(weight * returns[key] for key, weight in allocation.items()) / total


def blended_volatility_upper_bound(allocation: Allocation) -> float:
    """Weight-average volatility.

    This is an upper bound, not an estimate: it is what you would see if every
    category moved in lockstep. Real blended volatility is lower because equity
    and debt are far from perfectly correlated. Computing the true figure needs
    a correlation matrix, which this dataset does not carry.
    """
    vols = volatilities()
    total = sum(allocation.values())
    return sum(weight * (vols[key] or 0.0) for key, weight in allocation.items()) / total


def asset_class_weights(allocation: Allocation) -> dict[str, float]:
    table = categories()
    grouped: dict[str, float] = {}
    for key, weight in allocation.items():
        asset_class = table[key]["asset_class"]
        grouped[asset_class] = grouped.get(asset_class, 0.0) + weight
    return grouped


def as_pct(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.{digits}f}%"
