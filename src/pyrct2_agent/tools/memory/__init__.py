"""Memory tools — persistent state that survives context truncation.

Each backend (_scratchpad, _kv_store, _vector_db) is independent.
This module assembles whichever are enabled.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool

from pyrct2_agent.tools.memory._scratchpad import (
    Scratchpad,
    make_tools as _scratchpad_tools,
)


def make_memory_tools() -> list[BaseTool]:
    """Create all enabled memory tools. Returns tools + any state objects."""
    scratchpad = Scratchpad()
    return _scratchpad_tools(scratchpad)
