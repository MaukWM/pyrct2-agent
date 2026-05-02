"""Unit tests for message history truncation — no game instance needed."""

from types import SimpleNamespace

from pyrct2_agent.modes import _truncate_messages, _CHARS_PER_TOKEN


def _fake_msg(content: str, tool_calls=None):
    return SimpleNamespace(content=content, tool_calls=tool_calls or [])


def test_over_budget_drops_oldest():
    big = "x" * 1000
    msgs = [_fake_msg(big) for _ in range(10)]
    budget = int(3 * 1000 / _CHARS_PER_TOKEN) + 1
    _truncate_messages(msgs, budget)
    assert len(msgs) == 3


def test_always_keeps_at_least_one():
    msgs = [_fake_msg("x" * 100_000)]
    _truncate_messages(msgs, 1)
    assert len(msgs) == 1


def test_preserves_recent_not_old():
    msgs = [_fake_msg(f"msg-{i}") for i in range(20)]
    _truncate_messages(msgs, 10)
    assert msgs[-1].content == "msg-19"
    assert msgs[0].content != "msg-0"
