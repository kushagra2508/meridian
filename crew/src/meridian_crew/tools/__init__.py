"""Tool packs for each Meridian agent."""

from crewai.tools import BaseTool

from .debt_slab import DebtSlabTool
from .drag_calc import DragCalcTool
from .fy_stager import FyStagerTool
from .goal_solver import GoalSolverTool
from .horizon_filter import HorizonFilterTool
from .ltcg_112a import Ltcg112aTool
from .nav_history import NavHistoryTool
from .reallocation_search import ReallocationSearchTool
from .scope_guard import ScopeGuardTool
from .stcg_111a import Stcg111aTool
from .surcharge_band import SurchargeBandTool
from .ter_lookup import TerLookupTool


def feasibility_tools() -> list[BaseTool]:
    """Fresh instances, in the order the agent is expected to reach for them."""
    return [
        NavHistoryTool(),
        GoalSolverTool(),
        ReallocationSearchTool(),
        HorizonFilterTool(),
    ]


def statute_tools() -> list[BaseTool]:
    return [
        Ltcg112aTool(),
        Stcg111aTool(),
        DebtSlabTool(),
        SurchargeBandTool(),
        FyStagerTool(),
    ]


def channel_tools() -> list[BaseTool]:
    return [
        TerLookupTool(),
        DragCalcTool(),
        ScopeGuardTool(),
    ]


__all__ = [
    "DebtSlabTool",
    "DragCalcTool",
    "FyStagerTool",
    "GoalSolverTool",
    "HorizonFilterTool",
    "Ltcg112aTool",
    "NavHistoryTool",
    "ReallocationSearchTool",
    "ScopeGuardTool",
    "Stcg111aTool",
    "SurchargeBandTool",
    "TerLookupTool",
    "channel_tools",
    "feasibility_tools",
    "statute_tools",
]
