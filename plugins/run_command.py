import logging
import os
import subprocess

from plugins.base_plugin import BasePlugin


LOGGER = logging.getLogger(__name__)


class RunCommandPlugin(BasePlugin):
    COMMAND_NORMALIZATION = {
        "clear": "cls",
        "ls": "dir",
    }
    SAFE_COMMAND_ALIASES = {
        "clear": {"windows": "cls", "default": "clear"},
        "clear screen": {"windows": "cls", "default": "clear"},
        "clear terminal": {"windows": "cls", "default": "clear"},
        "clear console": {"windows": "cls", "default": "clear"},
        "cls": {"windows": "cls", "default": "clear"},
        "ls": {"windows": "dir", "default": "ls"},
        "dir": {"windows": "dir", "default": "ls"},
    }
    BLOCKED_KEYWORDS = {
        "del",
        "erase",
        "format",
        "rmdir",
        "rd",
        "rm",
        "remove-item",
        "shutdown",
        "restart",
        "reboot",
        "taskkill",
        "diskpart",
        "reg delete",
    }

    action = "run_command"
    required_parameters = {
        "command": "Please specify which command to run",
    }

    def execute(self, parameters):
        raw_command = (parameters.get("command") or "").strip()
        normalized_command = self.normalize_command(raw_command)

        if self.is_blocked_command(normalized_command):
            LOGGER.warning("Blocked harmful command request: %s", raw_command)
            return f"Blocked unsafe command: {raw_command}"

        safe_command = self.resolve_safe_command(normalized_command)

        if not safe_command:
            LOGGER.warning("Rejected unsupported command request: %s", raw_command)
            return f"Unsupported command: {raw_command}"

        try:
            completed = subprocess.run(
                safe_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            LOGGER.exception("Failed to run command: %s", raw_command)
            return f"Failed to run command: {raw_command}"

        if completed.returncode == 0:
            LOGGER.info("Command executed successfully: %s", raw_command)
            return f"Command executed successfully: {raw_command}"

        LOGGER.warning(
            "Command failed with return code %s: %s",
            completed.returncode,
            raw_command,
        )
        return f"Command failed: {raw_command}"

    def resolve_safe_command(self, normalized_command):
        command_entry = self.SAFE_COMMAND_ALIASES.get(normalized_command)

        if not command_entry:
            return None

        if os.name == "nt":
            return command_entry["windows"]

        return command_entry["default"]

    def is_blocked_command(self, normalized_command):
        return any(keyword in normalized_command for keyword in self.BLOCKED_KEYWORDS)

    @staticmethod
    def normalize_command(command):
        normalized_command = " ".join(str(command or "").strip().lower().split())
        return RunCommandPlugin.COMMAND_NORMALIZATION.get(normalized_command, normalized_command)
