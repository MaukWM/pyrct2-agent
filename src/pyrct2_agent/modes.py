"""Game loop timing modes.

Each mode is a callable that returns a generator of RoundSnapshots.
The generator handles mode-specific timing; the caller handles end conditions.
"""

from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pyrct2.client import RCT2

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


@dataclass
class RoundSnapshot:
    """What happened during one round of the game loop."""

    actions: int


def _stream_actions(agent_executor: CompiledStateGraph, messages: list) -> Generator:
    """Yield messages from the LLM stream, appending to history."""
    for chunk in agent_executor.stream({"messages": messages}):
        for _node, updates in chunk.items():
            for msg in updates.get("messages", []):
                messages.append(msg)
                if msg.type == "ai":
                    if msg.content:
                        print(f"  Agent: {msg.content}")
                    for tc in msg.tool_calls:
                        print(f"  -> {tc['name']}({tc['args']})")
                elif msg.type == "tool":
                    print(f"  <- {msg.name}: {msg.content}")
                yield msg


@dataclass(frozen=True)
class TickPerAction:
    """Each action sees exactly ``ticks_per_action`` ticks of game progression.
    Ticks advance in a background thread while the LLM thinks, hiding latency.
    Deterministic — timing is independent of LLM speed."""

    ticks_per_action: int = 200

    def __call__(
        self,
        game: RCT2,
        agent_executor: CompiledStateGraph,
        messages: list,
    ) -> Generator[RoundSnapshot]:
        with ThreadPoolExecutor(max_workers=1) as tick_executor:
            while True:
                tick_future: Future | None = tick_executor.submit(
                    game.advance_ticks, self.ticks_per_action
                )
                action_count = 0

                for msg in _stream_actions(agent_executor, messages):
                    if msg.type == "ai" and msg.tool_calls:
                        if tick_future is not None:
                            tick_future.result()
                            tick_future = None
                        action_count += len(msg.tool_calls)
                    elif msg.type == "tool":
                        tick_future = tick_executor.submit(
                            game.advance_ticks, self.ticks_per_action
                        )

                if tick_future is not None:
                    tick_future.result()

                yield RoundSnapshot(actions=action_count)


@dataclass(frozen=True)
class PauseAndAct:
    """Game is paused while the agent acts. After ``actions_per_turn`` actions
    (or when the LLM stops), the game advances ``ticks_per_turn`` ticks."""

    ticks_per_turn: int = 1000
    actions_per_turn: int = 20

    def __call__(
        self,
        game: RCT2,
        agent_executor: CompiledStateGraph,
        messages: list,
    ) -> Generator[RoundSnapshot]:
        while True:
            action_count = 0

            for msg in _stream_actions(agent_executor, messages):
                if msg.type == "ai" and msg.tool_calls:
                    action_count += len(msg.tool_calls)
                    if action_count >= self.actions_per_turn:
                        break

            game.advance_ticks(self.ticks_per_turn)
            yield RoundSnapshot(actions=action_count)


@dataclass(frozen=True)
class RealTime:
    """Game runs continuously — never pauses. Non-deterministic: LLM latency
    means variable game time passes between actions."""

    def __call__(
        self,
        game: RCT2,
        agent_executor: CompiledStateGraph,
        messages: list,
    ) -> Generator[RoundSnapshot]:
        while True:
            game.unpause()
            action_count = 0

            for msg in _stream_actions(agent_executor, messages):
                if msg.type == "ai" and msg.tool_calls:
                    action_count += len(msg.tool_calls)

            game.pause()
            yield RoundSnapshot(actions=action_count)


Mode = TickPerAction | PauseAndAct | RealTime
