"""Ride and stall tools."""

from langchain_core.tools import tool, BaseTool
from pyrct2.errors import ActionError
from pyrct2.objects import RideObjects
from pyrct2._generated.objects import RideObjectInfo
from pyrct2.enums import Direction
from pyrct2.world import Tile

# Coasters require track design which the agent can't do yet
_EXCLUDED_CATEGORIES = {"rollercoaster", "transport", "water"}

# Name → RideObjectInfo lookup, excluding unsupported categories
_ALL_RIDES: dict[str, RideObjectInfo] = {
    obj.name: obj for obj in RideObjects.all()
    if not (set(obj.category) & _EXCLUDED_CATEGORIES if isinstance(obj.category, list) else obj.category in _EXCLUDED_CATEGORIES)
}

_DIRECTIONS = {"north": Direction.NORTH, "south": Direction.SOUTH, "east": Direction.EAST, "west": Direction.WEST}


def make_ride_tools(game):
    @tool
    def list_available_rides() -> str:
        """List all ride and stall types that can be built right now.

        Returns name, category, and footprint for each.
        """
        lines = []
        for obj in _ALL_RIDES.values():
            if not game.objects.is_loaded(obj):
                continue
            size = f"{obj.tiles_x}x{obj.tiles_y}" if obj.tiles_x else "1x1"
            lines.append(f"  {obj.name} [{obj.category}] {size}")
        if not lines:
            return "No rides available yet. Research more!"
        return f"{len(lines)} available:\n" + "\n".join(sorted(lines))

    @tool
    def get_ride_info(name: str) -> str:
        """Get detailed info about a ride/stall type by name (e.g. 'Merry-Go-Round')."""
        obj = _ALL_RIDES.get(name)
        if not obj:
            close = [n for n in _ALL_RIDES if name.lower() in n.lower()]
            return f"Unknown ride '{name}'. Did you mean: {', '.join(close[:5])}" if close else f"Unknown ride '{name}'"
        size = f"{obj.tiles_x}x{obj.tiles_y}" if obj.tiles_x else "1x1"
        loaded = game.objects.is_loaded(obj)
        return (
            f"Name: {obj.name}\n"
            f"Type: {obj.ride_type}\n"
            f"Category: {obj.category}\n"
            f"Footprint: {size}\n"
            f"Loaded: {loaded}"
        )

    @tool
    def place_ride(
        name: str,
        x: int, y: int,
        entrance_x: int, entrance_y: int,
        exit_x: int, exit_y: int,
        direction: str = "north",
    ) -> str:
        """Place a flat ride. Entrance/exit must be adjacent to the footprint, not inside it.

        Args:
            name: Ride name (e.g. 'Merry-Go-Round'). Use list_available_rides to see options.
            x, y: Placement tile (center for odd-sized rides).
            entrance_x, entrance_y: Entrance tile (adjacent to ride).
            exit_x, exit_y: Exit tile (adjacent to ride).
            direction: Facing direction: north, south, east, west.
        """
        obj = _ALL_RIDES.get(name)
        if not obj:
            return f"Unknown ride '{name}'"
        d = _DIRECTIONS.get(direction.lower(), Direction.NORTH)
        try:
            ride = game.rides.place_flat_ride(
                obj=obj,
                tile=Tile(x, y),
                entrance=Tile(entrance_x, entrance_y),
                exit=Tile(exit_x, exit_y),
                direction=d,
            )
            ride.open()
            return f"Placed {name} (id={ride.data.id}) at ({x},{y}), entrance ({entrance_x},{entrance_y}), exit ({exit_x},{exit_y}). Opened."
        except (ActionError, ValueError, RuntimeError) as e:
            return f"FAILED: {e}"

    @tool
    def place_stall(
        name: str,
        x: int, y: int,
        direction: str = "north",
    ) -> str:
        """Place a stall (food, drink, shop, etc.). Stalls are 1x1, no entrance/exit needed.

        Args:
            name: Stall name (e.g. 'Burger Bar'). Use list_available_rides to see options.
            x, y: Tile to place the stall on.
            direction: Which way guests approach: north, south, east, west.
        """
        obj = _ALL_RIDES.get(name)
        if not obj:
            return f"Unknown stall '{name}'"
        d = _DIRECTIONS.get(direction.lower(), Direction.NORTH)
        try:
            stall = game.rides.place_stall(obj=obj, tile=Tile(x, y), direction=d)
            stall.open()
            return f"Placed {name} (id={stall.data.id}) at ({x},{y}) facing {direction}. Opened."
        except (ActionError, ValueError, RuntimeError) as e:
            return f"FAILED: {e}"

    @tool
    def set_ride_price(ride_id: int, price: int) -> str:
        """Set entry price for a ride or stall."""
        ride = game.rides.get(ride_id)
        if not ride:
            return f"Ride {ride_id} not found"
        try:
            ride.set_price(price)
            return f"Set {ride.data.name} price to ${price}"
        except ActionError as e:
            return f"FAILED: {e}"

    @tool
    def get_rides() -> str:
        """List all rides and stalls currently in the park with stats."""
        rides = game.state.rides()
        if not rides:
            return "No rides in the park yet."
        lines = []
        for r in rides:
            lines.append(
                f"  #{r.id} {r.name} [{r.classification}] {r.status} "
                f"| excitement={r.excitement} intensity={r.intensity} nausea={r.nausea}"
            )
        return f"{len(rides)} rides:\n" + "\n".join(lines)

    @tool
    def check_ride_connectivity(ride_id: int, target_x: int | None = None, target_y: int | None = None) -> str:
        """Check if a ride/stall entrance and exit are connected to paths.

        Without target: checks if paths exist adjacent to entrance/exit.
        With target (x,y): checks full path connectivity to that tile (e.g. park gate).
        """
        ride = game.rides.get(ride_id)
        if not ride:
            return f"Ride {ride_id} not found"
        if (target_x is None) != (target_y is None):
            return "ERROR: provide both target_x and target_y, or neither"
        target = Tile(target_x, target_y) if target_x is not None else None

        if ride.entrance is not None:
            entrance_ok = ride.is_entrance_reachable(target)
            exit_ok = ride.is_exit_reachable(target)
            parts = []
            parts.append(f"entrance: {'connected' if entrance_ok else 'NOT connected'}")
            parts.append(f"exit: {'connected' if exit_ok else 'NOT connected'}")
            return f"{ride.data.name}: {', '.join(parts)}"
        else:
            ok = ride.is_reachable(target)
            return f"{ride.data.name}: {'reachable' if ok else 'NOT reachable (not facing a path)'}"

    @tool
    def demolish_ride(ride_id: int) -> str:
        """Demolish a ride or stall, removing it from the map."""
        ride = game.rides.get(ride_id)
        if not ride:
            return f"Ride {ride_id} not found"
        name = ride.data.name
        try:
            ride.demolish()
            return f"Demolished {name}"
        except ActionError as e:
            return f"FAILED: {e}"

    return [v for v in locals().values() if isinstance(v, BaseTool)]
