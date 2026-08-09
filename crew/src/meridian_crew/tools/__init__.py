"""Tool packs for each Meridian agent."""

from crewai.tools import BaseTool

from .debt_slab import DebtSlabTool
from .drag_calc import DragCalcTool
from .eligibility_gate import EligibilityGateTool
from .fy_stager import FyStagerTool
from .goal_solver import GoalSolverTool
from .horizon_filter import HorizonFilterTool
from .ledger import LedgerTool
from .ltcg_112a import Ltcg112aTool
from .monthly_topup import MonthlyTopupTool
from .nav_history import NavHistoryTool
from .price_options import PriceOptionsTool
from .prose_writer import ProseWriterTool
from .reallocation_search import ReallocationSearchTool
from .scope_guard import ScopeGuardTool
from .shrink_target import ShrinkTargetTool
from .slip_year import SlipYearTool
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


def reframe_tools() -> list[BaseTool]:
    return [
        SlipYearTool(),
        ShrinkTargetTool(),
        MonthlyTopupTool(),
        PriceOptionsTool(),
    ]


def shared_tools() -> list[BaseTool]:
    return [
        EligibilityGateTool(),
        LedgerTool(),
        ProseWriterTool(),
    ]


__all__ = [
    "DebtSlabTool",
    "DragCalcTool",
    "EligibilityGateTool",
    "FyStagerTool",
    "GoalSolverTool",
    "HorizonFilterTool",
    "LedgerTool",
    "Ltcg112aTool",
    "MonthlyTopupTool",
    "NavHistoryTool",
    "PriceOptionsTool",
    "ProseWriterTool",
    "ReallocationSearchTool",
    "ScopeGuardTool",
    "ShrinkTargetTool",
    "SlipYearTool",
    "Stcg111aTool",
    "SurchargeBandTool",
    "TerLookupTool",
    "channel_tools",
    "feasibility_tools",
    "reframe_tools",
    "shared_tools",
    "statute_tools",
]
