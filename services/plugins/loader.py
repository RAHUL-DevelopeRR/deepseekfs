"""
Neuron — Plugin Loader
========================
Discovers and loads plugins from the plugins directory.

Scan strategy:
  1. Look in storage/plugins/ for .py files
  2. Import each module dynamically
  3. Find classes that subclass BaseTool
  4. Validate they have required properties
  5. Register them in the global tool registry

Safety:
  - Catches all import errors per-plugin (one bad plugin ≠ app crash)
  - Validates tool names are unique (no overwriting builtins)
  - Logs all discovery activity
"""
from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from app.logger import logger
import app.config as config
from services.tools import BaseTool, ALL_TOOLS


_PLUGINS_DIR = config.STORAGE_DIR / "plugins"


def discover_plugins() -> List[Tuple[str, BaseTool]]:
    """Scan the plugins directory and return discovered tools.
    
    Returns:
        List of (source_file, tool_instance) tuples
    
    Does NOT modify the global registry — caller decides.
    """
    _PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    discovered = []

    for py_file in sorted(_PLUGINS_DIR.glob("*.py")):
        if py_file.name.startswith("_"):
            continue

        module_name = f"neuron_plugin_{py_file.stem}"

        try:
            spec = importlib.util.spec_from_file_location(module_name, str(py_file))
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Find all BaseTool subclasses in the module
            for attr_name in dir(module):
                obj = getattr(module, attr_name)
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, BaseTool)
                    and obj is not BaseTool
                    and hasattr(obj, "name")
                    and hasattr(obj, "execute")
                ):
                    try:
                        instance = obj()
                        discovered.append((py_file.name, instance))
                        logger.info(
                            f"PluginLoader: Discovered '{instance.name}' "
                            f"from {py_file.name}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"PluginLoader: Failed to instantiate "
                            f"{attr_name} from {py_file.name}: {e}"
                        )

        except Exception as e:
            logger.warning(f"PluginLoader: Failed to load {py_file.name}: {e}")
            # Clean up failed module
            sys.modules.pop(module_name, None)

    return discovered


def register_plugins() -> int:
    """Discover and register all plugins. Returns count registered.
    
    Skips plugins whose tool name conflicts with built-in tools.
    """
    discovered = discover_plugins()
    registered = 0

    for source, tool in discovered:
        if tool.name in ALL_TOOLS:
            logger.warning(
                f"PluginLoader: Skipping '{tool.name}' from {source} "
                f"(conflicts with built-in tool)"
            )
            continue

        ALL_TOOLS[tool.name] = tool
        registered += 1
        logger.info(f"PluginLoader: Registered '{tool.name}' from {source}")

    if registered:
        logger.info(f"PluginLoader: {registered} plugin(s) registered")

    return registered
