from collections import Counter, defaultdict
from datetime import datetime


class Memory:

    def __init__(self, history_limit=100):
        self.history_limit = history_limit
        self.command_history = []
        self.command_counter = Counter()
        self.action_counter = Counter()
        self.resource_counter = Counter()
        self.hourly_action_counter = defaultdict(Counter)
        self.last_suggested_command = None
        self.last_suggested_count = 0
        self.last_suggestion_reason = None
        self.last_action = None

    def remember(self, user_input, action_schema):
        timestamp = datetime.now()
        normalized_command = self._normalize_command(user_input)
        action = action_schema.get("action")
        resource = action_schema.get("resource")

        record = {
            "timestamp": timestamp,
            "user_input": user_input,
            "normalized_command": normalized_command,
            "action": action,
            "resource": resource,
            "parameters": dict(action_schema.get("parameters", {})),
            "source": action_schema.get("metadata", {}).get("source", "unknown"),
        }

        self.command_history.append(record)

        if len(self.command_history) > self.history_limit:
            self.command_history.pop(0)

        if normalized_command:
            self.command_counter[normalized_command] += 1

        if action:
            self.action_counter[action] += 1
            self.hourly_action_counter[timestamp.hour][action] += 1

        if resource:
            self.resource_counter[resource] += 1

    def get_recent_commands(self, limit=5):
        return self.command_history[-limit:]

    def get_last_command(self):
        if not self.command_history:
            return None

        return self.command_history[-1]

    def update_last_action(self, action_schema):
        if not action_schema:
            return

        self.last_action = {
            "action": action_schema.get("action"),
            "resource": action_schema.get("resource"),
            "parameters": dict(action_schema.get("parameters", {})),
        }

    def get_last_action(self):
        return self.last_action

    def get_top_action(self):
        if not self.action_counter:
            return None
        return self.action_counter.most_common(1)[0]

    def get_top_command(self):
        if not self.command_counter:
            return None

        return self.command_counter.most_common(1)[0]

    def get_top_resource(self):
        if not self.resource_counter:
            return None
        return self.resource_counter.most_common(1)[0]

    def get_top_resource_for_action(self, action):
        if not action:
            return None

        resource_counter = Counter(
            record["resource"]
            for record in self.command_history
            if record["action"] == action and record.get("resource")
        )

        if not resource_counter:
            return None

        return resource_counter.most_common(1)[0]

    def get_hourly_top_action(self, hour):
        action_counts = self.hourly_action_counter.get(hour)

        if not action_counts:
            return None

        return action_counts.most_common(1)[0]

    def get_suggestion(self):
        top_command = self.get_top_command()

        if not top_command:
            self.last_suggestion_reason = None
            return None

        command, count = top_command

        if count < 2:
            self.last_suggestion_reason = None
            return None

        if (
            command == self.last_suggested_command
            and count <= self.last_suggested_count
        ):
            return None

        self.last_suggested_command = command
        self.last_suggested_count = count
        self.last_suggestion_reason = {
            "command": command,
            "count": count,
            "message": f"Because you opened {command.split(' ', 1)[1]} {count} times recently"
            if command.startswith("open ") and len(command.split()) > 1
            else f"Because you used '{command}' {count} times recently",
        }
        return f"You usually {command}. Want me to?"

    def explain_suggestion(self, user_input=None):
        if not self.last_suggestion_reason:
            return "I have not made any suggestion yet."

        if user_input:
            requested_topic = self._extract_suggestion_target(user_input)
            suggested_topic = self._extract_suggestion_target(
                self.last_suggestion_reason["command"]
            )

            if requested_topic and suggested_topic and requested_topic != suggested_topic:
                return "That was not my latest suggestion."

        return self.last_suggestion_reason["message"]

    def summarize(self):
        parts = []
        top_command = self.get_top_command()
        top_action = self.get_top_action()
        top_resource = self.get_top_resource()

        if top_command:
            command, count = top_command
            parts.append(f"Frequent command: {command} ({count} times)")

        if top_action:
            action, count = top_action
            parts.append(f"Frequent action: {action} ({count} times)")

        if top_resource:
            resource, count = top_resource
            parts.append(f"Frequent resource: {resource} ({count} times)")

        if not parts:
            return "No memory available yet."

        return " | ".join(parts)

    @staticmethod
    def _normalize_command(user_input):
        return " ".join(user_input.lower().split())

    @staticmethod
    def _extract_suggestion_target(text):
        normalized_text = " ".join((text or "").lower().split())

        if normalized_text.startswith("why did you suggest "):
            return normalized_text.replace("why did you suggest ", "", 1).strip()

        if normalized_text.startswith("why suggest "):
            return normalized_text.replace("why suggest ", "", 1).strip()

        if normalized_text.startswith("open "):
            return normalized_text.replace("open ", "", 1).strip()

        return normalized_text
