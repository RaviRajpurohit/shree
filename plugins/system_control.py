import logging
import subprocess

from plugins.base_plugin import BasePlugin


LOGGER = logging.getLogger(__name__)


class SystemControlPlugin(BasePlugin):
    ACTION_COMMANDS = {
        "restart_system": ["shutdown", "/r", "/t", "0"],
        "lock_screen": ["rundll32.exe", "user32.dll,LockWorkStation"],
        "sleep_system": [
            "rundll32.exe",
            "powrprof.dll,SetSuspendState",
            "0,1,0",
        ],
    }
    SAFETY_MESSAGES = {
        "restart_system": "Confirmation required before restart",
        "shutdown_system": "Confirmation required before shutdown",
    }
    SUCCESS_MESSAGES = {
        "restart_system": "Restart command sent.",
        "lock_screen": "Lock screen command sent.",
        "sleep_system": "Sleep command sent.",
    }

    def __init__(self, action_name="restart_system"):
        self.action = action_name

    def execute(self, parameters):
        parameters = parameters or {}
        action_name = self.action

        if action_name in self.SAFETY_MESSAGES and not parameters.get("confirm"):
            LOGGER.info("Blocked %s because confirmation was not provided.", action_name)
            return self.SAFETY_MESSAGES[action_name]

        command = self.ACTION_COMMANDS.get(action_name)

        if not command:
            LOGGER.warning("Unsupported system action requested: %s", action_name)
            return "Unsupported system control action."

        try:
            subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                shell=False,
            )
        except OSError:
            LOGGER.exception("Failed to execute system action: %s", action_name)
            return f"I couldn't complete the {action_name.replace('_', ' ')} request."

        LOGGER.info("Executed system action: %s", action_name)
        return self.SUCCESS_MESSAGES.get(action_name, "System command sent.")
