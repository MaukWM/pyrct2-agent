"""State-to-text renderers for LLM consumption."""

from pyrct2.world import Tile

# EntranceElement.object values (from C++ EntranceElement.h):
# 0 = ride entrance, 1 = ride exit, 2 = park entrance
_RIDE_ENTRANCE = 0
_RIDE_EXIT = 1
_PARK_ENTRANCE = 2


def render_map_area(game, x: int, y: int, w: int = 16, h: int = 16) -> str:
    """Render an ASCII grid of a map region."""
    stall_ids = {r.id for r in game.state.rides() if r.classification == "stall"}

    tiles = game.world.get_tiles(Tile(x, y), Tile(x + w - 1, y + h - 1))

    grid: dict[tuple[int, int], str] = {}
    for t in tiles:
        k = (t.x, t.y)
        if t.entrances:
            e = t.entrances[0]
            if e.object == _PARK_ENTRANCE:
                grid[k] = "G"
            elif e.object == _RIDE_EXIT:
                grid[k] = "x"
            else:
                grid[k] = "E"
        elif t.tracks:
            track = t.tracks[0]
            grid[k] = "F" if track.ride in stall_ids else "R"
        elif t.paths:
            grid[k] = "Q" if any(p.isQueue for p in t.paths) else "P"
        elif t.scenery:
            grid[k] = "S"
        else:
            s = t.surface
            if s.waterHeight > 0:
                grid[k] = "~"
            elif s.hasOwnership:
                grid[k] = "."
            else:
                grid[k] = "_"

    header = "     " + "".join(f"{x + dx:>3}" for dx in range(w))
    lines = [header]
    for dy in range(h):
        row = f"Y{y + dy:<4}" + "".join(
            f"  {grid.get((x + dx, y + dy), ' ')}" for dx in range(w)
        )
        lines.append(row)
    return "\n".join(lines)
