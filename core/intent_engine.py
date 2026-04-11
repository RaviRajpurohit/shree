import json
import logging
import re
from difflib import get_close_matches

from llm.ollama_client import generate


LOGGER = logging.getLogger(__name__)

REQUIRED_INTENT_KEYS = ("action", "resource", "device", "parameters")


def clean_input(text: str) -> str:
    cleaned = text.lower()

    filler_patterns = [
        r"\bhello\b",
        r"\bhi\b",
        r"\bhii+\b",
        r"\bhey there\b",
        r"\bplease\b",
        r"\bcan you\b",
        r"\bcould you\b",
        r"\bwould you\b",
        r"\bkindly\b",
        r"\bhey\b",
        r"\bshree\b",
    ]

    for pattern in filler_patterns:
        cleaned = re.sub(pattern, " ", cleaned)

    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def clean_llm_output(text: str) -> dict:
    fallback = {
        "action": "unknown",
        "resource": "",
        "device": "local",
        "parameters": {},
    }

    if not text:
        return fallback

    cleaned_text = re.sub(r"```(?:json)?", " ", str(text), flags=re.IGNORECASE)
    candidate = _extract_first_valid_json_object(cleaned_text)

    if not _has_valid_intent_shape(candidate):
        return fallback

    return {
        "action": candidate["action"],
        "resource": candidate["resource"],
        "device": candidate["device"],
        "parameters": candidate["parameters"],
    }


def _extract_first_valid_json_object(text):
    start_positions = [index for index, char in enumerate(text) if char == "{"] 

    for start in start_positions:
        brace_count = 0

        for index in range(start, len(text)):
            if text[index] == "{":
                brace_count += 1
            elif text[index] == "}":
                brace_count -= 1

                if brace_count != 0:
                    continue

                candidate_text = text[start : index + 1]

                try:
                    candidate = json.loads(candidate_text)
                except json.JSONDecodeError:
                    break

                if _has_valid_intent_shape(candidate):
                    return candidate

                break

    return None


def _has_valid_intent_shape(candidate):
    if not isinstance(candidate, dict):
        return False

    if any(key not in candidate for key in REQUIRED_INTENT_KEYS):
        return False

    if not isinstance(candidate.get("action"), str) or not candidate["action"].strip():
        return False

    if not isinstance(candidate.get("resource"), str):
        return False

    if not isinstance(candidate.get("device"), str):
        return False

    if not isinstance(candidate.get("parameters"), dict):
        return False

    return True


