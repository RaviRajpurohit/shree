import logging

from core.intent_engine import IntentEngine
from core.context_manager import ContextManager
from core.intent_router import IntentRouter
from core.memory import Memory
from core.memory_manager import MemoryManager
from core.normalization_engine import NormalizationEngine
from core.normalizer import normalize
from core.offline_knowledge_engine import OfflineKnowledgeEngine
from core.planner_engine import PlannerEngine
from core.suggestion_engine import SuggestionEngine
from core.executor import Executor
from plugins.plugin_manager import PluginManager


LOGGER = logging.getLogger(__name__)


class AgentLoop:

    def __init__(self):

        self.intent_engine = IntentEngine()
        self.context_manager = ContextManager()
        self.memory = Memory()
        self.memory_manager = MemoryManager()
        self.normalization_engine = NormalizationEngine()
        self.offline_knowledge_engine = OfflineKnowledgeEngine()
        self.planner_engine = PlannerEngine()
        self.intent_router = IntentRouter(self.intent_engine, self.memory, self.context_manager)
        self.plugin_manager = PluginManager()
        self.executor = Executor(self.plugin_manager, self.context_manager)
        self.suggestion_engine = SuggestionEngine(self.memory, self.memory_manager)

    def process(self, user_input):
        LOGGER.info("User input received: %s", user_input)

        normalized_user_input = self.normalization_engine.normalize(user_input)
        normalized_input = " ".join(normalized_user_input.lower().split())
        offline_response = self.offline_knowledge_engine.respond(normalized_user_input)

        if offline_response:
            LOGGER.info("Resolved with OfflineKnowledgeEngine: %s", offline_response)
            return offline_response

        action_schema = normalize(self.intent_router.route(normalized_user_input))

        if not action_schema:
            LOGGER.warning("No action schema could be created for input: %s", user_input)
            return "Sorry, I couldn't understand."

        LOGGER.info("Resolved action schema: %s", action_schema)

        if isinstance(action_schema, list):
            execution_plan = self.planner_engine.build_plan(action_schema)

            if not execution_plan:
                LOGGER.warning("PlannerEngine did not produce any executable steps for input: %s", user_input)
                return "Sorry, I couldn't understand."

            LOGGER.info("Execution plan: %s", execution_plan)
            response = self.executor.execute(execution_plan)
            LOGGER.info("Execution response: %s", response)

            for action in execution_plan:
                self.memory.remember(user_input, action)
                self.memory.update_last_action(action)
                self.record_successful_action(action, response)
                self.update_runtime_context(action, response)

            self.suggestion_engine.update_after_command()
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

        execution_plan = self.planner_engine.build_plan(action_schema)

        if not execution_plan:
            LOGGER.warning("PlannerEngine did not produce any executable steps for input: %s", user_input)
            return "Sorry, I couldn't understand."

        LOGGER.info("Execution plan: %s", execution_plan)
        response = self.executor.execute(execution_plan)
        LOGGER.info("Execution response: %s", response)

        for action in execution_plan:
            self.memory.remember(user_input, action)
            self.memory.update_last_action(action)
            self.record_successful_action(action, response)
            self.update_runtime_context(action, response)

        self.suggestion_engine.update_after_command()

        suggested_command = ""

        if self.memory.last_suggestion_reason:
            suggested_command = self.memory.last_suggestion_reason.get("command", "")

        if normalized_input == suggested_command:
            self.memory.last_suggested_command = None
            self.memory.last_suggested_count = 0
            self.memory.last_suggestion_reason = None
            self.suggestion_engine.clear_suggestion()

        return response

    def get_suggestion(self):
        suggestion = self.suggestion_engine.get_suggestion()

        if suggestion:
            LOGGER.info("Suggestion generated: %s", suggestion)

        return suggestion

    def get_memory_summary(self):
        return self.memory.summarize()

    def record_successful_action(self, action_schema, response):
        if not self._should_record_action(action_schema, response):
            return

        self.memory_manager.record_action(
            action_schema.get("action"),
            action_schema.get("resource", ""),
        )

    def update_runtime_context(self, action_schema, response):
        if not self._should_record_action(action_schema, response):
            return

        self.context_manager.update_context(
            action_schema.get("action"),
            action_schema.get("resource", ""),
        )

    @staticmethod
    def _should_record_action(action_schema, response):
        if not isinstance(action_schema, dict):
            return False

        action = action_schema.get("action")

        if action in {None, "", "unknown", "show_history", "explain_suggestion"}:
            return False

        normalized_response = str(response or "").strip().lower()

        failure_markers = (
            "i don't know how to perform that action",
            "invalid command format",
            "missing action in command",
            "couldn't understand",
            "llm unavailable",
            "please specify",
            "could not find",
            "confirmation required before",
            "that request looks like a control command",
            "unsupported",
            "something went wrong while executing",
        )

        return not any(marker in normalized_response for marker in failure_markers)
