"""Scratchpad memory — persistent free-form text that survives context truncation."""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool


class Scratchpad:
    """Simple string store. The agent manages the content itself."""

    def __init__(self) -> None:
        self._text = ""

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        self._text = value


def make_tools(scratchpad: Scratchpad) -> list[BaseTool]:
    @tool
    def read_scratchpad() -> str:
        """Read your scratchpad. Returns the full contents, or 'empty' if nothing has been written yet.

        Use this to recall notes you've saved about your strategy, park layout,
        game mechanics you've discovered, or anything else worth remembering.
        """
        return scratchpad.text or "empty"

    @tool
    def write_scratchpad(content: str) -> str:
        """Overwrite your scratchpad with new content. Returns 'ok'.

        The scratchpad persists across turns even when older conversation
        history is forgotten. You can use it to save any information you want.

        This overwrites the entire scratchpad. Include everything you want to keep.
        """
        scratchpad.text = content
        return "ok"

    return [read_scratchpad, write_scratchpad]
