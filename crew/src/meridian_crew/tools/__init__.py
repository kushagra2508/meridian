"""The four tools the Feasibility agent carries."""

from crewai.tools import BaseTool

from .goal_solver import GoalSolverTool
from .horizon_filter import HorizonFilterTool
from .nav_history import NavHistoryTool
from .reallocation_search import ReallocationSearchTool


def feasibility_tools() -> list[BaseTool]:
    """Fresh instances, in the order the agent is expected to reach for them."""
    return [
        NavHistoryTool(),
        GoalSolverTool(),
        ReallocationSearchTool(),
        HorizonFilterTool(),
    ]


__all__ = [
    "GoalSolverTool",
    "HorizonFilterTool",
    "NavHistoryTool",
    "ReallocationSearchTool",
    "feasibility_tools",
]
