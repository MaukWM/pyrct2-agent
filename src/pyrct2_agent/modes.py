"""Game loop timing modes — pure config, no logic.

Each mode defines how game time flows relative to agent actions:
- TickPerAction: each action triggers exactly N ticks (deterministic)
- PauseAndAct: agent takes N actions while paused, then M ticks advance
- RealTime: game runs continuously, agent acts under time pressure
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TickPerAction:
    """Each agent action sees exactly ``ticks_per_action`` ticks of game
    progression. Ticks advance in a background thread while the LLM thinks,
    hiding latency. Deterministic — timing is independent of LLM speed."""

    ticks_per_action: int = 200


@dataclass(frozen=True)
class PauseAndAct:
    """Game is paused while the agent thinks and acts. After
    ``actions_per_turn`` actions (or when the LLM stops), the game advances
    ``ticks_per_turn`` ticks in one shot, then pauses again."""

    ticks_per_turn: int = 1000
    actions_per_turn: int = 20


@dataclass(frozen=True)
class RealTime:
    """Game runs continuously — never pauses. The agent acts under real time
    pressure. Non-deterministic: LLM latency means variable game time passes
    between actions."""


# Union type for mode parameters.
Mode = TickPerAction | PauseAndAct | RealTime
