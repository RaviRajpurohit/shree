from collections import Counter
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys


ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agent_loop import AgentLoop
from plugins.open_app import OpenAppPlugin
from plugins.base_plugin import BasePlugin
from plugins.play_music import PlayMusicPlugin
from plugins.search_web import SearchWebPlugin


TEST_CATEGORIES = [
    (
        "Basic Commands",
        [
            "open chrome",
            "open calculator",
            "open notepad",
            "open cmd",
            "open command prompt",
            "open terminal",
            "open file explorer",
        ],
    ),
    (
        "Variation Tests",
        [
            "open chrome browser",
            "please open chrome",
            "can you open chrome",
            "launch chrome",
            "start chrome",
        ],
    ),
    (
        "Edge Cases",
        [
            "open chrom",
            "open calculater",
            "open notpad",
            "play musc",
        ],
    ),
    (
        "Music Commands",
        [
            "play music",
            "play song",
            "play shree ram",
            "play hanuman chalisa",
            "play something relaxing",
            "play hanuman chalisa on youtube",
            "play devotional songs on spotify",
        ],
    ),
    (
        "Reminder Commands",
        [
            "create reminder at 9am",
            "set reminder for tomorrow 10am",
            "remind me at 7pm",
            "create reminder for meeting at 5pm",
        ],
    ),
    (
        "Search Commands",
        [
            "search python tutorial",
            "please search for ai tutorial",
        ],
    ),
    (
        "System Commands",
        [
            "shutdown system",
            "restart computer",
            "lock screen",
        ],
    ),
    (
        "Unknown Commands",
        [
            "who are you",
            "what is the time",
            "what is the date",
            "what is python",
            "tell me a joke",
        ],
    ),
    (
        "Mixed Commands",
        [
            "open chrome and play music",
            "open calculator and set reminder",
            "open chrome and search ai tutorial",
        ],
    ),
    (
        "Context Commands",
        [
            "open chrome",
            "open new tab",
            "play bhajan",
            "play next",
        ],
    ),
    (
        "History And Explainability",
        [
            "show my last commands",
            "why did you suggest chrome",
            "explain suggestion",
        ],
    ),
    (
        "Negative Tests",
        [
            "open nothing",
            "play nothing",
            "remind nothing",
        ],
    ),
]

SUGGESTION_SEQUENCE = ["open cmd", "open cmd", "open cmd", "hello"]


class SnapshotOpenAppPlugin(OpenAppPlugin):

    def execute(self, parameters):
        app_name = parameters.get("name")

        if not app_name:
            return "Application name not provided."

        launch_target = self.normalize_app_name(app_name)
        resolved_target = self.resolve_launch_target(launch_target)
        can_launch = self.can_launch_without_opening(resolved_target)

        if can_launch:
            return f"{app_name} opened [snapshot mode -> {resolved_target}]"

        return f"I tried to open {app_name}, but Windows could not find a matching application."

    def can_launch_without_opening(self, target):
        if not target:
            return False

        if Path(target).exists():
            return True

        return shutil.which(target) is not None


class SnapshotSearchWebPlugin(SearchWebPlugin):

    def execute(self, parameters):
        query = (parameters.get("query") or "").strip()

        if not query:
            return "Search query not provided."

        return f"Searching for {query} [snapshot mode]"


class SnapshotPlayMusicPlugin(PlayMusicPlugin):

    def send_media_key(self, command):
        return True

    def resolve_local_media(self, query):
        return None

    def execute(self, parameters):
        parameters = parameters or {}
        name = (parameters.get("name") or "").strip()
        source = (parameters.get("source") or "").strip()
        resource = (parameters.get("resource") or "").strip().lower()

        control_command = self.resolve_control_command(name or resource)

        if control_command:
            return f"{self.build_control_response(control_command)} [snapshot mode]"

        query = name or source

        if not query:
            return "Please specify which song or music to play"

        platform = self.detect_platform(query)
        cleaned_query = self.clean_query(query)

        if platform == "spotify":
            return f"Opening Spotify results for {cleaned_query} [snapshot mode]"

        return f"Playing music: {cleaned_query} [snapshot mode]"


class SnapshotBrowserControlPlugin(BasePlugin):

    action = "browser_control"

    def execute(self, parameters):
        browser = (parameters.get("browser") or "browser").strip()
        return f"Opened a new tab in {browser} [snapshot mode]"


def patch_llm_fallback(agent):
    def instant_detect_intent(_user_input):
        return {
            "action": "unknown",
            "resource": "",
            "device": "local",
            "parameters": {"message": "LLM unavailable."},
        }

    agent.intent_engine.detect_intent = instant_detect_intent


