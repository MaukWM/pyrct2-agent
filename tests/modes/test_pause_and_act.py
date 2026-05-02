"""Tests for PauseAndAct mode."""

from __future__ import annotations

import pytest

from conftest import get_ticks, patch_step, step_snap

from pyrct2_agent.modes import PauseAndAct


class TestPauseAndAct:
    @pytest.mark.parametrize("ticks_per_turn", [10, 25, 50])
    def test_advances_ticks_after_turn(self, game, ticks_per_turn):
        """Ticks advance once after a full turn of actions."""
        actions_per_turn = 3
        mode = PauseAndAct(
            ticks_per_turn=ticks_per_turn, actions_per_turn=actions_per_turn
        )
        # Need enough snaps for one full turn + first step of next turn
        # (the advance_ticks fires between turns).
        snaps = [step_snap(action="place_ride") for _ in range(actions_per_turn + 1)]
        with patch_step(snaps):
            gen = mode(game, None, [], {}, "", [])
            ticks_before = get_ticks(game)
            # Consume one full turn + first step of next turn.
            # advance_ticks fires after turn 1 completes, before turn 2 starts.
            for _ in range(actions_per_turn + 1):
                next(gen)
            delta = get_ticks(game) - ticks_before
        # One completed turn = one advance_ticks call.
        assert ticks_per_turn <= delta <= ticks_per_turn + 1

    def test_stops_turn_when_no_action(self, game):
        """Turn ends early if LLM returns no tool call."""
        mode = PauseAndAct(ticks_per_turn=10, actions_per_turn=5)
        snaps = [step_snap(action="place_ride"), step_snap()]  # second step = no action
        with patch_step(snaps):
            gen = mode(game, None, [], {}, "", [])
            s1 = next(gen)
            s2 = next(gen)
        assert s1.action == "place_ride"
        assert s2.action is None
