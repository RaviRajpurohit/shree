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

    def __init__(self, intent_engine, memory=None):
        self.intent_engine = intent_engine
        self.memory = memory

    def route(self, user_input):
        pattern_intent = self._resolve_pattern_intent(user_input)

        if pattern_intent:
            self.attach_source(pattern_intent, "pattern")
            LOGGER.info("Pattern matched")
            return pattern_intent

        contextual_intent = self._resolve_contextual_intent(user_input)

        if contextual_intent:
            self.attach_source(contextual_intent, "context")
            LOGGER.info("Intent router used memory context for input: %s", user_input)
            return contextual_intent

        local_intent = self.intent_engine.parse_local_intent(user_input)
        local_intent = self._prevent_wrong_routing(local_intent)

        if local_intent:
            self.attach_source(local_intent, "rule")
            LOGGER.info("Intent router selected rule engine for input: %s", user_input)
            return local_intent

        LOGGER.info("Intent router falling back to LLM for input: %s", user_input)
        llm_intent = self.intent_engine.detect_intent(user_input)
        llm_intent = self._prevent_wrong_routing(llm_intent)

        if llm_intent:
            self.attach_source(llm_intent, "llm")
            LOGGER.info("LLM returned action schema: %s", llm_intent)

        return llm_intent

    def _resolve_pattern_intent(self, user_input):
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

    def attach_source(self, action_schema, source):
        if isinstance(action_schema, list):
            for action in action_schema:
                action.setdefault("metadata", {})
                action["metadata"]["source"] = source
            return

        action_schema.setdefault("metadata", {})
        action_schema["metadata"]["source"] = source