def run_test_case(agent, command):
    suggestion_before = agent.get_suggestion()
    action_schema = agent.intent_router.route(command)
    response = agent.process(command)
    suggestion_after = agent.get_suggestion()

    return {
        "command": command,
        "source": get_result_source(action_schema),
        "action": get_result_action(action_schema),
        "resource": get_result_resource(action_schema),
        "response": response,
        "suggestion_before": suggestion_before,
        "suggestion_after": suggestion_after,
    }


def get_result_source(action_schema):
    if not action_schema:
        return "none"

    if isinstance(action_schema, list):
        return ",".join(
            action.get("metadata", {}).get("source", "unknown")
            for action in action_schema
        )

    return action_schema.get("metadata", {}).get("source", "unknown")


def get_result_action(action_schema):
    if not action_schema:
        return None

    if isinstance(action_schema, list):
        return ", ".join(action.get("action", "") for action in action_schema)

    return action_schema.get("action")


def get_result_resource(action_schema):
    if not action_schema:
        return None

    if isinstance(action_schema, list):
        return ", ".join(action.get("resource", "") for action in action_schema)

    return action_schema.get("resource")


def classify_result(result):
    response = result["response"].lower()

    if (
        "opened" in response
        or "playing music" in response
        or "opening spotify results" in response
        or "skipping to the next track" in response
        or "going back to the previous track" in response
        or "pausing playback" in response
        or "resuming playback" in response
        or "stopping playback" in response
        or "reminder created" in response
        or "searching for" in response
        or "offline ai assistant" in response
        or "recent commands:" in response
        or "because you " in response
    ):
        return "success"

    if re.fullmatch(r"\d{2}:\d{2}", response) or re.fullmatch(r"\d{2} \w+ \d{4}", response):
        return "success"

    if "shutdown requested" in response:
        return "expected-safe-block"

    if "llm unavailable" in response:
        return "llm-unavailable"

    if "i don't know how to perform that action" in response:
        return "unsupported-action"

    if "could not find a matching application" in response:
        return "mapping-or-discovery-failure"

    if "sorry, i couldn't understand" in response:
        return "parse-failure"

    return "other"


def build_report(results, suggestion_results, report_path):
    status_counter = Counter(classify_result(result) for result in results)

    lines = [
        "# Shree Prompt Test Report",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Total commands tested: {len(results)}",
        "",
        "## Summary",
        "",
    ]

    for status, count in sorted(status_counter.items()):
        lines.append(f"- {status}: {count}")

    lines.extend(
        [
            "",
            "## Command Snapshots",
            "",
        ]
    )

    for result in results:
        lines.extend(
            [
                f"### {result['command']}",
                "",
                f"- Source: {result['source']}",
                f"- Action: {result['action']}",
                f"- Resource: {result['resource']}",
                f"- Suggestion before: {result['suggestion_before'] or 'None'}",
                f"- Response: {result['response']}",
                f"- Suggestion after: {result['suggestion_after'] or 'None'}",
                f"- Classification: {classify_result(result)}",
                "",
                "```text",
                f"You: {result['command']}",
                f"Shree: {result['response']}",
                "```",
                "",
            ]
        )

    lines.extend(
        [
            "## Suggestion Sequence Snapshot",
            "",
        ]
    )

    for result in suggestion_results:
        lines.extend(
            [
                f"### {result['command']}",
                "",
                f"- Suggestion before: {result['suggestion_before'] or 'None'}",
                f"- Response: {result['response']}",
                f"- Suggestion after: {result['suggestion_after'] or 'None'}",
                "",
                "```text",
                f"You: {result['command']}",
                f"Shree: {result['response']}",
                "```",
                "",
            ]
        )

    report_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)

    agent = AgentLoop()
    agent.plugin_manager.plugins["open"] = SnapshotOpenAppPlugin()
    agent.plugin_manager.plugins["search"] = SnapshotSearchWebPlugin()
    agent.plugin_manager.plugins["play_music"] = SnapshotPlayMusicPlugin()
    agent.plugin_manager.plugins["browser_control"] = SnapshotBrowserControlPlugin()
    patch_llm_fallback(agent)

    results = []

    for category_name, commands in TEST_CATEGORIES:
        for command in commands:
            result = run_test_case(agent, command)
            result["category"] = category_name
            results.append(result)

    suggestion_agent = AgentLoop()
    suggestion_agent.plugin_manager.plugins["open"] = SnapshotOpenAppPlugin()
    suggestion_agent.plugin_manager.plugins["search"] = SnapshotSearchWebPlugin()
    suggestion_agent.plugin_manager.plugins["play_music"] = SnapshotPlayMusicPlugin()
    suggestion_agent.plugin_manager.plugins["browser_control"] = SnapshotBrowserControlPlugin()
    patch_llm_fallback(suggestion_agent)
    suggestion_results = [run_test_case(suggestion_agent, command) for command in SUGGESTION_SEQUENCE]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = reports_dir / f"shree_prompt_test_report_{timestamp}.md"
    build_report(results, suggestion_results, report_path)

    print(report_path)


if __name__ == "__main__":
    main()
