import logging
import os
from pathlib import Path

from plugins.base_plugin import BasePlugin


LOGGER = logging.getLogger(__name__)


class OpenFilePlugin(BasePlugin):
    action = "open_file"
    required_parameters = {
        "name": "Please specify which file to open",
    }
    SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".jpg", ".png"}

    def execute(self, parameters):
        file_name = (parameters.get("name") or "").strip().strip("\"'")

        if not file_name:
            return "Please specify which file to open."

        LOGGER.info("Searching for file: %s", file_name)
        file_path = self.find_file(file_name)

        if not file_path:
            LOGGER.info("File not found in supported folders: %s", file_name)
            return (
                f"I couldn't find '{file_name}' in Desktop, Downloads, or Documents. "
                "Supported file types are .pdf, .txt, .jpg, and .png."
            )

        try:
            os.startfile(str(file_path))
        except OSError:
            LOGGER.exception("Failed to open file: %s", file_path)
            return f"I found '{file_path.name}', but Windows could not open it."

        LOGGER.info("Opened file: %s", file_path)
        return f"Opened file: {file_path.name}"

    def find_file(self, file_name):
        normalized_name = file_name.lower()
        requested_extension = Path(normalized_name).suffix.lower()

        if requested_extension and requested_extension not in self.SUPPORTED_EXTENSIONS:
            LOGGER.info("Unsupported file extension requested: %s", requested_extension)
            return None

        candidate_names = self.build_candidate_names(normalized_name)

        for directory in self.get_search_directories():
            if not directory.exists():
                continue

            LOGGER.debug("Searching for %s in %s", file_name, directory)

            for path in directory.rglob("*"):
                if not path.is_file():
                    continue

                if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
                    continue

                if path.name.lower() in candidate_names:
                    return path

        return None

    def build_candidate_names(self, file_name):
        suffix = Path(file_name).suffix.lower()

        if suffix:
            return {file_name}

        return {
            f"{file_name}{extension}"
            for extension in sorted(self.SUPPORTED_EXTENSIONS)
        }

    @staticmethod
    def get_search_directories():
        home = Path.home()
        return [
            home / "Desktop",
            home / "Downloads",
            home / "Documents",
        ]
