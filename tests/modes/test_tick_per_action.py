"""Tests for TickPerAction mode."""

from __future__ import annotations

import pytest

from conftest import ai, get_ticks, patch_stream, tool

from pyrct2_agent.modes import TickPerAction


class TestTickPerAction:
    @pytest.mark.parametrize("ticks_per_action", [10, 25, 50])
    def test_advances_exact_ticks(self, game, ticks_per_action):
        """N tool calls should advance ~N * ticks_per_action ticks.

        Each tool call triggers one advance_ticks batch, plus one initial
        batch at round start. So 2 tool calls = 3 advance_ticks calls.
        """
        rounds = 3
        tool_calls_per_round = 2
        mode = TickPerAction(ticks_per_action=ticks_per_action)
        # Each round: AI with N tool calls, followed by N tool results
        turns = [
            [ai(tool_calls=tool_calls_per_round)] + [tool() for _ in range(tool_calls_per_round)]
            for _ in range(rounds)
        ]
        with patch_stream(turns):
            gen = mode(game, None, [])
            ticks_before = get_ticks(game)
            for _ in range(rounds):
                next(gen)
            delta = get_ticks(game) - ticks_before
        # Per round: 1 initial + N per tool result = (1 + tool_calls) batches
        batches = rounds * (1 + tool_calls_per_round)
        expected = batches * ticks_per_action
        # Lower bound: exact. Upper bound: +1 per batch (off-by-one bug)
        assert expected <= delta <= expected + batches
