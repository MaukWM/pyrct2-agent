"""Default prompts for the agent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyrct2_agent.modes import PauseAndAct, RealTime, TickPerAction

if TYPE_CHECKING:
    from pyrct2_agent.modes import Mode

DEFAULT_SYSTEM_PROMPT = "You are playing RollerCoaster Tycoon 2."


def _time_description(mode: Mode) -> str:
    if isinstance(mode, TickPerAction):
        return f"The game advances {mode.ticks_per_action} ticks after each action."
    if isinstance(mode, PauseAndAct):
        return (
            f"The game is paused while you act ({mode.actions_per_turn} actions per turn). "
            f"After your turn, {mode.ticks_per_turn} ticks advance."
        )
    if isinstance(mode, RealTime):
        return "The game runs in real time. Time passes while you think."
    raise ValueError(f"Unknown mode: {mode}")


def build_system_prompt(mode: Mode, custom_prompt: str | None = None) -> str:
    """Build the full system prompt.

    Time description is always prepended — it's a mechanical fact
    about the mode, not optional guidance.
    """
    body = custom_prompt if custom_prompt is not None else DEFAULT_SYSTEM_PROMPT
    return body + "\n\n" + _time_description(mode)
