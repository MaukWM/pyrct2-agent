"""Path building tools."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.tools import BaseTool, tool
from pyrct2.errors import ActionError
from pyrct2.world import Tile

if TYPE_CHECKING:
    from pyrct2.client import RCT2


def make_tools(game: RCT2) -> list[BaseTool]:
    @tool
    def place_path(x: int, y: int, queue: bool = False) -> str:
        """Place a footpath tile at (x, y). Set queue=True for queue paths (connect to ride entrances)."""
        try:
            r = game.paths.place(Tile(x, y), queue=queue)
            kind = "Queue path" if queue else "Path"
            return f"{kind} placed at ({x},{y}), cost=${r.cost}"
        except ActionError as e:
            return f"FAILED: {e}"

    @tool
    def place_path_line(x1: int, y1: int, x2: int, y2: int, queue: bool = False) -> str:
        """Place straight path line. Must be cardinal (same x or same y). Set queue=True for queue paths."""
        try:
            start, end = Tile(x1, y1), Tile(x2, y2)
            r = game.paths.place_line(start, end, queue=queue)
            kind = "Queue" if queue else "Path"
            parts = [
                f"{kind} line: {r.succeeded} placed, {r.failed} failed, cost=${r.total_cost}"
            ]
            # Build matching tile list to report failure locations
            if x1 == x2:
                step = 1 if y2 >= y1 else -1
                tiles = [(x1, y) for y in range(y1, y2 + step, step)]
            else:
                step = 1 if x2 >= x1 else -1
                tiles = [(x, y1) for x in range(x1, x2 + step, step)]
            for (tx, ty), result in zip(tiles, r.results):
                if isinstance(result, ActionError):
                    parts.append(f"  ({tx},{ty}): {result}")
            return "\n".join(parts)
        except (ActionError, ValueError) as e:
            return f"FAILED: {e}"

    @tool
    def remove_path(x: int, y: int) -> str:
        """Remove a footpath or queue tile at (x, y)."""
        try:
            game.paths.remove(Tile(x, y))
            return f"Removed path at ({x},{y})"
        except ActionError as e:
            return f"FAILED: {e}"

    return [v for v in locals().values() if isinstance(v, BaseTool)]
