import copy
import logging


LOGGER = logging.getLogger(__name__)


class PlannerEngine:
    DEFAULT_BROWSER = "chrome"

    def build_plan(self, action_schema):
        if not action_schema:
            LOGGER.warning("PlannerEngine received empty action schema.")
            return []

        actions = action_schema if isinstance(action_schema, list) else [action_schema]
        actions = self._expand_browser_dependencies(actions)
        plan = []

        for index, action in enumerate(actions, start=1):
            if not isinstance(action, dict):
                LOGGER.warning("PlannerEngine skipped invalid action at step %s: %s", index, action)
                continue

            planned_step = copy.deepcopy(action)
            planned_step["step"] = index
            plan.append(planned_step)

        LOGGER.info("PlannerEngine created plan with %s step(s).", len(plan))
        return plan

    def _expand_browser_dependencies(self, actions):
        normalized_actions = [action for action in actions if isinstance(action, dict)]

        if not normalized_actions:
            return actions

        if not self._contains_search_action(normalized_actions):
            return actions

        if self._contains_browser_open(normalized_actions):
            return actions

        LOGGER.info(
            "PlannerEngine prepended browser launch because search action had no browser open step."
        )

        return [self._build_open_browser_step(), *actions]

    @staticmethod
    def _contains_search_action(actions):
        return any(action.get("action") == "search" for action in actions)

    def _contains_browser_open(self, actions):
        for action in actions:
            if action.get("action") != "open":
                continue

            resource = str(action.get("resource") or "").strip().lower()
            parameters = action.get("parameters") or {}
            app_name = str(parameters.get("name") or resource).strip().lower()

            if app_name == self.DEFAULT_BROWSER:
                return True

        return False

    def _build_open_browser_step(self):
        return {
            "action": "open",
            "resource": self.DEFAULT_BROWSER,
            "device": "local",
            "parameters": {"name": self.DEFAULT_BROWSER},
        }
