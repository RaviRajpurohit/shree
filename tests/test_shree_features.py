import sys
import unittest
import json
from pathlib import Path
import shutil
import uuid
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agent_loop import AgentLoop
from core.executor import Executor
from core.intent_engine import clean_llm_output
from core.intent_engine import clean_input
from core.memory import Memory
from core.memory_manager import MemoryManager
from core.normalizer import normalize
from core.offline_knowledge_engine import OfflineKnowledgeEngine
from core.intent_router import IntentRouter
from core.suggestion_engine import SuggestionEngine
from plugins.base_plugin import BasePlugin
from plugins.browser_control import BrowserControlPlugin
from plugins.open_file import OpenFilePlugin
from plugins.play_music import PlayMusicPlugin
from plugins.plugin_manager import PluginManager
from plugins.run_command import RunCommandPlugin
from plugins.system_control import SystemControlPlugin


class DummyOpenPlugin(BasePlugin):
    action = "open"
    required_parameters = {
        "name": "Please specify which application to open",
    }

    def execute(self, parameters):
        return f"{parameters['name']} opened [test]"


class DummyPlayMusicPlugin(BasePlugin):
    action = "play_music"

    def execute(self, parameters):
        if parameters.get("resource") == "next":
            return "Skipping to the next track."

        name = parameters.get("name") or parameters.get("source")
        return f"Playing music: {name} [test]"


class DummyBrowserControlPlugin(BasePlugin):
    action = "browser_control"

    def execute(self, parameters):
        return f"Opened a new tab in {parameters.get('browser', 'default')} [test]"


class DummyOpenFilePlugin(BasePlugin):
    action = "open_file"

    def execute(self, parameters):
        return f"Opened file: {parameters['name']} [test]"


class DummyRunCommandPlugin(BasePlugin):
    action = "run_command"

    def execute(self, parameters):
        return f"Command executed successfully: {parameters['command']} [test]"


class FailingRunCommandPlugin(BasePlugin):
    action = "run_command"

    def execute(self, parameters):
        return f"Failed to execute '{parameters['command']}' command"


class CrashingRunCommandPlugin(BasePlugin):
    action = "run_command"

    def execute(self, parameters):
        raise RuntimeError("boom")


