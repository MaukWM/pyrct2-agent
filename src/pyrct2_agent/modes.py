"""Game loop timing modes.

Each mode is a callable that yields StepSnapshots — one per LLM invocation.
The LLM makes exactly one tool call per step. Modes control when game ticks
advance relative to steps.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from pyrct2.client import RCT2

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langchain_core.tools import BaseTool

# How many turns a park message stays visible to the agent.
_MESSAGE_TTL: int = 4

# Default context budget in estimated tokens.
DEFAULT_MAX_HISTORY_TOKENS: int = 30_000

# Rough chars-per-token ratio (conservative — overestimates tokens slightly).
_CHARS_PER_TOKEN: float = 3.5


@dataclass
class StepSnapshot:
    """What happened during one agent step (one LLM call)."""

    action: str | None = None  # tool name called, or None if LLM didn't act
    args: dict[str, Any] = field(default_factory=dict)
    result: str | None = None


# ── Token estimation & truncation ───────────────────────────────────


def _estimate_message_tokens(msg) -> int:
    """Estimate token count for a single LangChain message."""
    chars = len(msg.content or "")
    for tc in getattr(msg, "tool_calls", []):
        chars += len(tc["name"]) + len(json.dumps(tc["args"]))
    return max(1, int(chars / _CHARS_PER_TOKEN))


def _truncate_messages(messages: list, max_tokens: int) -> None:
    """Drop oldest messages until history fits within *max_tokens*.

    Mutates in-place.  Always keeps at least the last message.
    """
    if max_tokens <= 0:
        messages.clear()
        return

    # Walk from newest to oldest, accumulating token cost.
    budget = max_tokens
    keep_count = 0
    for msg in reversed(messages):
        cost = _estimate_message_tokens(msg)
        if budget - cost < 0 and keep_count > 0:
            break
        budget -= cost
        keep_count += 1

    keep_from = len(messages) - keep_count

    if keep_from > 0:
        # Never leave an orphaned ToolMessage at the start — the API requires
        # every ToolMessage to follow the AIMessage that requested it.
        while keep_from < len(messages) and isinstance(
            messages[keep_from], ToolMessage
        ):
            keep_from += 1

        kept = len(messages) - keep_from
        total_before = len(messages)
        del messages[:keep_from]
        print(f"  [truncated {total_before - kept} messages, kept {kept}]")


# ── Park message tracking ──────────────────────────────────────────


class MessageTracker:
    """Shows each park message for up to _MESSAGE_TTL turns, then drops it."""

    def __init__(self, game: RCT2) -> None:
        self._game = game
        self._seen: set[tuple[str, int, int]] = set()
        # key = (text, month, day), value = turns remaining
        self._active: dict[tuple[str, int, int], int] = {}

    def tick(self) -> list[str]:
        """Advance one turn: ingest new messages, decrement TTLs, return visible texts."""
        for m in self._game.state.park_messages():
            key = (m.text, m.month, m.day)
            if key not in self._seen:
                self._seen.add(key)
                self._active[key] = _MESSAGE_TTL

        # Collect visible texts, then decrement. Remove expired.
        visible = [text for (text, _, _), ttl in self._active.items() if ttl > 0]
        expired = []
        for key in self._active:
            self._active[key] -= 1
            if self._active[key] <= 0:
                expired.append(key)
        for key in expired:
            del self._active[key]

        return visible


# ── Single-tool step ────────────────────────────────────────────────


def _step(
    llm: BaseChatModel,
    tools: list[BaseTool],
    tool_map: dict[str, BaseTool],
    system_prompt: str,
    messages: list,
    max_history_tokens: int,
    *,
    msg_tracker: MessageTracker | None = None,
) -> StepSnapshot:
    """One LLM invocation → at most one tool call → result appended.

    Returns a StepSnapshot describing what happened.
    """
    _truncate_messages(messages, max_history_tokens)

    # Build the full message list: system prompt + conversation history.
    llm_input = [SystemMessage(content=system_prompt)] + messages

    # Append park notifications as the very last thing the LLM sees.
    # These are ephemeral — not stored in conversation history.
    # Each message appears for a few turns then fades out.
    if msg_tracker is not None:
        texts = msg_tracker.tick()
        if texts:
            note = (
                "[Park notifications — recent game messages. "
                "Each fades after a few turns. "
                "Do not repeatedly react to the same message.]\n"
                + "\n".join(f"- {t}" for t in texts)
            )
            llm_input.append(SystemMessage(content=note))
            print(f"  [notifications: {len(texts)} park messages]")
    history_tokens = sum(_estimate_message_tokens(m) for m in messages)
    prompt_tokens = _estimate_message_tokens(llm_input[0])
    print(
        f"  [context: ~{prompt_tokens + history_tokens} tokens (prompt {prompt_tokens} + history {history_tokens})]"
    )

    # Bind tools so the LLM knows what's available.
    response: AIMessage = llm.bind_tools(tools).invoke(llm_input)
    messages.append(response)

    if response.content:
        print(f"  Agent: {response.content}")

    if not response.tool_calls:
        return StepSnapshot()

    # Execute all tool calls. Parallel tool calls should be disabled at the
    # LLM level (e.g. parallel_tool_calls=False) so models naturally send one,
    # but if multiple arrive we execute them all rather than silently dropping.
    last_action = None
    last_args: dict[str, Any] = {}
    last_result = None
    for tc in response.tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]
        print(f"  -> {tool_name}({tool_args})")

        tool = tool_map.get(tool_name)
        if tool is None:
            result_str = f"Unknown tool: {tool_name}"
        else:
            result_str = str(tool.invoke(tool_args))

        print(f"  <- {tool_name}: {result_str}")
        messages.append(ToolMessage(content=result_str, tool_call_id=tc["id"]))
        last_action = tool_name
        last_args = tool_args
        last_result = result_str

    return StepSnapshot(action=last_action, args=last_args, result=last_result)


# ── Modes ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class TickPerAction:
    """Game advances a fixed number of ticks after each agent step.
    Deterministic — timing is independent of LLM speed."""

    ticks_per_action: int = 200
    max_history_tokens: int = DEFAULT_MAX_HISTORY_TOKENS

    def __call__(
        self,
        game: RCT2,
        llm: BaseChatModel,
        tools: list[BaseTool],
        tool_map: dict[str, BaseTool],
        system_prompt: str,
        messages: list,
    ) -> Generator[StepSnapshot]:
        tracker = MessageTracker(game)
        while True:
            game.advance_ticks(self.ticks_per_action)
            snapshot = _step(
                llm,
                tools,
                tool_map,
                system_prompt,
                messages,
                self.max_history_tokens,
                msg_tracker=tracker,
            )
            yield snapshot


@dataclass(frozen=True)
class PauseAndAct:
    """Agent takes up to ``actions_per_turn`` steps while paused,
    then the game advances ``ticks_per_turn`` ticks."""

    ticks_per_turn: int = 2_500
    actions_per_turn: int = 5
    max_history_tokens: int = DEFAULT_MAX_HISTORY_TOKENS

    def __call__(
        self,
        game: RCT2,
        llm: BaseChatModel,
        tools: list[BaseTool],
        tool_map: dict[str, BaseTool],
        system_prompt: str,
        messages: list,
    ) -> Generator[StepSnapshot]:
        tracker = MessageTracker(game)
        while True:
            for _ in range(self.actions_per_turn):
                snapshot = _step(
                    llm,
                    tools,
                    tool_map,
                    system_prompt,
                    messages,
                    self.max_history_tokens,
                    msg_tracker=tracker,
                )
                yield snapshot
                if snapshot.action is None:
                    break  # LLM chose to stop acting
            game.advance_ticks(self.ticks_per_turn)


@dataclass(frozen=True)
class RealTime:
    """Game runs continuously — never pauses. Non-deterministic: LLM latency
    means variable game time passes between steps."""

    max_history_tokens: int = DEFAULT_MAX_HISTORY_TOKENS

    def __call__(
        self,
        game: RCT2,
        llm: BaseChatModel,
        tools: list[BaseTool],
        tool_map: dict[str, BaseTool],
        system_prompt: str,
        messages: list,
    ) -> Generator[StepSnapshot]:
        tracker = MessageTracker(game)
        game.unpause()
        while True:
            snapshot = _step(
                llm,
                tools,
                tool_map,
                system_prompt,
                messages,
                self.max_history_tokens,
                msg_tracker=tracker,
            )
            yield snapshot


Mode = TickPerAction | PauseAndAct | RealTime
