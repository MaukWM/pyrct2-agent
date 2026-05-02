"""Builtin tools for the pyrct2 agent.

Each module exports a ``make_tools(game)`` function returning a list of
LangChain tools. Modules are auto-discovered at import time.

Public API:
    default_tools(game)        — instantiate all builtin tools for a game
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import TYPE_CHECKING

from langchain_core.tools import BaseTool

from pyrct2_agent.tools.memory import make_memory_tools

if TYPE_CHECKING:
    from pyrct2.client import RCT2

# Auto-discover all sibling modules that have a make_tools function.
# Skips the memory/ subpackage — it's handled separately.
_MODULES: list[str] = []
for _info in pkgutil.iter_modules(__path__):
    if _info.ispkg:
        continue
    _mod = importlib.import_module(f".{_info.name}", __package__)
    if hasattr(_mod, "make_tools"):
        _MODULES.append(f".{_info.name}")


def default_tools(game: RCT2) -> list[BaseTool]:
    """Instantiate all builtin tools for a live game instance."""
    tools: list[BaseTool] = []
    for mod_name in _MODULES:
        mod = importlib.import_module(mod_name, __package__)
        tools.extend(mod.make_tools(game))
    tools.extend(make_memory_tools())
    return tools
