"""Observation tools — the agent's eyes."""

from langchain_core.tools import tool, BaseTool

from pyrct2_agent.renderers import render_map_area


def make_observe_tools(game):
    @tool
    def get_park_status() -> str:
        """Get park info: date, cash, rating, guests."""
        p = game.park
        d = p.date
        return f"{p.name} | Month {d.month} Year {d.year} | ${p.finance.cash:,} | Rating {p.rating} | {p.guests.count()} guests"

    @tool
    def show_map(
        x1: int | None = None,
        y1: int | None = None,
        x2: int | None = None,
        y2: int | None = None,
    ) -> str:
        """Show ASCII grid of the map. No args = full map. With args = region from (x1,y1) to (x2,y2).

        Legend: R=Ride/track, E=Ride entrance/exit, F=Food/drink stall,
        G=Park gate, P=Path, Q=Queue, S=Scenery, .=Owned, ~=Water, _=Unowned
        Note: ride entrances/exits always face outward from the ride.
        """
        coords = [x1, y1, x2, y2]
        if all(c is None for c in coords):
            b = game.world.get_bounds()
            return render_map_area(game, 0, 0, b.x, b.y)
        if any(c is None for c in coords):
            return "ERROR: provide all of x1, y1, x2, y2 or none for full map"
        return render_map_area(game, x1, y1, x2 - x1 + 1, y2 - y1 + 1)

    return [v for v in locals().values() if isinstance(v, BaseTool)]
