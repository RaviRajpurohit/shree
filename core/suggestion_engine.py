class SuggestionEngine:
    SESSION_WINDOW = 5
    MIN_PATTERN_SUPPORT = 2
    CONTEXT_LENGTHS = (2, 1)

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
        payload = self._build_next_action_suggestion()

        if payload:
            return self._publish_suggestion(payload)

        self.memory.last_suggestion_reason = None
        self.latest_suggestion = None
        return None

    def _build_next_action_suggestion(self):
        records = self.memory.command_history

        if len(records) < 3:
            return None

        recent_records = records[-self.SESSION_WINDOW :]

        for context_length in self.CONTEXT_LENGTHS:
            if len(recent_records) < context_length:
                continue

            context_records = recent_records[-context_length:]
            context_signature = [self._sequence_signature(record) for record in context_records]
            matches = self._find_next_action_matches(records, context_signature)

            if not matches:
                continue

            best_match = max(matches, key=lambda item: (item["count"], item["next_command"]))

            if best_match["count"] < self.MIN_PATTERN_SUPPORT:
                continue

            if best_match["next_signature"] == context_signature[-1]:
                continue

            return self._build_payload(context_records, best_match)

        return None

    def _find_next_action_matches(self, records, context_signature):
        context_length = len(context_signature)
        cutoff_index = len(records) - context_length
        matches = {}

        for start_index in range(cutoff_index):
            end_index = start_index + context_length

            if end_index >= len(records):
                break

            candidate_context = [
                self._sequence_signature(record)
                for record in records[start_index:end_index]
            ]

            if candidate_context != context_signature:
                continue

            next_record = records[end_index]
            next_signature = self._sequence_signature(next_record)

            if next_signature not in matches:
                matches[next_signature] = {
                    "count": 0,
                    "record": next_record,
                    "next_signature": next_signature,
                    "next_command": self._format_history_record(next_record),
                }

            matches[next_signature]["count"] += 1

        return list(matches.values())

    def _build_payload(self, context_records, match):
        next_record = match["record"]
        next_command = match["next_command"]
        suggested_command = self._format_suggestion_command(next_record)
        context_summary = self._summarize_context(context_records)
        suggestion = self._build_suggestion_text(next_record, context_summary, next_command)
        reason = f"Because after {context_summary}, your next step is usually {next_command}."

        return {
            "key": f"next:{'|'.join(self._sequence_signature(record) for record in context_records)}->{match['next_signature']}",
            "command": suggested_command,
            "strength": match["count"],
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

    def _summarize_context(self, context_records):
        if not context_records:
            return "that"

        primary_record = None

        for record in context_records:
            if record.get("action") == "open" and record.get("resource"):
                primary_record = record
                break

        if primary_record:
            return f"opening {primary_record.get('resource')}"

        return self._format_history_record(context_records[-1])

    def _build_suggestion_text(self, next_record, context_summary, next_command):
        action = next_record.get("action")

        if action == "search":
            return f"You usually search after {context_summary}. Want me to search something?"

        if action == "browser_control" and next_record.get("resource") == "new_tab":
            return f"You usually open a tab after {context_summary}. Want me to?"

        if action == "open" and next_record.get("resource"):
            return f"You usually open {next_record['resource']} after {context_summary}. Want me to?"

        return f"You usually {next_command} after {context_summary}. Want me to?"

    @staticmethod
    def _format_suggestion_command(record):
        action = record.get("action")
        resource = record.get("resource", "")

        if action == "search":
            return "search"

        if action == "browser_control" and resource == "new_tab":
            return "open new tab"

        if action == "open" and resource:
            return f"open {resource}"

        return SuggestionEngine._format_history_record(record)

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
            return f"search {query}".strip() or "search"

        if action == "play_music":
            target = (parameters.get("name") or resource or "").strip()
            return f"play {target}".strip()

        return " ".join(part for part in [action, resource] if part).strip()
