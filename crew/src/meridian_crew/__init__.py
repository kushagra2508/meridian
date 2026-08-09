"""CrewAI Feasibility agent for the Meridian wealth platform.

Importing `crewai` creates its storage directory as a side effect, so the
environment is pointed at a project-local path before that happens. Otherwise
CrewAI writes to `~/Library/Application Support/crew` and the working state of a
demo ends up outside the repository.
"""

from __future__ import annotations

import os
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

os.environ.setdefault("CREWAI_STORAGE_DIR", str(_PROJECT_ROOT / ".crewai"))
# Nothing here needs usage analytics, and a blocked telemetry call adds seconds
# to every run. Override in the environment if you want it back.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

__all__ = ["__version__"]

__version__ = "0.1.0"