class ShreeFeatureTests(unittest.TestCase):
    def test_offline_knowledge_engine_handles_identity_query(self):
        engine = OfflineKnowledgeEngine()

        self.assertEqual(
            engine.respond("who are you"),
            "I am Shree, your offline AI assistant.",
        )

    def test_offline_knowledge_engine_handles_greeting(self):
        engine = OfflineKnowledgeEngine()

        self.assertEqual(
            engine.respond("hello"),
            "Hello! I am Shree. How can I help you offline today?",
        )

    def test_offline_knowledge_engine_handles_help_query(self):
        engine = OfflineKnowledgeEngine()

        response = engine.respond("basic help")

        self.assertIn("opening apps", response)
        self.assertIn("reminders", response)

    def test_clean_input_normalizes_command(self):
        self.assertEqual(
            clean_input("Can you please open chrome?"),
            "open chrome",
        )

    def test_clean_input_ignores_greeting_noise_for_rule_commands(self):
        self.assertEqual(
            clean_input("hello please open chrome"),
            "open chrome",
        )

    def test_clean_llm_output_extracts_first_valid_json_from_markdown(self):
        output = clean_llm_output(
            """Here is the result:
```json
{"action":"open","resource":"chrome","device":"local","parameters":{"name":"chrome"}}
```
"""
        )

        self.assertEqual(output["action"], "open")
        self.assertEqual(output["resource"], "chrome")
        self.assertEqual(output["device"], "local")
        self.assertEqual(output["parameters"]["name"], "chrome")

    def test_clean_llm_output_ignores_extra_json_after_first_valid_object(self):
        output = clean_llm_output(
            '{"action":"search","resource":"web","device":"local","parameters":{"query":"python"}} '
            '{"action":"open","resource":"chrome","device":"local","parameters":{"name":"chrome"}}'
        )

        self.assertEqual(output["action"], "search")
        self.assertEqual(output["parameters"]["query"], "python")

    def test_clean_llm_output_returns_unknown_for_invalid_schema(self):
        output = clean_llm_output('```json {"action":"open"} ```')

        self.assertEqual(
            output,
            {"action": "unknown", "resource": "", "device": "local", "parameters": {}},
        )

    def test_memory_returns_suggestion_and_explanation(self):
        memory = Memory()

        for _ in range(5):
            memory.remember(
                "open chrome",
                {
                    "action": "open",
                    "resource": "chrome",
                    "parameters": {"name": "chrome"},
                },
            )

        self.assertEqual(
            memory.get_suggestion(),
            "You usually open chrome. Want me to?",
        )
        self.assertEqual(
            memory.explain_suggestion("why did you suggest chrome"),
            "Because you opened chrome 5 times recently",
        )

    def test_memory_manager_records_action_and_updates_count(self):
        memory_path = ROOT / ".codex_tmp" / f"memory_manager_{uuid.uuid4().hex}.json"
        self.addCleanup(memory_path.unlink, True)
        manager = MemoryManager(memory_path)

        manager.record_action("open", "chrome")
        manager.record_action("open", "chrome")

        records = manager.get_top_actions()

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["action"], "open")
        self.assertEqual(records[0]["resource"], "chrome")
        self.assertEqual(records[0]["count"], 2)
        self.assertTrue(records[0]["last_used"])

        persisted = json.loads(memory_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted[0]["count"], 2)

    def test_memory_manager_returns_last_actions(self):
        memory_path = ROOT / ".codex_tmp" / f"memory_manager_{uuid.uuid4().hex}.json"
        self.addCleanup(memory_path.unlink, True)
        manager = MemoryManager(memory_path)

        manager.record_action("open", "chrome")
        manager.record_action("play_music", "bhajan")

        last_actions = manager.get_last_actions(1)

        self.assertEqual(len(last_actions), 1)
        self.assertEqual(last_actions[0]["action"], "play_music")

    def test_memory_tracks_last_five_commands_and_last_app(self):
        memory = Memory()

        commands = [
            ("open chrome", {"action": "open", "resource": "chrome", "parameters": {"name": "chrome"}}),
            ("open notepad", {"action": "open", "resource": "notepad", "parameters": {"name": "notepad"}}),
            ("open calc", {"action": "open", "resource": "calculator", "parameters": {"name": "calculator"}}),
            ("new tab", {"action": "browser_control", "resource": "new_tab", "parameters": {"browser": "chrome"}}),
            ("open paint", {"action": "open", "resource": "paint", "parameters": {"name": "paint"}}),
            ("open edge", {"action": "open", "resource": "edge", "parameters": {"name": "edge"}}),
        ]

        for command, intent in commands:
            memory.remember(command, intent)

        self.assertEqual(
            memory.last_5_commands,
            ["open notepad", "open calc", "new tab", "open paint", "open edge"],
        )
        self.assertEqual(memory.last_app, "edge")

    def test_memory_returns_most_used_apps(self):
        memory = Memory()

        memory.remember("open chrome", {"action": "open", "resource": "chrome", "parameters": {"name": "chrome"}})
        memory.remember("new tab", {"action": "browser_control", "resource": "new_tab", "parameters": {"browser": "chrome"}})
        memory.remember("open edge", {"action": "open", "resource": "edge", "parameters": {"name": "edge"}})
        memory.remember("open chrome", {"action": "open", "resource": "chrome", "parameters": {"name": "chrome"}})

        self.assertEqual(
            memory.get_most_used_apps(),
            [("chrome", 3), ("edge", 1)],
        )

    def test_suggestion_engine_uses_memory_manager_for_frequent_action(self):
        memory = Memory()
        memory_path = ROOT / ".codex_tmp" / f"suggestion_memory_{uuid.uuid4().hex}.json"
        self.addCleanup(memory_path.unlink, True)
        memory_manager = MemoryManager(memory_path)
        suggestion_engine = SuggestionEngine(memory, memory_manager)

        for _ in range(3):
            memory.remember(
                "open chrome",
                {
                    "action": "open",
                    "resource": "chrome",
                    "parameters": {"name": "chrome"},
                },
            )
            memory_manager.record_action("open", "chrome")

        self.assertEqual(
            suggestion_engine.get_suggestion(),
            "You usually open chrome. Want me to?",
        )

    def test_suggestion_engine_suggests_repeated_sequence(self):
        memory = Memory()
        memory_path = ROOT / ".codex_tmp" / f"suggestion_memory_{uuid.uuid4().hex}.json"
        self.addCleanup(memory_path.unlink, True)
        memory_manager = MemoryManager(memory_path)
        suggestion_engine = SuggestionEngine(memory, memory_manager)

        sequence = [
            ("open chrome", {"action": "open", "resource": "chrome", "parameters": {"name": "chrome"}}),
            ("open new tab", {"action": "browser_control", "resource": "new_tab", "parameters": {"browser": "chrome", "resource": "new_tab"}}),
            ("search python", {"action": "search", "resource": "web", "parameters": {"query": "python"}}),
        ]

        for _ in range(2):
            for command, intent in sequence:
                memory.remember(command, intent)

        self.assertEqual(
            suggestion_engine.get_suggestion(),
            "You often open chrome then open new tab then search python. Want me to do that?",
        )

    def test_normalizer_converts_open_new_tab_in_chrome(self):
        action_schema = normalize(
            {
                "action": "open",
                "resource": "new tab in chrome",
                "parameters": {},
            }
        )

        self.assertEqual(action_schema["action"], "browser_control")
        self.assertEqual(action_schema["resource"], "new_tab")
        self.assertEqual(action_schema["parameters"]["browser"], "chrome")
        self.assertEqual(action_schema["parameters"]["resource"], "new_tab")

    def test_normalizer_fills_missing_open_name_and_alias(self):
        action_schema = normalize(
            {
                "action": "open",
                "resource": "google chrome",
                "parameters": {},
            }
        )

        self.assertEqual(action_schema["resource"], "chrome")
        self.assertEqual(action_schema["parameters"]["name"], "chrome")

    def test_normalizer_standardizes_next_tab_browser_action(self):
        action_schema = normalize(
            {
                "action": "browser control",
                "resource": "next in microsoft edge",
                "parameters": {},
            }
        )

        self.assertEqual(action_schema["action"], "browser_control")
        self.assertEqual(action_schema["resource"], "next_tab")
        self.assertEqual(action_schema["parameters"]["browser"], "edge")
        self.assertEqual(action_schema["parameters"]["resource"], "next_tab")

    def test_normalizer_fills_missing_open_file_name(self):
        action_schema = normalize(
            {
                "action": "open_file",
                "resource": "report.pdf",
                "parameters": {},
            }
        )

        self.assertEqual(action_schema["parameters"]["name"], "report.pdf")

    def test_router_uses_last_action_for_open_new_tab(self):
        memory = Memory()
        memory.update_last_action(
            {
                "action": "open",
                "resource": "chrome",
                "parameters": {"name": "chrome"},
            }
        )

        router = IntentRouter(intent_engine=None, memory=memory)
        action_schema = router.route("open new tab")

        self.assertEqual(action_schema["action"], "browser_control")
        self.assertEqual(action_schema["resource"], "new_tab")
        self.assertEqual(action_schema["parameters"]["browser"], "chrome")
        self.assertEqual(action_schema["metadata"]["source"], "pattern")

    def test_router_prioritizes_pattern_for_open_new_tab_in_chrome(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("open new tab in chrome")

        self.assertEqual(action_schema["action"], "browser_control")
        self.assertEqual(action_schema["resource"], "new_tab")
        self.assertEqual(action_schema["parameters"]["browser"], "chrome")
        self.assertEqual(action_schema["metadata"]["source"], "pattern")

    def test_router_forces_rule_engine_for_keyword_commands(self):
        agent = AgentLoop()

        with patch.object(agent.intent_engine, "detect_intent") as mock_detect:
            action_schema = agent.intent_router.route("hello please open chrome")

        mock_detect.assert_not_called()
        self.assertEqual(action_schema["action"], "open")
        self.assertEqual(action_schema["resource"], "chrome")
        self.assertEqual(action_schema["metadata"]["source"], "rule")
        self.assertEqual(action_schema["metadata"]["confidence"], 1.0)

    def test_agent_loop_handles_basic_query_before_router_or_llm(self):
        agent = AgentLoop()

        with patch.object(agent.intent_router, "route") as mock_route:
            response = agent.process("what is time")

        mock_route.assert_not_called()
        self.assertRegex(response, r"^\d{2}:\d{2}$")

    def test_agent_loop_handles_help_without_llm_fallback(self):
        agent = AgentLoop()

        with patch.object(agent.intent_engine, "detect_intent") as mock_detect:
            response = agent.process("basic help")

        mock_detect.assert_not_called()
        self.assertIn("opening apps", response)

    def test_intent_engine_scores_fuzzy_rule_match(self):
        engine = AgentLoop().intent_engine

        result = engine.parse_local_intent_with_confidence("opne chrome")

        self.assertEqual(result["confidence"], 0.7)
        self.assertEqual(result["candidate_command"], "open chrome")
        self.assertEqual(result["intent"]["action"], "open")

    def test_router_requests_clarification_for_fuzzy_rule_match(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("opne chrome")

        self.assertEqual(action_schema["action"], "unknown")
        self.assertIn("did you mean 'open chrome'?", action_schema["parameters"]["message"].lower())
        self.assertEqual(action_schema["metadata"]["source"], "rule")
        self.assertEqual(action_schema["metadata"]["confidence"], 0.7)

    def test_router_falls_back_to_llm_for_weak_match(self):
        agent = AgentLoop()

        with patch.object(
            agent.intent_engine,
            "parse_local_intent_with_confidence",
            return_value={
                "intent": None,
                "confidence": 0.4,
                "match_type": "weak",
                "candidate_command": "",
            },
        ):
            with patch.object(
                agent.intent_engine,
                "detect_intent",
                return_value={
                    "action": "search",
                    "resource": "web",
                    "device": "local",
                    "parameters": {"query": "python"},
                },
            ) as mock_detect:
                action_schema = agent.intent_router.route("maybe search python")

        mock_detect.assert_called_once()
        self.assertEqual(action_schema["action"], "search")
        self.assertEqual(action_schema["metadata"]["source"], "llm")
        self.assertEqual(action_schema["metadata"]["confidence"], 0.0)

    def test_router_maps_open_file_called_report_pdf(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("open file called report.pdf")

        self.assertEqual(action_schema["action"], "open_file")
        self.assertEqual(action_schema["resource"], "report.pdf")
        self.assertEqual(action_schema["parameters"]["name"], "report.pdf")
        self.assertEqual(action_schema["metadata"]["source"], "pattern")

    def test_local_intent_maps_restart_computer(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("restart computer")

        self.assertEqual(action_schema["action"], "restart_system")
        self.assertEqual(action_schema["resource"], "system")
        self.assertEqual(action_schema["parameters"]["confirm"], False)
        self.assertEqual(action_schema["metadata"]["source"], "rule")

    def test_local_intent_maps_lock_screen(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("lock screen")

        self.assertEqual(action_schema["action"], "lock_screen")
        self.assertEqual(action_schema["resource"], "screen")
        self.assertEqual(action_schema["metadata"]["source"], "rule")

    def test_local_intent_maps_sleep_system(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("sleep system")

        self.assertEqual(action_schema["action"], "sleep_system")
        self.assertEqual(action_schema["resource"], "system")
        self.assertEqual(action_schema["metadata"]["source"], "rule")

    def test_local_intent_maps_clear_to_run_command(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("clear")

        self.assertEqual(action_schema["action"], "run_command")
        self.assertEqual(action_schema["resource"], "terminal")
        self.assertEqual(action_schema["parameters"]["command"], "clear")
        self.assertEqual(action_schema["metadata"]["source"], "rule")

    def test_local_intent_maps_explicit_run_command(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("run command clear")

        self.assertEqual(action_schema["action"], "run_command")
        self.assertEqual(action_schema["parameters"]["command"], "clear")

    def test_local_intent_maps_run_clear_command_without_open_fallback(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("run clear command")

        self.assertEqual(action_schema["action"], "run_command")
        self.assertEqual(action_schema["parameters"]["command"], "clear")
        self.assertNotEqual(action_schema["action"], "open")

    def test_local_intent_maps_execute_dir_to_run_command(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("execute dir")

        self.assertEqual(action_schema["action"], "run_command")
        self.assertEqual(action_schema["parameters"]["command"], "dir")

    def test_local_intent_maps_type_cls_to_run_command(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("type cls")

        self.assertEqual(action_schema["action"], "run_command")
        self.assertEqual(action_schema["parameters"]["command"], "cls")

    def test_router_maps_open_tab_in_chrome(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("open tab in chrome")

        self.assertEqual(action_schema["action"], "browser_control")
        self.assertEqual(action_schema["resource"], "new_tab")
        self.assertEqual(action_schema["parameters"]["browser"], "chrome")

    def test_router_maps_new_tab_in_edge(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("new tab in edge")

        self.assertEqual(action_schema["action"], "browser_control")
        self.assertEqual(action_schema["resource"], "new_tab")
        self.assertEqual(action_schema["parameters"]["browser"], "edge")

    def test_router_uses_default_browser_when_none_available(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("open tab")

        self.assertEqual(action_schema["action"], "browser_control")
        self.assertEqual(action_schema["parameters"]["browser"], "default")

    def test_router_splits_open_browser_with_new_tab_into_two_actions(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("open chrome with new tab")

        self.assertIsInstance(action_schema, list)
        self.assertEqual(len(action_schema), 2)
        self.assertEqual(action_schema[0]["action"], "open")
        self.assertEqual(action_schema[0]["resource"], "chrome")
        self.assertEqual(action_schema[1]["action"], "browser_control")
        self.assertEqual(action_schema[1]["resource"], "new_tab")
        self.assertEqual(action_schema[1]["parameters"]["browser"], "chrome")
        self.assertEqual(action_schema[0]["metadata"]["source"], "pattern")
        self.assertEqual(action_schema[1]["metadata"]["source"], "pattern")

    def test_router_splits_open_browser_and_new_tab_into_two_actions(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("open chrome and new tab")

        self.assertIsInstance(action_schema, list)
        self.assertEqual(len(action_schema), 2)
        self.assertEqual(action_schema[0]["action"], "open")
        self.assertEqual(action_schema[0]["resource"], "chrome")
        self.assertEqual(action_schema[1]["action"], "browser_control")
        self.assertEqual(action_schema[1]["resource"], "new_tab")
        self.assertEqual(action_schema[1]["parameters"]["browser"], "chrome")

    def test_router_splits_open_browser_then_new_tab_into_two_actions(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("open chrome then new tab")

        self.assertIsInstance(action_schema, list)
        self.assertEqual(len(action_schema), 2)
        self.assertEqual(action_schema[0]["action"], "open")
        self.assertEqual(action_schema[0]["resource"], "chrome")
        self.assertEqual(action_schema[1]["action"], "browser_control")
        self.assertEqual(action_schema[1]["resource"], "new_tab")
        self.assertEqual(action_schema[1]["parameters"]["browser"], "chrome")

    def test_router_maps_open_google_chrome_with_new_tab(self):
        agent = AgentLoop()

        action_schema = agent.intent_router.route("open google chrome with new tab")

        self.assertIsInstance(action_schema, list)
        self.assertEqual(action_schema[0]["resource"], "chrome")
        self.assertEqual(action_schema[1]["action"], "browser_control")
        self.assertEqual(action_schema[1]["parameters"]["browser"], "chrome")

    def test_executor_returns_meaningful_error_for_missing_open_name(self):
        plugin_manager = PluginManager()
        plugin_manager.plugins["open"] = DummyOpenPlugin()
        executor = Executor(plugin_manager)

        response = executor.execute(
            {
                "action": "open",
                "resource": "",
                "parameters": {},
            }
        )

        self.assertEqual(response, "Please specify which application to open")

    def test_executor_blocks_reserved_open_control_resources(self):
        plugin_manager = PluginManager()
        plugin_manager.plugins["open"] = DummyOpenPlugin()
        executor = Executor(plugin_manager)

        response = executor.execute(
            {
                "action": "open",
                "resource": "new tab",
                "parameters": {"name": "new tab"},
            }
        )

        self.assertEqual(
            response,
            "That request looks like a control command, not an application to open.",
        )

    def test_executor_runs_action_lists_sequentially(self):
        plugin_manager = PluginManager()
        plugin_manager.plugins["open"] = DummyOpenPlugin()
        plugin_manager.plugins["browser_control"] = DummyBrowserControlPlugin()
        executor = Executor(plugin_manager)

        response = executor.execute(
            [
                {"action": "open", "resource": "chrome", "parameters": {"name": "chrome"}},
                {
                    "action": "browser_control",
                    "resource": "new_tab",
                    "parameters": {"browser": "chrome", "resource": "new_tab"},
                },
            ]
        )

        self.assertEqual(
            response,
            "chrome opened [test] | Opened a new tab in chrome [test]",
        )

    def test_executor_stops_multi_step_execution_after_failure(self):
        plugin_manager = PluginManager()
        plugin_manager.plugins["open"] = DummyOpenPlugin()
        plugin_manager.plugins["run_command"] = FailingRunCommandPlugin()
        plugin_manager.plugins["browser_control"] = DummyBrowserControlPlugin()
        executor = Executor(plugin_manager)

        response = executor.execute(
            [
                {"action": "open", "resource": "cmd", "parameters": {"name": "cmd"}},
                {"action": "run_command", "resource": "terminal", "parameters": {"command": "clear"}},
                {
                    "action": "browser_control",
                    "resource": "new_tab",
                    "parameters": {"browser": "chrome", "resource": "new_tab"},
                },
            ]
        )

        self.assertEqual(
            response,
            "cmd opened [test] | Failed to execute 'clear' command",
        )

    def test_executor_returns_partial_result_when_step_crashes(self):
        plugin_manager = PluginManager()
        plugin_manager.plugins["open"] = DummyOpenPlugin()
        plugin_manager.plugins["run_command"] = CrashingRunCommandPlugin()
        plugin_manager.plugins["browser_control"] = DummyBrowserControlPlugin()
        executor = Executor(plugin_manager)

        response = executor.execute(
            [
                {"action": "open", "resource": "cmd", "parameters": {"name": "cmd"}},
                {"action": "run_command", "resource": "terminal", "parameters": {"command": "clear"}},
                {
                    "action": "browser_control",
                    "resource": "new_tab",
                    "parameters": {"browser": "chrome", "resource": "new_tab"},
                },
            ]
        )

        self.assertEqual(
            response,
            "cmd opened [test] | Failed to execute 'clear' command",
        )

    def test_plugin_manager_registers_open_file_plugin(self):
        plugin_manager = PluginManager()

        plugin = plugin_manager.get_plugin("open_file")

        self.assertIsNotNone(plugin)
        self.assertIsInstance(plugin, OpenFilePlugin)

    def test_plugin_manager_registers_browser_control_plugin(self):
        plugin_manager = PluginManager()

        plugin = plugin_manager.get_plugin("browser_control")

        self.assertIsNotNone(plugin)
        self.assertIsInstance(plugin, BrowserControlPlugin)

    def test_plugin_manager_registers_system_control_plugins(self):
        plugin_manager = PluginManager()

        self.assertIsInstance(plugin_manager.get_plugin("restart_system"), SystemControlPlugin)
        self.assertIsInstance(plugin_manager.get_plugin("lock_screen"), SystemControlPlugin)
        self.assertIsInstance(plugin_manager.get_plugin("sleep_system"), SystemControlPlugin)

    def test_plugin_manager_registers_run_command_plugin(self):
        plugin_manager = PluginManager()

        plugin = plugin_manager.get_plugin("run_command")

        self.assertIsNotNone(plugin)
        self.assertIsInstance(plugin, RunCommandPlugin)

    def test_agent_loop_returns_recent_last_five_commands(self):
        agent = AgentLoop()
        agent.plugin_manager.plugins["open"] = DummyOpenPlugin()
        agent.plugin_manager.plugins["play_music"] = DummyPlayMusicPlugin()

        commands = [
            "open chrome",
            "play bhajan",
            "open notepad",
            "play next",
            "open calculator",
            "open paint",
        ]

        for command in commands:
            agent.process(command)

        response = agent.process("show my last commands")

        self.assertEqual(
            response,
            "Recent commands: play bhajan, open notepad, play next, open calculator, open paint",
        )

    def test_agent_loop_explains_latest_suggestion(self):
        memory_path = ROOT / ".codex_tmp" / f"agent_suggestion_{uuid.uuid4().hex}.json"
        self.addCleanup(memory_path.unlink, True)
        agent = AgentLoop()
        agent.memory_manager = MemoryManager(memory_path)
        agent.suggestion_engine = SuggestionEngine(agent.memory, agent.memory_manager)
        agent.plugin_manager.plugins["open"] = DummyOpenPlugin()

        for _ in range(5):
            agent.process("open chrome")

        self.assertEqual(
            agent.get_suggestion(),
            "You usually open chrome. Want me to?",
        )
        self.assertEqual(
            agent.process("why did you suggest chrome"),
            "Because you opened chrome 5 times recently",
        )

    def test_agent_loop_normalizes_before_executor(self):
        agent = AgentLoop()
        agent.plugin_manager.plugins["browser_control"] = DummyBrowserControlPlugin()

        with patch.object(
            agent.intent_router,
            "route",
            return_value={
                "action": "open",
                "resource": "new tab in chrome",
                "parameters": {},
            },
        ):
            response = agent.process("please do it")

        self.assertEqual(response, "Opened a new tab in chrome [test]")

    def test_agent_loop_executes_open_file_intent(self):
        agent = AgentLoop()
        agent.plugin_manager.plugins["open_file"] = DummyOpenFilePlugin()

        with patch.object(
            agent.intent_router,
            "route",
            return_value={
                "action": "open_file",
                "resource": "report.pdf",
                "parameters": {},
            },
        ):
            response = agent.process("open file called report.pdf")

        self.assertEqual(response, "Opened file: report.pdf [test]")

    def test_agent_loop_executes_run_command_intent(self):
        agent = AgentLoop()
        agent.plugin_manager.plugins["run_command"] = DummyRunCommandPlugin()

        with patch.object(
            agent.intent_router,
            "route",
            return_value={
                "action": "run_command",
                "resource": "terminal",
                "parameters": {"command": "clear"},
            },
        ):
            response = agent.process("clear")

        self.assertEqual(response, "Command executed successfully: clear [test]")

    def test_agent_loop_records_successful_action_in_memory_manager(self):
        memory_path = ROOT / ".codex_tmp" / f"memory_manager_{uuid.uuid4().hex}.json"
        self.addCleanup(memory_path.unlink, True)
        agent = AgentLoop()
        agent.memory_manager = MemoryManager(memory_path)
        agent.plugin_manager.plugins["open"] = DummyOpenPlugin()

        agent.process("open chrome")

        stored = json.loads(memory_path.read_text(encoding="utf-8"))
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["action"], "open")
        self.assertEqual(stored[0]["resource"], "chrome")
        self.assertEqual(stored[0]["count"], 1)

    def test_agent_loop_does_not_record_failed_action_in_memory_manager(self):
        memory_path = ROOT / ".codex_tmp" / f"memory_manager_{uuid.uuid4().hex}.json"
        self.addCleanup(memory_path.unlink, True)
        agent = AgentLoop()
        agent.memory_manager = MemoryManager(memory_path)

        with patch.object(
            agent.intent_router,
            "route",
            return_value={
                "action": "unknown",
                "resource": "",
                "parameters": {"message": "LLM unavailable."},
            },
        ):
            agent.process("something unclear")

        stored = json.loads(memory_path.read_text(encoding="utf-8"))
        self.assertEqual(stored, [])

    def test_open_file_plugin_opens_supported_file_when_found(self):
        base_path = ROOT / ".codex_tmp" / f"open_file_test_{uuid.uuid4().hex}"
        documents = base_path / "Documents"
        documents.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, base_path, True)
        target_file = documents / "report.pdf"
        target_file.write_text("test", encoding="utf-8")

        plugin = OpenFilePlugin()

        with patch.object(plugin, "get_search_directories", return_value=[documents]):
            with patch("plugins.open_file.os.startfile", return_value=None) as mock_startfile:
                response = plugin.execute({"name": "report.pdf"})

        self.assertEqual(response, "Opened file: report.pdf")
        mock_startfile.assert_called_once_with(str(target_file))

    def test_open_file_plugin_returns_message_when_file_missing(self):
        base_path = ROOT / ".codex_tmp" / f"open_file_test_{uuid.uuid4().hex}"
        desktop = base_path / "Desktop"
        desktop.mkdir(parents=True, exist_ok=True)
        self.addCleanup(shutil.rmtree, base_path, True)

        plugin = OpenFilePlugin()

        with patch.object(plugin, "get_search_directories", return_value=[desktop]):
            response = plugin.execute({"name": "report.pdf"})

        self.assertIn("couldn't find 'report.pdf'", response.lower())

    def test_system_control_plugin_requires_confirmation_for_restart(self):
        plugin = SystemControlPlugin("restart_system")

        response = plugin.execute({"confirm": False})

        self.assertEqual(response, "Confirmation required before restart")

    def test_system_control_plugin_runs_lock_screen_command(self):
        plugin = SystemControlPlugin("lock_screen")

        with patch("plugins.system_control.subprocess.run") as mock_run:
            response = plugin.execute({})

        self.assertEqual(response, "Lock screen command sent.")
        mock_run.assert_called_once()

    def test_run_command_plugin_executes_clear_on_windows(self):
        plugin = RunCommandPlugin()

        with patch("plugins.run_command.os.name", "nt"):
            with patch("plugins.run_command.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                response = plugin.execute({"command": "clear"})

        self.assertEqual(response, "Command executed successfully: clear")
        mock_run.assert_called_once_with(
            "cls",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

    def test_run_command_plugin_normalizes_ls_to_dir_on_windows(self):
        plugin = RunCommandPlugin()

        with patch("plugins.run_command.os.name", "nt"):
            with patch("plugins.run_command.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                response = plugin.execute({"command": "ls"})

        self.assertEqual(response, "Command executed successfully: ls")
        mock_run.assert_called_once_with(
            "dir",
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

    def test_run_command_plugin_normalize_command_maps_aliases(self):
        self.assertEqual(RunCommandPlugin.normalize_command("clear"), "cls")
        self.assertEqual(RunCommandPlugin.normalize_command("ls"), "dir")

    def test_run_command_plugin_blocks_harmful_commands(self):
        plugin = RunCommandPlugin()

        with patch("plugins.run_command.subprocess.run") as mock_run:
            response = plugin.execute({"command": "del important.txt"})

        self.assertEqual(response, "Blocked unsafe command: del important.txt")
        mock_run.assert_not_called()

    def test_run_command_plugin_rejects_unsupported_commands(self):
        plugin = RunCommandPlugin()

        with patch("plugins.run_command.subprocess.run") as mock_run:
            response = plugin.execute({"command": "pwd"})

        self.assertEqual(response, "Unsupported command: pwd")
        mock_run.assert_not_called()

    def test_play_music_plugin_opens_youtube_search(self):
        plugin = PlayMusicPlugin()

        with patch("plugins.play_music.webbrowser.open", return_value=True) as mock_open:
            response = plugin.execute({"name": "hanuman chalisa"})

        self.assertEqual(response, "Playing music: hanuman chalisa")
        mock_open.assert_called_once()
        called_url = mock_open.call_args.args[0]
        self.assertIn("youtube.com/results", called_url)
        self.assertIn("hanuman+chalisa", called_url)

    def test_play_music_plugin_handles_next_track(self):
        plugin = PlayMusicPlugin()

        with patch.object(plugin, "send_media_key", return_value=True) as mock_send:
            response = plugin.execute({"resource": "next"})

        self.assertEqual(response, "Skipping to the next track.")
        mock_send.assert_called_once_with("next")


if __name__ == "__main__":
    unittest.main()
