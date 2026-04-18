"""Shared fixtures and helpers for pyrct2-agent tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

import pytest
from pyrct2.client import RCT2
from pyrct2.scenarios import Scenario


# ---------------------------------------------------------------------------
# Real game fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def game():
    """Launch a fresh headless game instance."""
    with RCT2.launch(Scenario.TEST_PARK) as g:
        yield g


@pytest.fixture
def game_with_guests():
    """Launch a headless game with guests already in the park."""
    with RCT2.launch(Scenario.TEST_PARK_WITH_GUESTS) as g:
        yield g


# ---------------------------------------------------------------------------
# Fake messages — minimal objects matching what _stream_actions yields
# ---------------------------------------------------------------------------


@dataclass
class Msg:
    """Minimal message matching what _stream_actions yields."""

    type: str
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    name: str = ""


def ai(content: str = "", tool_calls: int = 0) -> Msg:
    """Fake AI message, optionally with N tool calls."""
    calls = [{"name": f"tool_{i}", "args": {}} for i in range(tool_calls)]
    return Msg(type="ai", content=content, tool_calls=calls)


def tool(name: str = "noop", content: str = "ok") -> Msg:
    """Fake tool result message."""
    return Msg(type="tool", content=content, name=name)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_ticks(game: RCT2) -> int:
    """Get engine tick count from game status."""
    return game.get_status()["payload"]["date"]["engineTicks"]


def patch_stream(turns: list[list[Msg]]):
    """Patch _stream_actions to yield pre-scripted turns.

    Each call to _stream_actions pops one turn from the list.
    When exhausted, yields an AI message with no tool calls.
    """
    turns = list(turns)

    def fake_stream(_executor, _messages):
        if turns:
            yield from turns.pop(0)
        else:
            yield ai("done")

    return patch("pyrct2_agent.modes._stream_actions", side_effect=fake_stream)
