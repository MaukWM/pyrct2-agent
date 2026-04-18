"""Tests for RealTime mode."""

from __future__ import annotations

from conftest import ai, get_ticks, patch_stream

from pyrct2_agent.modes import RealTime


class TestRealTime:
    def test_counts_actions(self, game):
        """Should count tool calls from stream."""
        mode = RealTime()
        turns = [[ai(tool_calls=2)]]
        with patch_stream(turns):
            snap = next(mode(game, None, []))
            assert snap.actions == 2

    def test_game_advances_while_unpaused(self, game):
        """Game should be paused after the round, with ticks having advanced."""
        ticks_before = get_ticks(game)
        mode = RealTime()
        turns = [[ai("hello")]]
        with patch_stream(turns):
            next(mode(game, None, []))
        assert game.get_status()["payload"]["paused"] is True
        assert get_ticks(game) > ticks_before
