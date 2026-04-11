import logging
import re
from datetime import datetime

LOGGER = logging.getLogger(__name__)


class OfflineKnowledgeEngine:
    IDENTITY_RESPONSES = (
        "who are you",
        "what are you",
        "tell me who you are",
        "introduce yourself",
    )
    TIME_RESPONSES = (
        "what is time",
        "what time is it",
        "tell me the time",
        "current time",
        "time",
    )
    DATE_RESPONSES = (
        "what is date",
        "what is the date",
        "tell me the date",
        "current date",
        "date",
    )
    GREETING_RESPONSES = {
        "hello",
        "hi",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
    }
    HELP_RESPONSES = {
        "help",
        "basic help",
        "what can you do",
        "show help",
        "commands",
    }

    def respond(self, user_input):
        normalized_input = self._normalize_input(user_input)

        if not normalized_input:
            return None

        if normalized_input in self.IDENTITY_RESPONSES:
            LOGGER.info("OfflineKnowledgeEngine handled identity query.")
            return "I am Shree, your offline AI assistant."

        if normalized_input in self.TIME_RESPONSES:
            LOGGER.info("OfflineKnowledgeEngine handled time query.")
            return datetime.now().strftime("%H:%M")

        if normalized_input in self.DATE_RESPONSES:
            LOGGER.info("OfflineKnowledgeEngine handled date query.")
            return datetime.now().strftime("%d %B %Y")

        if normalized_input in self.GREETING_RESPONSES:
            LOGGER.info("OfflineKnowledgeEngine handled greeting.")
            return "Hello! I am Shree. How can I help you offline today?"

        if normalized_input in self.HELP_RESPONSES:
            LOGGER.info("OfflineKnowledgeEngine handled help query.")
            return (
                "I can help with offline commands like opening apps, opening files, "
                "playing music, reminders, browser controls, command history, and suggestions."
            )

        return None

    @staticmethod
    def _normalize_input(user_input):
        text = str(user_input or "").lower().strip()
        text = re.sub(r"[^\w\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()
