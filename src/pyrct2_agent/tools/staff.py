"""Staff management tools — hiring and listing."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from langchain_core.tools import BaseTool, tool
from pyrct2._generated.enums import StaffType
from pyrct2.errors import ActionError

if TYPE_CHECKING:
    from pyrct2.client import RCT2

_VALID_TYPES = {
    "handyman": StaffType.HANDYMAN,
    "mechanic": StaffType.MECHANIC,
    "security": StaffType.SECURITY,
    "entertainer": StaffType.ENTERTAINER,
}

# Default staff orders bitmask per type (see OpenRCT2 Staff.h STAFF_ORDERS).
# Handyman: sweep(1) + water(2) + empty bins(4) = 7  (skip mow grass)
# Mechanic: inspect(1) + fix(2) = 3
_DEFAULT_ORDERS = {
    StaffType.HANDYMAN: 7,
    StaffType.MECHANIC: 3,
    StaffType.SECURITY: 0,
    StaffType.ENTERTAINER: 0,
}


def make_tools(game: RCT2) -> list[BaseTool]:
    @tool
    def hire_staff(staff_type: str) -> str:
        """Hire a new staff member with sensible default duties enabled.

        Args:
            staff_type: 'handyman' (sweeps paths, empties bins, waters gardens),
                        'mechanic' (inspects and fixes rides),
                        'security' (prevents vandalism),
                        or 'entertainer' (increases guest happiness).
        """
        st = _VALID_TYPES.get(staff_type.lower())
        if st is None:
            return f"Invalid staff type '{staff_type}'. Use: handyman, mechanic, security, entertainer."
        try:
            orders = _DEFAULT_ORDERS[st]
            entity = game.park.staff.hire(st, staff_orders=orders)
            return f"Hired {staff_type} '{entity.data.name}' (id={entity.data.id})"
        except (ActionError, RuntimeError) as e:
            return f"FAILED: {e}"

    @tool
    def list_staff() -> str:
        """List all staff members with their type, name, and id."""
        staff = game.park.staff.list()
        return json.dumps(
            [
                {
                    "id": s.data.id,
                    "name": s.data.name,
                    "type": s.data.staffType,
                }
                for s in staff
            ]
        )

    return [v for v in locals().values() if isinstance(v, BaseTool)]
