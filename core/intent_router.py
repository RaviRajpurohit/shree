import logging
import re

from core.intent_engine import clean_input


LOGGER = logging.getLogger(__name__)


class IntentRouter:
    BROWSER_NAMES = ("chrome", "edge", "firefox")
    BROWSER_ALIASES = {
        "google chrome": "chrome",
        "microsoft edge": "edge",
        "mozilla firefox": "firefox",
        "chrome browser": "chrome",
        "edge browser": "edge",
        "firefox browser": "firefox",
    }
    RESERVED_OPEN_TERMS = ("tab", "next", "previous")
    CHAIN_SEPARATORS = ("and", "with", "then")
    RULE_ENGINE_KEYWORDS = ("open", "play", "search")
    FILE_OPEN_NOISE_PREFIXES = (
        "hello ",
        "hi ",
        "hey ",
        "please ",
        "can you ",
        "could you ",
        "would you ",
        "kindly ",
        "shree ",
    )

    def __init__(self, intent_engine, memory=None):
        self.intent_engine = intent_engine
        self.memory = memory

    def route(self, user_input):
        chained_intent = self._resolve_chained_intent(user_input)

        if chained_intent:
            LOGGER.info("Intent router resolved chained command: %s", user_input)
            return chained_intent

        return self._route_single_intent(user_input)

    def _route_single_intent(self, user_input):
        pattern_intent = self._resolve_pattern_intent(user_input)

        if pattern_intent:
            self.attach_metadata(pattern_intent, "pattern", 1.0)
            LOGGER.info("Pattern matched")
            return pattern_intent

        contextual_intent = self._resolve_contextual_intent(user_input)

        if contextual_intent:
            self.attach_metadata(contextual_intent, "context", 1.0)
            LOGGER.info("Intent router used memory context for input: %s", user_input)
            return contextual_intent

        rule_result = self.intent_engine.parse_local_intent_with_confidence(user_input)
        local_intent = self._prevent_wrong_routing(rule_result.get("intent"))
        confidence = rule_result.get("confidence", 0.0)

        if local_intent and confidence > 0.8:
            self.attach_metadata(local_intent, "rule", confidence)
            LOGGER.info(
                "Intent router selected rule engine for input: %s with confidence %.2f",
                user_input,
                confidence,
            )
            return local_intent

        if local_intent and confidence > 0.5:
            clarification = self._build_clarification_action(rule_result, confidence)
            self.attach_metadata(clarification, "rule", confidence)
            LOGGER.info(
                "Intent router requesting clarification for input: %s with confidence %.2f",
                user_input,
                confidence,
            )
            return clarification

        LOGGER.info("Intent router falling back to LLM for input: %s", user_input)
        llm_intent = self.intent_engine.detect_intent(user_input)
        llm_intent = self._prevent_wrong_routing(llm_intent)

        if llm_intent:
            self.attach_metadata(llm_intent, "llm", 0.0)
            LOGGER.info("LLM returned action schema: %s", llm_intent)

        return llm_intent

    def _should_force_rule_engine(self, user_input):
        text = clean_input(user_input)

        if not text:
            return False

        tokens = set(text.split())
        return any(keyword in tokens for keyword in self.RULE_ENGINE_KEYWORDS)

    def _resolve_chained_intent(self, user_input):
        parts = self._split_chained_input(user_input)

        if len(parts) < 2:
            return None

        actions = []
        chain_context = {}

        for part in parts:
            action_schema = self._route_single_intent(part)

            if not action_schema or isinstance(action_schema, list):
                return None

            action_schema = self._apply_chain_context(action_schema, chain_context)
            actions.append(action_schema)
            chain_context = self._update_chain_context(chain_context, action_schema)

        self.attach_metadata(actions, "pattern", 1.0)
        return actions

    def _split_chained_input(self, user_input):
        text = clean_input(user_input)

        if not text:
            return []

        separator_pattern = r"\b(?:and|with|then)\b"
        parts = [part.strip() for part in re.split(separator_pattern, text) if part.strip()]

        if len(parts) < 2:
            return []

        return parts

    def _apply_chain_context(self, action_schema, chain_context):
        if action_schema.get("action") == "open":
            browser = self._extract_browser_name(action_schema.get("resource", ""))

            if browser:
                action_schema["resource"] = browser
                action_schema.setdefault("parameters", {})
                action_schema["parameters"]["name"] = browser

        if action_schema.get("action") != "browser_control":
            return action_schema

        parameters = action_schema.setdefault("parameters", {})
        browser = parameters.get("browser")

        if browser and browser != "default":
            return action_schema

        if chain_context.get("browser"):
            parameters["browser"] = chain_context["browser"]

        return action_schema

    def _update_chain_context(self, chain_context, action_schema):
        updated_context = dict(chain_context)

        browser = self._extract_browser_name(action_schema.get("resource", ""))

        if action_schema.get("action") == "open" and browser:
            updated_context["browser"] = browser
        elif action_schema.get("action") == "browser_control":
            browser = action_schema.get("parameters", {}).get("browser")

            if browser and browser != "default":
                updated_context["browser"] = browser

        return updated_context

    def _resolve_pattern_intent(self, user_input):
        file_intent = self._parse_open_file_intent(user_input)

        if file_intent:
            LOGGER.info("File open pattern matched")
            return file_intent

        text = clean_input(user_input)

        if not text:
            return None

        split_actions = self._parse_open_with_browser_control(text)

        if split_actions:
            LOGGER.info("Split command detected")
            return split_actions

        browser_control = self._parse_browser_control(text)

        if browser_control:
            return browser_control

        return None

    def _parse_open_file_intent(self, user_input):
        text = self._normalize_file_command_text(user_input)

        if not text:
            return None

        match = re.match(
            r"^open\s+file(?:\s+called)?\s+(?P<name>.+?)$",
            text,
            re.IGNORECASE,
        )

        if not match:
            return None

        file_name = match.group("name").strip().strip("\"'")

        if not file_name:
            return None

        return self._build_action(
            "open_file",
            file_name,
            {"name": file_name},
        )

    def _parse_open_with_browser_control(self, text):
        match = re.match(
            r"^open\s+(?P<browser>.+?)\s+with\s+(?P<control>.+)$",
            text,
            re.IGNORECASE,
        )

        if not match:
            return None

        browser = self._extract_browser_name(match.group("browser"))
        control_text = match.group("control").strip()

        if not browser or not self._contains_tab_phrase(control_text):
            return None

        return [
            self._build_action("open", browser, {"name": browser}),
            self._build_action(
                "browser_control",
                "new_tab",
                {"browser": browser, "resource": "new_tab"},
            ),
        ]

    def _parse_browser_control(self, text):
        if not self._contains_tab_phrase(text):
            return None

        browser = self._extract_browser_name(text) or self._get_context_browser() or "default"

        return self._build_action(
            "browser_control",
            "new_tab",
            {"browser": browser, "resource": "new_tab"},
        )

    def _resolve_contextual_intent(self, user_input):
        if not self.memory:
            return None

        last_action = self.memory.get_last_action()

        if not last_action:
            return None

        text = clean_input(user_input)

        if text in {"open new tab", "open tab", "new tab"}:
            browser = self._get_context_browser()

            if browser:
                return self._build_action(
                    "browser_control",
                    "new_tab",
                    {"browser": browser, "resource": "new_tab"},
                )

        if text == "play next" and last_action.get("action") == "play_music":
            parameters = dict(last_action.get("parameters", {}))

            if last_action.get("resource"):
                parameters.setdefault("source", last_action["resource"])

            return self._build_action("play_music", "next", parameters)

        if text == "play previous" and last_action.get("action") == "play_music":
            parameters = dict(last_action.get("parameters", {}))

            if last_action.get("resource"):
                parameters.setdefault("source", last_action["resource"])

            return self._build_action("play_music", "previous", parameters)

        return None

    def _get_context_browser(self):
        if not self.memory:
            return None

        last_action = self.memory.get_last_action()

        if not last_action or last_action.get("action") != "open":
            return None

        return self._extract_browser_name(last_action.get("resource", ""))

    def _prevent_wrong_routing(self, action_schema):
        if not action_schema:
            return action_schema

        if isinstance(action_schema, list):
            sanitized_actions = [self._prevent_wrong_routing(action) for action in action_schema]
            return [action for action in sanitized_actions if action]

        if action_schema.get("action") != "open":
            return action_schema

        resource = clean_input(action_schema.get("resource", ""))

        if any(term in resource.split() for term in self.RESERVED_OPEN_TERMS):
            if "tab" in resource.split():
                browser = self._extract_browser_name(resource) or self._get_context_browser() or "default"
                LOGGER.info("Pattern matched")
                return self._build_action(
                    "browser_control",
                    "new_tab",
                    {"browser": browser, "resource": "new_tab"},
                )

            return self._build_action("unknown", "", {"message": "Unsupported open target."})

        return action_schema

    def _extract_browser_name(self, text):
        normalized_text = clean_input(text)

        for alias, canonical_name in self.BROWSER_ALIASES.items():
            if alias in normalized_text:
                return canonical_name

        for browser_name in self.BROWSER_NAMES:
            if re.search(rf"\b{re.escape(browser_name)}\b", normalized_text):
                return browser_name

        return None

    @staticmethod
    def _contains_tab_phrase(text):
        normalized_text = clean_input(text)

        return bool(
            re.search(r"\bnew tab\b", normalized_text)
            or re.search(r"\bopen tab\b", normalized_text)
            or re.search(r"\btab\b", normalized_text)
        )

    @staticmethod
    def _build_action(action, resource, parameters=None):
        return {
            "action": action,
            "resource": resource,
            "device": "local",
            "parameters": parameters or {},
        }

    def _normalize_file_command_text(self, user_input):
        text = " ".join(str(user_input or "").strip().split())

        if not text:
            return ""

        lowered_text = text.lower()

        for prefix in self.FILE_OPEN_NOISE_PREFIXES:
            if lowered_text.startswith(prefix):
                text = text[len(prefix):].strip()
                lowered_text = text.lower()

        return text

    def _build_clarification_action(self, rule_result, confidence):
        candidate_command = (rule_result.get("candidate_command") or "").strip()

        if candidate_command:
            message = f"Did you mean '{candidate_command}'?"
        else:
            message = "I found a partial match. Could you clarify the command?"

        return self._build_action(
            "unknown",
            "",
            {
                "message": message,
                "clarification_needed": True,
                "candidate_command": candidate_command,
                "confidence": confidence,
            },
        )

    def attach_metadata(self, action_schema, source, confidence):
        if isinstance(action_schema, list):
            for action in action_schema:
                action.setdefault("metadata", {})
                action["metadata"]["source"] = source
                action["metadata"]["confidence"] = confidence
            return

        action_schema.setdefault("metadata", {})
        action_schema["metadata"]["source"] = source
        action_schema["metadata"]["confidence"] = confidence
