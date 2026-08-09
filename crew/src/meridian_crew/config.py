"""Runtime configuration and the modelling assumptions the tools share."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
DATA_DIR = PACKAGE_ROOT / "data"

NAV_HISTORY_PATH = DATA_DIR / "nav_history.json"
PRODUCTS_PATH = DATA_DIR / "products.json"

load_dotenv(PROJECT_ROOT / ".env")

DEFAULT_MODEL = "openrouter/openai/gpt-5-mini"

# Trailing CAGR is a backward-looking number. Quoting it as a forward return
# over-promises on the asset classes whose recent run has been strongest, so
# each asset class gets a haircut before it reaches the projection maths.
# These are planning assumptions, not forecasts -- tune them deliberately.
FORWARD_RETURN_HAIRCUT = {
    "equity": 0.20,
    "hybrid": 0.12,
    "debt": 0.05,
    "commodity": 0.25,
}

# Applied when a category carries an asset class we have no haircut for.
DEFAULT_HAIRCUT = 0.15


def llm_model() -> str:
    return os.getenv("MERIDIAN_LLM_MODEL", DEFAULT_MODEL)


def has_llm_credentials() -> bool:
    return any(
        os.getenv(key)
        for key in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")
    )


def assumed_forward_return(trailing_cagr: float, asset_class: str) -> float:
    haircut = FORWARD_RETURN_HAIRCUT.get(asset_class, DEFAULT_HAIRCUT)
    return round(trailing_cagr * (1.0 - haircut), 6)
