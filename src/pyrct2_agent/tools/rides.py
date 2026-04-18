"""Ride and stall tools."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from langchain_core.tools import BaseTool, tool
from pyrct2.enums import Direction
from pyrct2.errors import ActionError
from pyrct2.objects import RideObjects
from pyrct2.world import Tile

if TYPE_CHECKING:
    from pyrct2.client import RCT2

# Coasters require track design which the agent can't do yet
_EXCLUDED_CATEGORIES = {"rollercoaster", "transport", "water"}

_DIRECTIONS = {
    "north": Direction.NORTH,
    "south": Direction.SOUTH,
    "east": Direction.EAST,
    "west": Direction.WEST,
}

_DIR_DELTA = {
    "north": (0, -1),
    "south": (0, 1),
    "east": (1, 0),
    "west": (-1, 0),
}


def _get_placeable_rides() -> dict:
    """Name → RideObjectInfo lookup, excluding unsupported categories."""
    return {
        obj.name: obj
        for obj in RideObjects.all()
        if not (
            set(obj.category) & _EXCLUDED_CATEGORIES
            if isinstance(obj.category, list)
            else obj.category in _EXCLUDED_CATEGORIES
        )
    }


def make_tools(game: RCT2) -> list[BaseTool]:
    all_rides = _get_placeable_rides()

    @tool
    def list_available_rides() -> str:
        """List all ride and stall types that can be built right now."""
        available = [
            obj.model_dump()
            for obj in all_rides.values()
            if game.objects.is_loaded(obj)
        ]
        return json.dumps(available)

    @tool
    def place_ride(
        name: str,
        x: int,
        y: int,
        entrance_x: int,
        entrance_y: int,
        exit_x: int,
        exit_y: int,
    ) -> str:
        """Place a flat ride. Entrance/exit must be adjacent to the footprint, not inside it.

        Args:
            name: Ride name (e.g. 'Merry-Go-Round'). Use list_available_rides to see options.
            x, y: Placement tile (center for odd-sized rides).
            entrance_x, entrance_y: Entrance tile (adjacent to ride).
            exit_x, exit_y: Exit tile (adjacent to ride).
        """
        obj = all_rides.get(name)
        if not obj:
            return f"Unknown ride '{name}'"
        # Direction hardcoded to NORTH: it only controls footprint rotation
        # (which corner the placement tile becomes), not gameplay. Exposing it
        # to the LLM adds confusion without benefit. Can be re-added later if
        # agents need to fit rides into tight spaces with specific orientations.
        try:
            entrance = Tile(entrance_x, entrance_y)
            exit_ = Tile(exit_x, exit_y)
            ride = game.rides.place_flat_ride(
                obj=obj,
                tile=Tile(x, y),
                entrance=entrance,
                exit=exit_,
            )
            ride.open()
            footprint = game.rides.get_footprint(obj, Tile(x, y))
            footprint_set = {(t.x, t.y) for t in footprint}

            # Access tiles: the tile on the opposite side of the entrance/exit
            # from the ride. This is where a path must be placed to connect.
            def _access_tile(gate: Tile) -> tuple[int, int]:
                for ft in footprint:
                    dx, dy = ft.x - gate.x, ft.y - gate.y
                    if abs(dx) + abs(dy) == 1:  # adjacent
                        return (gate.x - dx, gate.y - dy)
                return (gate.x, gate.y)

            entrance_path = _access_tile(entrance)
            exit_path = _access_tile(exit_)
            return (
                f"Placed {name} (id={ride.data.id}) at ({x},{y}). Opened.\n"
                f"Occupied tiles (cannot build on): {sorted(footprint_set)}"
                f" + entrance {(entrance_x, entrance_y)} + exit {(exit_x, exit_y)}\n"
                f"Connect paths to: entrance via {entrance_path}, exit via {exit_path}"
            )
        except (ActionError, ValueError, RuntimeError) as e:
            return f"FAILED: {e}"

    @tool
    def place_stall(
        name: str,
        x: int,
        y: int,
        direction: str = "north",
    ) -> str:
        """Place a stall (food, drink, shop, etc.). Stalls are 1x1, no entrance/exit needed.

        Args:
            name: Stall name (e.g. 'Burger Bar'). Use list_available_rides to see options.
            x, y: Tile to place the stall on.
            direction: Direction the stall faces — must point toward the adjacent path.
                E.g. if the path is north of the stall, use 'north'.
        """
        obj = all_rides.get(name)
        if not obj:
            return f"Unknown stall '{name}'"
        d = _DIRECTIONS.get(direction.lower())
        if d is None:
            return f"Invalid direction '{direction}'. Use: north, south, east, west."
        # OpenRCT2 convention: direction = stall's back, not its service window.
        # We invert so the LLM can think "face toward the path".
        d_internal = Direction((d + 2) % 4)
        try:
            stall = game.rides.place_stall(obj=obj, tile=Tile(x, y), direction=d_internal)
            stall.open()
            dx, dy = _DIR_DELTA[direction.lower()]
            access = (x + dx, y + dy)
            return (
                f"Placed {name} (id={stall.data.id}) at ({x},{y}) facing {direction}. Opened.\n"
                f"Accessible from {access}"
            )
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

    _RIDE_FIELDS = {
        "id", "name", "classification", "status", "price",
        "excitement", "intensity", "nausea",
        "totalCustomers", "totalProfit", "runningCost",
        "satisfaction", "age", "downtime", "value", "breakdown",
    }

    @tool
    def get_rides() -> str:
        """List all rides and stalls currently in the park with stats."""
        rides = game.state.rides()
        return json.dumps([
            {k: v for k, v in r.model_dump().items() if k in _RIDE_FIELDS}
            for r in rides
        ])

    @tool
    def check_ride_connectivity(ride_id: int) -> str:
        """Check if a ride/stall is reachable from the park entrance.

        For rides: checks entrance and exit separately.
        For stalls: checks if the stall faces a connected path.
        """
        ride = game.rides.get(ride_id)
        if not ride:
            return f"Ride {ride_id} not found"

        result = {"name": ride.data.name, "id": ride_id}
        if ride.entrance is not None:
            result["entrance_reachable"] = ride.is_entrance_reachable()
            result["exit_reachable"] = ride.is_exit_reachable()
        else:
            result["reachable"] = ride.is_stall_reachable()
        return json.dumps(result)

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
