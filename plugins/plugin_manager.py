import logging

from core.action_registry import build_action_registry
from plugins.browser_control import BrowserControlPlugin
from plugins.system_control import SystemControlPlugin


LOGGER = logging.getLogger(__name__)


class PluginManager:

    def __init__(self):

        self.plugins = {}
        self.load_errors = {}

        self.load_plugins()

    def load_plugins(self):
        self.plugins, self.load_errors = build_action_registry()
        self.plugins.setdefault("browser_control", BrowserControlPlugin())
        self.plugins.setdefault("restart_system", SystemControlPlugin("restart_system"))
        self.plugins.setdefault("lock_screen", SystemControlPlugin("lock_screen"))
        self.plugins.setdefault("sleep_system", SystemControlPlugin("sleep_system"))
        LOGGER.info("Loaded plugins: %s", sorted(self.plugins))

        if self.load_errors:
            LOGGER.warning("Plugin load errors: %s", self.load_errors)

        return self.plugins

    def get_plugin(self, action):

        return self.plugins.get(action)

    def get_plugin_registry(self):
        return {
            action: plugin.__class__.__name__
            for action, plugin in self.plugins.items()
        }

    def get_load_errors(self):
        return dict(self.load_errors)
