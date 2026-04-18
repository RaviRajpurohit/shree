import logging


LOGGER = logging.getLogger(__name__)


class ContextManager:
    SESSION_LIMIT = 5
    BROWSER_APPS = {"chrome", "edge", "firefox"}

    def __init__(self):
        self._context = {
            "active_app": "",
            "last_action": "",
            "session": [],
        }

    def update_context(self, action, resource):
        normalized_action = str(action or "").strip().lower()
        normalized_resource = str(resource or "").strip().lower()

        if not normalized_action:
            LOGGER.debug("Skipped runtime context update because action was empty.")
            return

        self._context["last_action"] = normalized_action
        self._append_session(normalized_action, normalized_resource)

        if self._should_update_active_app(normalized_action, normalized_resource):
            self._context["active_app"] = normalized_resource

        LOGGER.info("Updated runtime context: %s", self._context)

    def get_active_app(self):
        return self._context["active_app"]

    def get_last_action(self):
        return self._context["last_action"]

    def get_session(self):
        return list(self._context["session"])

    def _append_session(self, action, resource):
        entry = {
            "action": action,
            "resource": resource,
        }
        self._context["session"].append(entry)
        self._context["session"] = self._context["session"][-self.SESSION_LIMIT :]

    def _should_update_active_app(self, action, resource):
        if not resource:
            return False

        if action == "open":
            return True

        return action == "browser_control" and resource in self.BROWSER_APPS
