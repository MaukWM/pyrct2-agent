"""Tests for PauseAndAct mode."""

from __future__ import annotations

import pytest

from conftest import ai, get_ticks, patch_stream

from pyrct2_agent.modes import PauseAndAct


class TestPauseAndAct:
    @pytest.mark.parametrize("ticks_per_turn", [10, 25, 50])
    def test_advances_exact_ticks(self, game, ticks_per_turn):
        """N rounds should advance ~N * ticks_per_turn ticks.

        Tolerates ±1 per round due to known advance_ticks off-by-one.
        """
        rounds = 3
        mode = PauseAndAct(ticks_per_turn=ticks_per_turn, actions_per_turn=10)
        turns = [[ai(tool_calls=1)] for _ in range(rounds)]
        with patch_stream(turns):
            gen = mode(game, None, [])
            ticks_before = get_ticks(game)
            for _ in range(rounds):
                next(gen)
            delta = get_ticks(game) - ticks_before
        expected = rounds * ticks_per_turn
        # Lower bound: exactly N*ticks (no off-by-one)
        # Upper bound: +1 per round (advance_ticks sometimes counts the
        # re-pause as an extra tick — known pyrct2 bug)
        assert expected <= delta <= expected + rounds
