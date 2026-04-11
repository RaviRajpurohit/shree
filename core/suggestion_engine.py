class SuggestionEngine:
    FREQUENT_ACTION_THRESHOLD = 3
    REPEATED_SEQUENCE_THRESHOLD = 2
    SEQUENCE_LENGTH = 3

    def __init__(self, memory, memory_manager):
        self.memory = memory
        self.memory_manager = memory_manager
        self.latest_suggestion = None

    def update_after_command(self):
        self.latest_suggestion = self._build_suggestion()
        return self.latest_suggestion

    def get_suggestion(self):
        if self.latest_suggestion:
            return self.latest_suggestion

        self.latest_suggestion = self._build_suggestion()
        return self.latest_suggestion

    def clear_suggestion(self):
        self.latest_suggestion = None

    def _build_suggestion(self):
        sequence_suggestion = self._build_repeated_sequence_suggestion()

        if sequence_suggestion:
            return self._publish_suggestion(sequence_suggestion)

        frequent_action_suggestion = self._build_frequent_action_suggestion()

        if frequent_action_suggestion:
            return self._publish_suggestion(frequent_action_suggestion)

        self.memory.last_suggestion_reason = None
        return None

    def _build_frequent_action_suggestion(self):
        top_actions = self.memory_manager.get_top_actions()

        if not top_actions:
            return None

        top_action = top_actions[0]
        count = top_action.get("count", 0)

        if count < self.FREQUENT_ACTION_THRESHOLD:
            return None

        command = self._format_action_command(top_action)
        suggestion = f"You usually {command}. Want me to?"
        reason = f"Because you used '{command}' {count} times recently"

        if top_action.get("action") == "open" and top_action.get("resource"):
            reason = f"Because you opened {top_action['resource']} {count} times recently"

        return {
            "key": f"frequent:{top_action.get('action')}:{top_action.get('resource')}",
            "command": command,
            "strength": count,
            "suggestion": suggestion,
            "reason": reason,
        }

    def _build_repeated_sequence_suggestion(self):
        records = self.memory.command_history

        if len(records) < self.SEQUENCE_LENGTH * self.REPEATED_SEQUENCE_THRESHOLD:
            return None

        last_sequence = [
            self._sequence_signature(record)
            for record in records[-self.SEQUENCE_LENGTH :]
        ]

        prior_signatures = [
            self._sequence_signature(record)
            for record in records[:-self.SEQUENCE_LENGTH]
        ]

        repeats = 1

        for start_index in range(len(prior_signatures) - self.SEQUENCE_LENGTH + 1):
            if prior_signatures[start_index : start_index + self.SEQUENCE_LENGTH] == last_sequence:
                repeats += 1

        if repeats < self.REPEATED_SEQUENCE_THRESHOLD:
            return None

        command_steps = [
            self._format_history_record(record)
            for record in records[-self.SEQUENCE_LENGTH :]
        ]
        command = " then ".join(command_steps)
        suggestion = f"You often {command}. Want me to do that?"
        reason = f"Because you often follow this pattern: {', then '.join(command_steps)}"

        return {
            "key": f"sequence:{'|'.join(last_sequence)}",
            "command": command,
            "strength": repeats,
            "suggestion": suggestion,
            "reason": reason,
        }

    def _publish_suggestion(self, payload):
        if (
            payload["key"] == self.memory.last_suggested_command
            and payload["strength"] <= self.memory.last_suggested_count
        ):
            return self.latest_suggestion

        self.memory.last_suggested_command = payload["key"]
        self.memory.last_suggested_count = payload["strength"]
        self.memory.last_suggestion_reason = {
            "command": payload["command"],
            "count": payload["strength"],
            "message": payload["reason"],
        }
        self.latest_suggestion = payload["suggestion"]
        return self.latest_suggestion

    @staticmethod
    def _sequence_signature(record):
        parameters = record.get("parameters", {})
        return "|".join(
            [
                record.get("action", ""),
                record.get("resource", ""),
                parameters.get("browser", ""),
                parameters.get("query", ""),
            ]
        )

    @staticmethod
    def _format_action_command(record):
        action = record.get("action")
        resource = record.get("resource", "")

        if action == "open" and resource:
            return f"open {resource}"

        if action == "browser_control":
            if resource == "new_tab":
                return "open new tab"
            if resource == "next_tab":
                return "go to the next tab"
            if resource == "previous_tab":
                return "go to the previous tab"

        if action == "search":
            return "search"

        if action == "play_music" and resource:
            return f"play {resource}"

        return " ".join(part for part in [action, resource] if part).strip()

    @staticmethod
    def _format_history_record(record):
        action = record.get("action")
        resource = record.get("resource", "")
        parameters = record.get("parameters", {})

        if action == "open" and resource:
            return f"open {resource}"

        if action == "browser_control":
            if resource == "new_tab":
                return "open new tab"
            if resource == "next_tab":
                return "go to the next tab"
            if resource == "previous_tab":
                return "go to the previous tab"

        if action == "search":
            query = parameters.get("query", "").strip()
            return f"search {query}".strip()

        if action == "play_music":
            target = (parameters.get("name") or resource or "").strip()
            return f"play {target}".strip()

        return " ".join(part for part in [action, resource] if part).strip()
