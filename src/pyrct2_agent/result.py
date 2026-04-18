"""Run result — what agent.run() returns."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Outcome(StrEnum):
    SCENARIO_COMPLETE = "scenario_complete"
    MAX_TICKS = "max_ticks"
    MAX_ACTIONS = "max_actions"
    ERROR = "error"


@dataclass
class RunResult:
    """Basic outcome of an agent run. Will grow with score curves,
    action logs, and cost tracking in later phases."""

    outcome: Outcome
    total_actions: int = 0
    total_ticks: int = 0
    wall_time_seconds: float = 0.0
