"""pyrct2-agent — LLM agent that plays RollerCoaster Tycoon 2."""

from pyrct2_agent.agent import Agent
from pyrct2_agent.modes import Mode, PauseAndAct, RealTime, TickPerAction
from pyrct2_agent.result import Outcome, RunResult

__all__ = [
    "Agent",
    "Mode",
    "Outcome",
    "PauseAndAct",
    "RealTime",
    "RunResult",
    "TickPerAction",
]
