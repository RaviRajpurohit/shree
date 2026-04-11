import copy
import logging


LOGGER = logging.getLogger(__name__)


class PlannerEngine:

    def build_plan(self, action_schema):
        if not action_schema:
            LOGGER.warning("PlannerEngine received empty action schema.")
            return []

        actions = action_schema if isinstance(action_schema, list) else [action_schema]
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
