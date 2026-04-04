import os
import shutil
import subprocess
from difflib import get_close_matches
from pathlib import Path

from plugins.base_plugin import BasePlugin


class OpenAppPlugin(BasePlugin):

    APP_ALIASES = {
        "chrome": "chrome",
        "google chrome": "chrome",
        "chrome browser": "chrome",
        "browser": "chrome",

        "calculator": "calc",
        "calc": "calc",

        "notepad": "notepad",
        "text editor": "notepad",

        "cmd": "cmd",
        "command prompt": "cmd",
        "terminal": "cmd",
        "windows terminal": "cmd",

        "file explorer": "explorer",
        "explorer": "explorer",
        "visual studio code": "code",
        "vs code": "code",
        "powershell": "powershell",
    }
    NAME_NORMALIZATION = APP_ALIASES
    FUZZY_CUTOFF = 0.72

    action = "open"
    required_parameters = {
        "name": "Please specify which application to open",
    }

    def execute(self, parameters):
        app_name = parameters.get("name")

        launch_target = self.normalize_app_name(app_name)
        resolved_target = self.resolve_launch_target(launch_target)

        if resolved_target and self.start_process(resolved_target):
            return f"{app_name} opened"

        return f"I tried to open {app_name}, but Windows could not find a matching application."

    def normalize_app_name(self, app_name):
        cleaned_name = app_name.strip().strip("\"'")
        lowered_name = cleaned_name.lower()

        if lowered_name in self.NAME_NORMALIZATION:
            return self.NAME_NORMALIZATION[lowered_name]

        fuzzy_alias = self.resolve_fuzzy_alias(lowered_name)

        if fuzzy_alias:
            return fuzzy_alias

        return cleaned_name

    def resolve_fuzzy_alias(self, app_name):
        alias_match = get_close_matches(
            app_name,
            self.NAME_NORMALIZATION.keys(),
            n=1,
            cutoff=self.FUZZY_CUTOFF,
        )

        if alias_match:
            return self.NAME_NORMALIZATION[alias_match[0]]

        canonical_names = sorted(set(self.NAME_NORMALIZATION.values()))
        canonical_match = get_close_matches(
            app_name,
            canonical_names,
            n=1,
            cutoff=self.FUZZY_CUTOFF,
        )

        if canonical_match:
            return canonical_match[0]

        return None

    def build_candidates(self, app_name):
        candidates = []
        base = app_name.strip()

        if not base:
            return candidates

        candidates.append(base)

        if " " in base:
            collapsed = base.replace(" ", "")
            if collapsed not in candidates:
                candidates.append(collapsed)

        if not base.lower().endswith(".exe"):
            exe_name = f"{base}.exe"
            if exe_name not in candidates:
                candidates.append(exe_name)

            if " " in base:
                collapsed_exe = f"{base.replace(' ', '')}.exe"
                if collapsed_exe not in candidates:
                    candidates.append(collapsed_exe)

        return candidates

    def resolve_launch_target(self, app_name):
        if not app_name:
            return None

        if os.path.exists(app_name):
            return app_name

        for candidate in self.build_candidates(app_name):
            if shutil.which(candidate):
                return candidate

        start_menu_match = self.find_start_menu_match(app_name)

        if start_menu_match:
            return start_menu_match

        installed_match = self.find_installed_app_match(app_name)

        if installed_match:
            return installed_match

        return app_name

    def find_start_menu_match(self, app_name):
        start_menu_dirs = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        ]
        extensions = {".lnk", ".url", ".appref-ms", ".exe"}

        for directory in start_menu_dirs:
            match = self.find_best_match(directory, app_name, extensions, max_depth=4)

            if match:
                return str(match)

        return None

    def find_installed_app_match(self, app_name):
        install_roots = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
            Path(os.environ.get("PROGRAMFILES", "")),
            Path(os.environ.get("PROGRAMFILES(X86)", "")),
        ]

        for root in install_roots:
            if not root.exists():
                continue

            candidate_dirs = [root]

            try:
                children = list(root.iterdir())
            except OSError:
                children = []

            for child in children:
                try:
                    is_directory = child.is_dir()
                except OSError:
                    continue

                if not is_directory:
                    continue

                if self.is_name_match(child.name, app_name):
                    candidate_dirs.append(child)

            for directory in candidate_dirs:
                match = self.find_best_match(directory, app_name, {".exe"}, max_depth=3)

                if match:
                    return str(match)

        return None

    def find_best_match(self, directory, app_name, extensions, max_depth):
        if not directory.exists():
            return None

        best_match = None
        best_score = None
        target = self.normalize_text(app_name)

        try:
            paths = directory.rglob("*")
        except OSError:
            return None

        for path in paths:
            try:
                is_file = path.is_file()
            except OSError:
                continue

            if not is_file:
                continue

            if path.suffix.lower() not in extensions:
                continue

            try:
                depth = len(path.relative_to(directory).parts)
            except ValueError:
                continue

            if depth > max_depth:
                continue

            score = self.match_score(path.stem, target)

            if score is None:
                continue

            if best_score is None or score < best_score:
                best_match = path
                best_score = score

                if score == 0:
                    break

        return best_match

    def match_score(self, candidate_name, normalized_target):
        normalized_candidate = self.normalize_text(candidate_name)

        if not normalized_candidate or not normalized_target:
            return None

        if normalized_candidate == normalized_target:
            return 0

        if normalized_candidate.startswith(normalized_target):
            return 1

        if normalized_target in normalized_candidate:
            return 2

        return None

    def is_name_match(self, candidate_name, target_name):
        normalized_candidate = self.normalize_text(candidate_name)
        normalized_target = self.normalize_text(target_name)

        if not normalized_candidate or not normalized_target:
            return False

        return (
            normalized_candidate == normalized_target
            or normalized_candidate.startswith(normalized_target)
            or normalized_target in normalized_candidate
        )

    def normalize_text(self, text):
        return "".join(char.lower() for char in text if char.isalnum())

    def start_process(self, target):
        escaped_target = target.replace("'", "''")
        commands = [
            ["cmd", "/c", "start", "", target],
            ["powershell", "-NoProfile", "-Command", f"Start-Process '{escaped_target}'"],
        ]

        for command in commands:
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    shell=False,
                )
            except (OSError, subprocess.SubprocessError):
                continue

            if completed.returncode == 0:
                return True

        if os.path.exists(target):
            try:
                os.startfile(target)
                return True
            except OSError:
                return False

        return False
