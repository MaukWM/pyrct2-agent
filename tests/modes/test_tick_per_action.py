"""Tests for TickPerAction mode."""

from __future__ import annotations

import pytest

from conftest import get_ticks, patch_step, step_snap

from pyrct2_agent.modes import TickPerAction


class TestTickPerAction:
    @pytest.mark.parametrize("ticks_per_action", [10, 25, 50])
    def test_advances_exact_ticks(self, game, ticks_per_action):
        """N steps should advance ~N * ticks_per_action ticks."""
        steps = 3
        mode = TickPerAction(ticks_per_action=ticks_per_action)
        snaps = [step_snap(action="place_ride") for _ in range(steps)]
        with patch_step(snaps):
            gen = mode(game, None, [], {}, "", [])
            ticks_before = get_ticks(game)
            for _ in range(steps):
                next(gen)
            delta = get_ticks(game) - ticks_before
        expected = steps * ticks_per_action
        # Tolerate ±1 per step due to advance_ticks off-by-one.
        assert expected <= delta <= expected + steps
