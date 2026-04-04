import ctypes
import os
import re
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

from plugins.base_plugin import BasePlugin


class PlayMusicPlugin(BasePlugin):
    action = "play_music"
    required_parameters = {
        "name": "Please specify which song or music to play",
    }

    MEDIA_KEY_COMMANDS = {
        "next": 0xB0,
        "previous": 0xB1,
        "stop": 0xB2,
        "pause": 0xB3,
        "resume": 0xB3,
        "play_pause": 0xB3,
    }
    CONTROL_ALIASES = {
        "next": "next",
        "next song": "next",
        "next track": "next",
        "previous": "previous",
        "previous song": "previous",
        "previous track": "previous",
        "pause": "pause",
        "resume": "resume",
        "stop": "stop",
        "play pause": "play_pause",
    }
    YOUTUBE_HINTS = ("youtube", "youtube.com", "youtu.be")
    SPOTIFY_HINTS = ("spotify", "spotify.com")

    def validate_parameters(self, parameters):
        parameters = parameters or {}
        candidate = parameters.get("name") or parameters.get("source")

        if candidate and str(candidate).strip():
            return None

        resource = (parameters.get("resource") or "").strip().lower()

        if resource in self.MEDIA_KEY_COMMANDS:
            return None

        return "Please specify which song or music to play"

    def execute(self, parameters):
        parameters = parameters or {}
        name = (parameters.get("name") or "").strip()
        source = (parameters.get("source") or "").strip()
        resource = (parameters.get("resource") or "").strip().lower()

        control_command = self.resolve_control_command(name or resource)

        if control_command:
            if self.send_media_key(control_command):
                return self.build_control_response(control_command)

            return f"I understood '{control_command}', but I could not control media playback on this system."

        query = name or source

        if not query:
            return "Please specify which song or music to play"

        local_media = self.resolve_local_media(query)

        if local_media:
            try:
                os.startfile(str(local_media))
                return f"Playing music: {query}"
            except OSError:
                return f"I found {query}, but could not open it."

        target_url = self.resolve_streaming_target(query)

        try:
            opened = webbrowser.open(target_url)
        except Exception:
            opened = False

        if not opened:
            return f"Music is ready for {query}, but I could not open the browser automatically."

        platform = self.detect_platform(query)

        if platform == "spotify":
            return f"Opening Spotify results for {self.clean_query(query)}"

        return f"Playing music: {self.clean_query(query)}"

    def resolve_control_command(self, value):
        normalized_value = self.clean_query(value).lower()

        if normalized_value in self.CONTROL_ALIASES:
            return self.CONTROL_ALIASES[normalized_value]

        return None

    def send_media_key(self, command):
        virtual_key = self.MEDIA_KEY_COMMANDS.get(command)

        if virtual_key is None:
            return False

        try:
            ctypes.windll.user32.keybd_event(virtual_key, 0, 0, 0)
            ctypes.windll.user32.keybd_event(virtual_key, 0, 2, 0)
            return True
        except Exception:
            return False

    def resolve_local_media(self, query):
        candidate = Path(query.strip().strip("\"'")).expanduser()

        if candidate.exists() and candidate.is_file():
            return candidate

        return None

    def resolve_streaming_target(self, query):
        cleaned_query = self.clean_query(query)
        lowered_query = cleaned_query.lower()

        if self.looks_like_url(cleaned_query):
            return cleaned_query

        if any(hint in lowered_query for hint in self.SPOTIFY_HINTS):
            spotify_query = self.strip_platform_hints(cleaned_query, self.SPOTIFY_HINTS)
            return f"https://open.spotify.com/search/{quote_plus(spotify_query or cleaned_query)}"

        youtube_query = self.strip_platform_hints(cleaned_query, self.YOUTUBE_HINTS)
        return f"https://www.youtube.com/results?search_query={quote_plus(youtube_query or cleaned_query)}"

    def detect_platform(self, query):
        lowered_query = query.lower()

        if any(hint in lowered_query for hint in self.SPOTIFY_HINTS):
            return "spotify"

        return "youtube"

    def clean_query(self, query):
        cleaned_query = " ".join(str(query).split())
        cleaned_query = re.sub(r"\b(play|music)\b", " ", cleaned_query, flags=re.IGNORECASE)
        cleaned_query = re.sub(r"\s+", " ", cleaned_query).strip(" -")
        return cleaned_query or str(query).strip()

    def strip_platform_hints(self, query, hints):
        cleaned_query = query

        for hint in hints:
            cleaned_query = re.sub(
                rf"\bon\s+{re.escape(hint)}\b",
                " ",
                cleaned_query,
                flags=re.IGNORECASE,
            )
            cleaned_query = re.sub(
                rf"\b{re.escape(hint)}\b",
                " ",
                cleaned_query,
                flags=re.IGNORECASE,
            )

        cleaned_query = re.sub(r"\s+", " ", cleaned_query).strip()
        return cleaned_query

    @staticmethod
    def looks_like_url(value):
        lowered_value = value.lower()
        return lowered_value.startswith(("http://", "https://", "www."))

    @staticmethod
    def build_control_response(command):
        responses = {
            "next": "Skipping to the next track.",
            "previous": "Going back to the previous track.",
            "pause": "Pausing playback.",
            "resume": "Resuming playback.",
            "stop": "Stopping playback.",
            "play_pause": "Toggling play and pause.",
        }
        return responses.get(command, f"Sent media command: {command}")