class IntentEngine:
    FALLBACK_MESSAGE = "fallback"
    RULE_CONFIDENCE_EXACT = 1.0
    RULE_CONFIDENCE_FUZZY = 0.7
    RULE_CONFIDENCE_WEAK = 0.4
    CONFIDENCE_KEYWORDS = ("open", "play", "search")

    SYSTEM_PROMPT = """
        You are Shree, an offline AI intent parser.

        STRICT RULES:
        1. Return ONLY valid JSON.
        2. DO NOT explain anything.
        3. DO NOT add text before or after JSON.
        4. DO NOT generate multiple JSON objects.
        5. If unsure, return action "unknown".

        SCHEMA:
        {
          "action": "",
          "resource": "",
          "device": "local",
          "parameters": {}
        }

        VALID ACTIONS:
        - open
        - create_reminder
        - play_music
        - search
        - shutdown_system
        - restart_system
        - lock_screen
        - sleep_system
        - unknown

        EXAMPLES:
        Input: open chrome
        Output: {"action":"open","resource":"chrome","device":"local","parameters":{"name":"chrome"}}

        Input: play hanuman chalisa
        Output: {"action":"play_music","resource":"hanuman chalisa","device":"local","parameters":{"name":"hanuman chalisa"}}

        Input: set reminder tomorrow 9am
        Output: {"action":"create_reminder","resource":"reminder","device":"local","parameters":{"time":"9am","day":"tomorrow"}}
    """.strip()

    SIMPLE_COMMAND_PREFIXES = (
        "open ",
        "play ",
        "create reminder",
        "set reminder",
        "remind ",
        "shutdown",
        "turn off",
    )
    OPEN_KEYWORDS = ("open", "launch", "start", "run")
    OPEN_PREFIXES = (
        "please ",
        "can you ",
        "could you ",
        "would you ",
        "kindly ",
    )

    def parse_local_intent(self, user_input):
        cleaned_input = clean_input(user_input)
        return self._parse_local_intent_exact(cleaned_input)

    def parse_local_intent_with_confidence(self, user_input):
        cleaned_input = clean_input(user_input)
        exact_intent = self._parse_local_intent_exact(cleaned_input)

        if exact_intent:
            return {
                "intent": exact_intent,
                "confidence": self.RULE_CONFIDENCE_EXACT,
                "match_type": "exact",
                "candidate_command": cleaned_input,
            }

        fuzzy_match = self._parse_fuzzy_local_intent(cleaned_input)

        if fuzzy_match:
            LOGGER.debug("Local intent matched fuzzy command: %s", fuzzy_match)
            return fuzzy_match

        weak_match = self._score_weak_local_match(cleaned_input)

        return {
            "intent": None,
            "confidence": weak_match,
            "match_type": "weak" if weak_match else "none",
            "candidate_command": cleaned_input,
        }

    def _parse_local_intent_exact(self, cleaned_input):
        multi_intent = self.parse_multi_intent(cleaned_input)

        if multi_intent:
            LOGGER.debug("Local intent matched multi-intent command: %s", multi_intent)
            return multi_intent

        open_intent = self.parse_open_intent(cleaned_input)

        if open_intent:
            LOGGER.debug("Local intent matched open command: %s", open_intent)
            return open_intent

        play_intent = self.parse_play_intent(cleaned_input)

        if play_intent:
            LOGGER.debug("Local intent matched play command: %s", play_intent)
            return play_intent

        search_intent = self.parse_search_intent(cleaned_input)

        if search_intent:
            LOGGER.debug("Local intent matched search command: %s", search_intent)
            return search_intent

        if not cleaned_input:
            return None

        history_intent = self.parse_history_intent(cleaned_input)

        if history_intent:
            LOGGER.debug("Local intent matched history command: %s", history_intent)
            return history_intent

        explain_intent = self.parse_explain_suggestion_intent(cleaned_input)

        if explain_intent:
            LOGGER.debug("Local intent matched explain suggestion command: %s", explain_intent)
            return explain_intent

        reminder_intent = self.parse_reminder_intent(cleaned_input)

        if reminder_intent:
            LOGGER.debug("Local intent matched reminder command: %s", reminder_intent)
            return reminder_intent

        system_control_intent = self.parse_system_control_intent(cleaned_input)

        if system_control_intent:
            LOGGER.debug("Local intent matched system control command: %s", system_control_intent)
            return system_control_intent

        shutdown_intent = self.parse_shutdown_intent(cleaned_input)

        if shutdown_intent:
            LOGGER.debug("Local intent matched shutdown command: %s", shutdown_intent)
            return shutdown_intent

        return None

    def _parse_fuzzy_local_intent(self, cleaned_input):
        tokens = cleaned_input.split()

        if not tokens:
            return None

        first_token = tokens[0]
        fuzzy_keyword = get_close_matches(
            first_token,
            self.CONFIDENCE_KEYWORDS,
            n=1,
            cutoff=0.6,
        )

        if not fuzzy_keyword or fuzzy_keyword[0] == first_token:
            return None

        candidate_command = " ".join([fuzzy_keyword[0], *tokens[1:]])
        candidate_intent = self._parse_local_intent_exact(candidate_command)

        if not candidate_intent:
            return None

        return {
            "intent": candidate_intent,
            "confidence": self.RULE_CONFIDENCE_FUZZY,
            "match_type": "fuzzy",
            "candidate_command": candidate_command,
        }

    def _score_weak_local_match(self, cleaned_input):
        tokens = cleaned_input.split()

        if not tokens:
            return 0.0

        first_token = tokens[0]
        weak_keyword = get_close_matches(
            first_token,
            self.CONFIDENCE_KEYWORDS,
            n=1,
            cutoff=0.4,
        )

        if weak_keyword:
            return self.RULE_CONFIDENCE_WEAK

        return 0.0

    def detect_intent(self, user_input):
        cleaned_input = clean_input(user_input)
        prompt = f"{self.SYSTEM_PROMPT}\n\nCommand: {cleaned_input}"
        LOGGER.info("LLM system prompt:\n%s", self.SYSTEM_PROMPT)
        LOGGER.info("LLM user command: %s", cleaned_input)

        try:
            response = generate(prompt)
            LOGGER.info("LLM raw response: %s", response)
            json_data = clean_llm_output(response)
            LOGGER.info("LLM cleaned JSON: %s", json_data)
            return json_data
        except Exception as exc:
            LOGGER.warning("LLM intent detection failed: %s", exc)
            return self.build_unknown_action()

    def is_valid_action_schema(self, action_schema):
        return _has_valid_intent_shape(action_schema)

    def clean_text(self, text):
        text = text.lower().strip()
        text = re.sub(r"[^\w\s:/.]", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text

    def parse_multi_intent(self, user_input):
        lowered_input = user_input.lower()

        if " and " not in lowered_input:
            return None

        parts = self.split_multi_intent(user_input)

        if len(parts) < 2:
            return None

        actions = []

        for part in parts:
            action_schema = self.parse_single_local_intent(part)

            if not action_schema:
                return None

            actions.append(action_schema)

        return actions

    def split_multi_intent(self, user_input):
        protected_input = re.sub(
            r"\b(remind me|set reminder|create reminder)\b",
            lambda match: match.group(0).replace(" and ", " __AND__ "),
            user_input,
            flags=re.IGNORECASE,
        )
        parts = [
            part.strip().replace("__AND__", "and")
            for part in re.split(r"\band\b", protected_input, flags=re.IGNORECASE)
            if part.strip()
        ]
        return parts

    def parse_single_local_intent(self, user_input):
        open_intent = self.parse_open_intent(user_input)

        if open_intent:
            return open_intent

        play_intent = self.parse_play_intent(user_input)

        if play_intent:
            return play_intent

        search_intent = self.parse_search_intent(user_input)

        if search_intent:
            return search_intent

        cleaned_input = self.clean_text(user_input)

        if not cleaned_input:
            return None

        history_intent = self.parse_history_intent(cleaned_input)

        if history_intent:
            return history_intent

        explain_intent = self.parse_explain_suggestion_intent(cleaned_input)

        if explain_intent:
            return explain_intent

        reminder_intent = self.parse_reminder_intent(cleaned_input)

        if reminder_intent:
            return reminder_intent

        system_control_intent = self.parse_system_control_intent(cleaned_input)

        if system_control_intent:
            return system_control_intent

        shutdown_intent = self.parse_shutdown_intent(cleaned_input)

        if shutdown_intent:
            return shutdown_intent

        return None

    def parse_open_intent(self, text):
        resource = self.extract_open_resource(text)

        if not resource:
            return None

        return self.build_action("open", resource, {"name": resource})

    def extract_open_resource(self, text):
        normalized_text = text.strip()

        if not normalized_text:
            return None

        lowered_text = normalized_text.lower()

        for prefix in self.OPEN_PREFIXES:
            if lowered_text.startswith(prefix):
                normalized_text = normalized_text[len(prefix):].strip()
                lowered_text = normalized_text.lower()
                break

        for keyword in self.OPEN_KEYWORDS:
            keyword_prefix = f"{keyword} "

            if lowered_text.startswith(keyword_prefix):
                resource = normalized_text[len(keyword_prefix):].strip().strip("\"'")
                resource = self.clean_text(resource).strip()
                return resource or None

        return None

    def parse_play_intent(self, text):
        match = re.match(r"^(?:please\s+)?play\s+(?P<resource>.+)$", text.strip(), re.IGNORECASE)

        if not match:
            return None

        resource = match.group("resource").strip().strip("\"'")
        return self.build_action("play_music", resource, {"name": resource})

    def parse_search_intent(self, text):
        cleaned_text = self.clean_text(text)
        match = re.match(
            r"^(?:please\s+)?search(?:\s+for)?\s+(?P<query>.+)$",
            cleaned_text,
            re.IGNORECASE,
        )

        if not match:
            return None

        query = match.group("query").strip()

        if not query:
            return None

        return self.build_action("search", "web", {"query": query})

    def parse_reminder_intent(self, text):
        simple_reminder = self.parse_simple_reminder_intent(text)

        if simple_reminder:
            return simple_reminder

        reminder_patterns = [
            r"^(?:create|set)\s+reminder\s+(?:for\s+)?(?P<topic>.+?)\s+(?:at|on)\s+(?P<time>[\w: ]+)$",
            r"^(?:create|set)\s+reminder\s+(?:at|on)\s+(?P<time>[\w: ]+)\s+(?:for\s+)?(?P<topic>.+)$",
        ]

        for pattern in reminder_patterns:
            match = re.match(pattern, text, re.IGNORECASE)

            if not match:
                continue

            topic = match.group("topic").strip()
            reminder_time = match.group("time").strip()

            return self.build_action(
                "create_reminder",
                topic,
                {
                    "topic": topic,
                    "time": reminder_time,
                    "day": "today",
                },
            )

        compact_match = re.match(
            r"^(?:create|set)\s+reminder(?:\s+for)?\s+(?:(?P<day>tomorrow|today)\s+)?(?P<time>\d{1,2}(?::\d{2})?\s?(?:am|pm))$",
            text,
            re.IGNORECASE,
        )

        if compact_match:
            reminder_time = compact_match.group("time").replace(" ", "")
            day = (compact_match.group("day") or "today").lower()
            return self.build_action(
                "create_reminder",
                "reminder",
                {
                    "topic": "reminder",
                    "time": reminder_time,
                    "day": day,
                },
            )

        if re.fullmatch(r"(?:create|set)\s+reminder", text, re.IGNORECASE):
            return self.build_action(
                "create_reminder",
                "reminder",
                {
                    "topic": "reminder",
                    "time": "unspecified",
                    "day": "today",
                },
            )

        return None

    def parse_simple_reminder_intent(self, text):
        if "reminder" not in text and "remind" not in text:
            return None

        time_match = re.search(r"\b(?P<time>\d{1,2}(?::\d{2})?\s?(?:am|pm))\b", text, re.IGNORECASE)

        if not time_match:
            return None

        reminder_time = time_match.group("time").replace(" ", "")
        day = "today"

        if "tomorrow" in text:
            day = "tomorrow"

        topic = self.extract_reminder_topic(text, time_match.group("time"))

        return self.build_action(
            "create_reminder",
            "reminder",
            {
                "topic": topic,
                "time": reminder_time,
                "day": day,
            },
        )

    def extract_reminder_topic(self, text, reminder_time):
        topic_match = re.search(
            r"\bfor\s+(?P<topic>.+?)\s+(?:at|on)\s+\d",
            text,
            re.IGNORECASE,
        )

        if topic_match:
            topic = topic_match.group("topic").strip()
            return topic or "reminder"

        cleaned_text = text.replace(reminder_time, "")
        cleaned_text = re.sub(
            r"\b(create|set|remind|reminder|me|at|on|for|tomorrow|today)\b",
            " ",
            cleaned_text,
            flags=re.IGNORECASE,
        )
        cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

        return cleaned_text or "reminder"

    def parse_shutdown_intent(self, text):
        if text in {"shutdown system", "shutdown", "turn off system", "turn off pc"}:
            return self.build_action("shutdown_system", "system", {"confirm": False})

        return None

    def parse_system_control_intent(self, text):
        if text in {"restart computer", "restart system", "restart pc", "reboot system", "reboot computer"}:
            return self.build_action("restart_system", "system", {"confirm": False})

        if text in {"lock screen", "lock computer", "lock pc"}:
            return self.build_action("lock_screen", "screen", {})

        if text in {"sleep system", "sleep computer", "sleep pc"}:
            return self.build_action("sleep_system", "system", {})

        return None

    def parse_history_intent(self, text):
        if text in {
            "what did i do today",
            "show command history",
            "command history",
            "show my last commands",
            "show my last command",
            "show recent commands",
            "show last 5 commands",
            "my last commands",
            "recent commands",
        }:
            return self.build_action(
                "show_history",
                "history",
                {"message": "Command history requested."},
            )

        return None

    def parse_explain_suggestion_intent(self, text):
        patterns = (
            r"^why did you suggest(?: (?P<target>.+))?$",
            r"^why suggest(?: (?P<target>.+))?$",
            r"^explain suggestion$",
            r"^explain your suggestion$",
        )

        for pattern in patterns:
            match = re.match(pattern, text, re.IGNORECASE)

            if not match:
                continue

            target = ""

            if "target" in match.groupdict():
                target = (match.group("target") or "").strip()

            return self.build_action(
                "explain_suggestion",
                target or "suggestion",
                {"target": target},
            )

        return None

    def build_action(self, action, resource, parameters=None):
        return {
            "action": action,
            "resource": resource,
            "device": "local",
            "parameters": parameters or {},
        }

    def build_unknown_action(self, message=None):
        return self.build_action(
            "unknown",
            "",
            {"message": message or self.FALLBACK_MESSAGE},
        )
