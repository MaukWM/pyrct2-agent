"""Tests for RealTime mode."""

from __future__ import annotations

import time

from conftest import get_ticks, patch_step, step_snap

from pyrct2_agent.modes import RealTime


class TestRealTime:
    def test_yields_snapshots(self, game):
        """Should yield one StepSnapshot per _step call."""
        mode = RealTime()
        snaps = [step_snap(action="place_ride")]
        with patch_step(snaps):
            gen = mode(game, None, [], {}, "", [])
            s = next(gen)
        assert s.action == "place_ride"

    def test_game_advances_while_unpaused(self, game):
        """Game ticks advance while the agent is thinking."""
        ticks_before = get_ticks(game)
        mode = RealTime()

        def slow_step(_llm, _tools, _tool_map, _prompt, _msgs, _max_tok):
            time.sleep(0.5)
            return step_snap()

        from unittest.mock import patch

        with patch("pyrct2_agent.modes._step", side_effect=slow_step):
            next(mode(game, None, [], {}, "", []))

        assert get_ticks(game) > ticks_before
