import copy
import re


APP_ALIASES = {
    "google chrome": "chrome",
    "chrome browser": "chrome",
    "microsoft edge": "edge",
    "edge browser": "edge",
    "mozilla firefox": "firefox",
    "firefox browser": "firefox",
    "browser": "chrome",
    "calc": "calculator",
    "text editor": "notepad",
    "command prompt": "cmd",
    "terminal": "cmd",
    "windows terminal": "cmd",
    "file explorer": "explorer",
    "visual studio code": "code",
    "vs code": "code",
}

BROWSER_ALIASES = {
    "google chrome": "chrome",
    "chrome browser": "chrome",
    "microsoft edge": "edge",
    "edge browser": "edge",
    "mozilla firefox": "firefox",
    "firefox browser": "firefox",
}

BROWSER_ACTION_ALIASES = {
    "tab": "new_tab",
    "new_tab": "new_tab",
    "new tab": "new_tab",
    "next": "next_tab",
    "next_tab": "next_tab",
    "next tab": "next_tab",
    "previous": "previous_tab",
    "previous_tab": "previous_tab",
    "previous tab": "previous_tab",
    "prev": "previous_tab",
    "prev tab": "previous_tab",
}


def normalize(intent):
    if isinstance(intent, list):
        return [normalized for item in intent if (normalized := normalize(item))]

    if not isinstance(intent, dict):
        return intent

    normalized = copy.deepcopy(intent)
    normalized["action"] = _normalize_token(normalized.get("action"))
    normalized["resource"] = _normalize_resource(normalized.get("resource"))
    normalized["device"] = normalized.get("device") or "local"
    normalized["parameters"] = dict(normalized.get("parameters") or {})

    if normalized["action"] == "open":
        return _normalize_open_intent(normalized)

    if normalized["action"] == "browser_control":
        return _normalize_browser_control_intent(normalized)

    return _fill_missing_parameters(normalized)


def _normalize_open_intent(intent):
    parameters = intent["parameters"]

    resource = intent["resource"] or _normalize_resource(parameters.get("name"))
    browser_control = _extract_browser_control(resource)

    if browser_control:
        action, browser = browser_control
        intent["action"] = "browser_control"
        intent["resource"] = action
        parameters.pop("name", None)
        parameters["resource"] = action
        parameters["browser"] = browser or _normalize_browser_name(parameters.get("browser")) or "default"
        return intent

    canonical_resource = _normalize_app_name(resource)

    if canonical_resource:
        intent["resource"] = canonical_resource
        parameters["name"] = canonical_resource

    return _fill_missing_parameters(intent)


def _normalize_browser_control_intent(intent):
    parameters = intent["parameters"]
    resource_candidates = [
        intent["resource"],
        _normalize_resource(parameters.get("resource")),
        _normalize_resource(parameters.get("name")),
    ]

    action = None
    browser = _normalize_browser_name(parameters.get("browser"))

    for candidate in resource_candidates:
        if not candidate:
            continue

        browser_control = _extract_browser_control(candidate)

        if browser_control:
            action, extracted_browser = browser_control
            browser = browser or extracted_browser
            break

        normalized_action = _normalize_browser_action(candidate)

        if normalized_action:
            action = normalized_action
            break

    intent["resource"] = action or "new_tab"
    parameters["resource"] = intent["resource"]
    parameters["browser"] = browser or "default"

    return intent


def _fill_missing_parameters(intent):
    parameters = intent["parameters"]
    action = intent.get("action")
    resource = intent.get("resource")

    if action == "open" and resource and not parameters.get("name"):
        parameters["name"] = resource

    if action == "open_file" and resource and not parameters.get("name"):
        parameters["name"] = resource

    if action == "browser_control":
        normalized_action = _normalize_browser_action(resource) or "new_tab"
        intent["resource"] = normalized_action
        parameters["resource"] = normalized_action
        parameters["browser"] = _normalize_browser_name(parameters.get("browser")) or "default"

    return intent


def _extract_browser_control(text):
    normalized_text = _normalize_resource(text)

    if not normalized_text:
        return None

    browser = _normalize_browser_name(normalized_text)
    action = None

    if re.search(r"\bnew tab\b", normalized_text) or re.search(r"\btab\b", normalized_text):
        action = "new_tab"
    elif re.search(r"\bnext(?: tab)?\b", normalized_text):
        action = "next_tab"
    elif re.search(r"\b(?:previous|prev)(?: tab)?\b", normalized_text):
        action = "previous_tab"

    if not action:
        return None

    return action, browser


def _normalize_browser_action(value):
    normalized_value = _normalize_resource(value)

    if not normalized_value:
        return None

    return BROWSER_ACTION_ALIASES.get(normalized_value)


def _normalize_browser_name(value):
    normalized_value = _normalize_resource(value)

    if not normalized_value:
        return None

    for alias, canonical_name in BROWSER_ALIASES.items():
        if alias in normalized_value:
            return canonical_name

    for browser_name in ("chrome", "edge", "firefox", "default"):
        if re.search(rf"\b{re.escape(browser_name)}\b", normalized_value):
            return browser_name

    return None


def _normalize_app_name(value):
    normalized_value = _normalize_resource(value)

    if not normalized_value:
        return ""

    return APP_ALIASES.get(normalized_value, normalized_value)


def _normalize_resource(value):
    if value is None:
        return ""

    return " ".join(str(value).strip().lower().split())


def _normalize_token(value):
    normalized_value = _normalize_resource(value)

    if not normalized_value:
        return ""

    normalized_value = re.sub(r"(?<!^)(?=[A-Z])", "_", str(value)).lower()
    return normalized_value.replace(" ", "_")
