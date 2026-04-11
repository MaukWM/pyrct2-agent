"""Path building tools."""

from langchain_core.tools import tool, BaseTool
from pyrct2.errors import ActionError
from pyrct2.world import Tile


def make_path_tools(game):
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
            r = game.paths.place_line(Tile(x1, y1), Tile(x2, y2), queue=queue)
            kind = "Queue" if queue else "Path"
            return f"{kind} line: {r.succeeded} placed, {r.failed} failed, cost=${r.total_cost}"
        except ActionError as e:
            return f"FAILED: {e}"

    return [v for v in locals().values() if isinstance(v, BaseTool)]
