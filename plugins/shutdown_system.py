from plugins.base_plugin import BasePlugin


class ShutdownSystemPlugin(BasePlugin):

    action = "shutdown_system"

    def execute(self, parameters):
        if not parameters.get("confirm"):
            return "Shutdown requested, but confirmation is required before powering off the system."

        return "Shutdown confirmed, but real shutdown is disabled for safety in this build."
