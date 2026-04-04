import logging

from core.action_registry import build_action_registry
from plugins.browser_control import BrowserControlPlugin


LOGGER = logging.getLogger(__name__)


class PluginManager:

    def __init__(self):

        self.plugins = {}
        self.load_errors = {}

        self.load_plugins()

    def load_plugins(self):
        self.plugins, self.load_errors = build_action_registry()
        self.plugins.setdefault("browser_control", BrowserControlPlugin())
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
