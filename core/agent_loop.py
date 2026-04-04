import logging
from datetime import datetime

from core.intent_engine import IntentEngine
from core.intent_router import IntentRouter
from core.memory import Memory
from core.suggestion_engine import SuggestionEngine
from core.executor import Executor
from plugins.plugin_manager import PluginManager


LOGGER = logging.getLogger(__name__)


class AgentLoop:

    def __init__(self):

        self.intent_engine = IntentEngine()
        self.memory = Memory()
        self.intent_router = IntentRouter(self.intent_engine, self.memory)
        self.plugin_manager = PluginManager()
        self.executor = Executor(self.plugin_manager)
        self.suggestion_engine = SuggestionEngine(self.memory)

    def process(self, user_input):
        LOGGER.info("User input received: %s", user_input)

        normalized_input = " ".join(user_input.lower().split())

        action_schema = self.intent_router.route(user_input)

        fallback_response = self.handle_basic_queries(user_input, action_schema)

        if fallback_response:
            LOGGER.info("Resolved with offline smart answer: %s", fallback_response)
            return fallback_response

        if not action_schema:
            LOGGER.warning("No action schema could be created for input: %s", user_input)
            return "Sorry, I couldn't understand."

        LOGGER.info("Resolved action schema: %s", action_schema)

        if isinstance(action_schema, list):
            response = self.executor.execute(action_schema)
            LOGGER.info("Execution response: %s", response)

            for action in action_schema:
                self.memory.remember(user_input, action)
                self.memory.update_last_action(action)

            return response

        if action_schema.get("action") == "show_history":
            history = self.memory.get_recent_commands(limit=5)

            if not history:
                return "No commands recorded yet."

            return "Recent commands: " + ", ".join(
                record["user_input"] for record in history
            )

        if action_schema.get("action") == "explain_suggestion":
            target = action_schema.get("parameters", {}).get("target")
            return self.memory.explain_suggestion(target)

        response = self.executor.execute(action_schema)
        LOGGER.info("Execution response: %s", response)

        self.memory.remember(user_input, action_schema)
        self.memory.update_last_action(action_schema)

        if normalized_input == self.memory.last_suggested_command:
            self.memory.last_suggested_command = None
            self.memory.last_suggested_count = 0

        return response

    def handle_basic_queries(self, user_input, action_schema):
        if not action_schema or isinstance(action_schema, list):
            return None

        if action_schema.get("action") != "unknown":
            return None

        text = user_input.lower()

        if "who are you" in text:
            return "I am Shree, your offline AI assistant."

        if "date" in text:
            return datetime.now().strftime("%d %B %Y")

        if "time" in text:
            return datetime.now().strftime("%H:%M")

        return None

    def get_suggestion(self):
        suggestion = self.suggestion_engine.get_suggestion()

        if suggestion:
            LOGGER.info("Suggestion generated: %s", suggestion)

        return suggestion

    def get_memory_summary(self):
        return self.memory.summarize()
