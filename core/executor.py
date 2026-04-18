import logging
import re


LOGGER = logging.getLogger(__name__)


class Executor:
    RESERVED_OPEN_RESOURCES = {"tab", "next", "previous"}
    CONTEXTUAL_APP_ACTIONS = {"browser_control"}
    BROWSER_APPS = {"chrome", "edge", "firefox"}
    FAILURE_MARKERS = (
        "invalid command format",
        "missing action in command",
        "that request looks like a control command",
        "please specify",
        "blocked unsafe command",
        "unsupported command",
        "command failed",
        "failed to execute",
        "something went wrong while executing",
        "i don't know how to perform that action",
        "could not find",
        "couldn't find",
        "confirmation required before",
        "unsupported",
    )

    def __init__(self, plugin_manager, context_manager=None):

        self.plugin_manager = plugin_manager
        self.context_manager = context_manager

    def execute(self, action_schema):
        if isinstance(action_schema, list):
            LOGGER.info("Executor received multi-action payload with %s actions", len(action_schema))

            if not action_schema:
                return "No actions to execute."

            responses = []

            for index, action in enumerate(action_schema, start=1):
                LOGGER.info("Executing step %s/%s", index, len(action_schema))
                try:
                    step_response = self.execute(action)
                except Exception as exc:
                    failed_action = self.normalize_action(action.get("action")) if isinstance(action, dict) else "unknown"
                    failed_resource = self._describe_action_target(action)
                    step_response = self._build_step_failure_message(failed_action, failed_resource, exc)
                    LOGGER.exception(
                        "Multi-step execution crashed at step %s/%s for action %s",
                        index,
                        len(action_schema),
                        failed_action,
                    )

                responses.append(step_response)

                if self.is_failure_response(step_response):
                    LOGGER.warning(
                        "Stopping multi-step execution at step %s/%s due to failure: %s",
                        index,
                        len(action_schema),
                        step_response,
                    )
                    break

            return " | ".join(response for response in responses if response)

        try:
            return self._execute_single_step(action_schema)
        except Exception as exc:
            failed_action = self.normalize_action(action_schema.get("action")) if isinstance(action_schema, dict) else "unknown"
            failed_target = self._describe_action_target(action_schema)
            LOGGER.exception(
                "Executor failed while handling single-step action=%s target=%s",
                failed_action,
                failed_target,
            )
            return self._build_step_failure_message(failed_action, failed_target, exc)

    def _execute_single_step(self, action_schema):

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

        parameters = self._inject_context_parameters(action, parameters)

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
                    "Plugin %s crashed during execution for action=%s target=%s",
                    plugin.__class__.__name__,
                    action,
                    self._describe_action_target(
                        {
                            "action": action,
                            "resource": resource,
                            "parameters": parameters,
                        }
                    ),
                )
                failed_target = self._describe_action_target(
                    {
                        "action": action,
                        "resource": resource,
                        "parameters": parameters,
                    }
                )
                return self._build_step_failure_message(action, failed_target, exc)

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

    def _inject_context_parameters(self, action, parameters):
        if action not in self.CONTEXTUAL_APP_ACTIONS:
            return parameters

        if not self.context_manager:
            return parameters

        active_app = str(self.context_manager.get_active_app() or "").strip().lower()

        if not active_app:
            return parameters

        if action == "browser_control" and active_app not in self.BROWSER_APPS:
            return parameters

        browser = str(parameters.get("browser") or "").strip().lower()

        if browser and browser != "default":
            return parameters

        updated_parameters = dict(parameters)
        updated_parameters["browser"] = active_app
        LOGGER.info(
            "Executor injected active app '%s' into action '%s' from runtime context.",
            active_app,
            action,
        )
        return updated_parameters

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

    @classmethod
    def is_failure_response(cls, response):
        normalized_response = str(response or "").strip().lower()

        if not normalized_response:
            return False

        return any(marker in normalized_response for marker in cls.FAILURE_MARKERS)

    @classmethod
    def _describe_action_target(cls, action_schema):
        if not isinstance(action_schema, dict):
            return "unknown"

        parameters = action_schema.get("parameters") or {}
        for key in ("command", "name", "query", "topic", "resource"):
            value = parameters.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip()

        resource = action_schema.get("resource")

        if isinstance(resource, str) and resource.strip():
            return resource.strip()

        return cls.normalize_action(action_schema.get("action")) or "unknown"

    @staticmethod
    def _build_step_failure_message(action, target, exc):
        descriptor = target or action or "step"
        return f"Failed to execute '{descriptor}' command"
