import logging
import re


LOGGER = logging.getLogger(__name__)


class Executor:
    RESERVED_OPEN_RESOURCES = {"tab", "next", "previous"}

    def __init__(self, plugin_manager):

        self.plugin_manager = plugin_manager

    def execute(self, action_schema):
        if isinstance(action_schema, list):
            LOGGER.info("Executor received multi-action payload with %s actions", len(action_schema))
            responses = []

            for index, action in enumerate(action_schema, start=1):
                LOGGER.info("Executing step %s/%s", index, len(action_schema))
                responses.append(self.execute(action))

            return " | ".join(response for response in responses if response)

        if not isinstance(action_schema, dict):
            LOGGER.warning("Executor received invalid action schema: %s", action_schema)
            return "Invalid command format."

        action = self.normalize_action(action_schema.get("action"))
        resource = action_schema.get("resource")
        parameters = dict(action_schema.get("parameters") or {})
        LOGGER.info("Executor received action=%s resource=%s parameters=%s", action, resource, parameters)

        if not action:
            return "Missing action in command."

        if action == "open" and self.is_reserved_open_resource(resource):
            return "That request looks like a control command, not an application to open."

        if action == "open" and resource and not parameters.get("name"):
            parameters.setdefault("name", resource)

        if action == "play_music" and resource and not parameters.get("resource"):
            parameters["resource"] = resource

        plugin = self.plugin_manager.get_plugin(action)

        if plugin:
            validation_error = self.validate_plugin_execution(plugin, parameters)

            if validation_error:
                LOGGER.warning(
                    "Validation failed for plugin %s: %s",
                    plugin.__class__.__name__,
                    validation_error,
                )
                return validation_error

            LOGGER.info("Executor dispatching to plugin: %s", plugin.__class__.__name__)
            try:
                return plugin.execute(parameters)
            except Exception as exc:
                LOGGER.exception(
                    "Plugin %s crashed during execution",
                    plugin.__class__.__name__,
                )
                return f"Something went wrong while executing '{action}': {exc}"

        message = parameters.get("message")

        if message:
            LOGGER.info("Executor returning fallback message from parameters.")
            return message

        LOGGER.warning("No plugin found for action: %s", action)
        return "I don't know how to perform that action."

    @staticmethod
    def validate_plugin_execution(plugin, parameters):
        if hasattr(plugin, "validate_parameters"):
            return plugin.validate_parameters(parameters)

        return None

    @staticmethod
    def normalize_action(action):
        if not action:
            return ""

        action = re.sub(r'(?<!^)(?=[A-Z])', '_', action).lower()
        action = action.replace(" ", "_")

        return action

    @classmethod
    def is_reserved_open_resource(cls, resource):
        normalized_resource = str(resource or "").strip().lower()
        tokens = set(normalized_resource.split())
        return any(term in tokens for term in cls.RESERVED_OPEN_RESOURCES)
