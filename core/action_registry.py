from importlib import import_module
from inspect import isclass
from pathlib import Path

from plugins.base_plugin import BasePlugin


PLUGIN_SKIP_FILES = {"__init__", "base_plugin", "plugin_manager"}
PLUGIN_FOLDER = Path(__file__).resolve().parent.parent / "plugins"


def iter_plugin_modules():
    for file_path in sorted(PLUGIN_FOLDER.glob("*.py")):
        if file_path.stem in PLUGIN_SKIP_FILES:
            continue
        yield file_path.stem


def discover_plugin_classes():
    plugin_classes = []
    load_errors = {}

    for module_name in iter_plugin_modules():
        try:
            module = import_module(f"plugins.{module_name}")
        except Exception as exc:
            load_errors[module_name] = str(exc)
            continue

        for attribute in vars(module).values():
            if not isclass(attribute):
                continue
            if not issubclass(attribute, BasePlugin) or attribute is BasePlugin:
                continue
            plugin_classes.append(attribute)

    return plugin_classes, load_errors


def build_action_registry():
    registry = {}
    load_errors = {}
    plugin_classes, import_errors = discover_plugin_classes()
    load_errors.update(import_errors)

    for plugin_class in plugin_classes:
        try:
            plugin = plugin_class()
        except Exception as exc:
            load_errors[plugin_class.__name__] = str(exc)
            continue

        if not plugin.action:
            load_errors[plugin_class.__name__] = "Missing action name."
            continue

        registry[plugin.action] = plugin

    return registry, load_errors
