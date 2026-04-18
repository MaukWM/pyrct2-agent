"""Observation tools — the agent's eyes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from langchain_core.tools import BaseTool, tool

from pyrct2_agent.renderers import render_map_area

if TYPE_CHECKING:
    from pyrct2.client import RCT2


def make_tools(game: RCT2) -> list[BaseTool]:
    @tool
    def get_park_status() -> str:
        """Get current park state: finances, ratings, date, guests, objective."""
        p = game.park
        d = p.date
        return json.dumps({
            "name": p.name,
            "month": d.month,
            "year": d.year,
            "cash": p.finance.cash,
            "park_value": p.value,
            "rating": p.rating,
            "guests": p.guests.count(),
            "objective": p.objective.model_dump(),
        })

    @tool
    def show_map(
        x1: int | None = None,
        y1: int | None = None,
        x2: int | None = None,
        y2: int | None = None,
    ) -> str:
        """Show ASCII grid of the map. No args = full map. With args = region from (x1,y1) to (x2,y2).

        Legend: R=Ride/track, E=Entrance, x=Exit, F=Food/drink stall,
        G=Park gate, P=Path, Q=Queue, S=Scenery, .=Owned, ~=Water, _=Unowned
        """
        coords = [x1, y1, x2, y2]
        if all(c is None for c in coords):
            b = game.world.get_bounds()
            return render_map_area(game, 0, 0, b.x, b.y)
        if any(c is None for c in coords):
            return "ERROR: provide all of x1, y1, x2, y2 or none for full map"
        return render_map_area(game, x1, y1, x2 - x1 + 1, y2 - y1 + 1)

    return [v for v in locals().values() if isinstance(v, BaseTool)]
