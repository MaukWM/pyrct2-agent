"""Auto-collect tools from all modules in this package.

Convention: each module exports a `make_*_tools(game)` function that
returns a list of @tool-decorated functions. Drop a new file here,
follow the convention, and it gets picked up automatically.
"""

import importlib
import pkgutil


def make_tools(game):
    tools = []
    for info in pkgutil.iter_modules(__path__):
        mod = importlib.import_module(f".{info.name}", __package__)
        for name in dir(mod):
            if name.startswith("make_") and name.endswith("_tools"):
                tools.extend(getattr(mod, name)(game))
    return tools
