"""Shared fixtures and helpers for pyrct2-agent tests."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

import pytest
from pyrct2.client import RCT2
from pyrct2.scenarios import Scenario

from pyrct2_agent.modes import StepSnapshot


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
# Helpers
# ---------------------------------------------------------------------------


def get_ticks(game: RCT2) -> int:
    """Get engine tick count from game status."""
    return game.get_status()["payload"]["date"]["engineTicks"]


def step_snap(
    action: str | None = None, args: dict[str, Any] | None = None
) -> StepSnapshot:
    """Create a StepSnapshot for testing."""
    return StepSnapshot(action=action, args=args or {}, result="ok" if action else None)


@contextmanager
def patch_step(snapshots: list[StepSnapshot]):
    """Patch _step to return pre-scripted StepSnapshots.

    When the list is exhausted, returns no-action snapshots.
    """
    snapshots = list(snapshots)

    def fake_step(_llm, _tools, _tool_map, _system_prompt, _messages, _max_tokens):
        if snapshots:
            return snapshots.pop(0)
        return StepSnapshot()

    with patch("pyrct2_agent.modes._step", side_effect=fake_step) as mock:
        yield mock
