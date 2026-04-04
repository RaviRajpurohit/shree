import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agent_loop import AgentLoop
from core.executor import Executor
from core.intent_engine import clean_input
from core.memory import Memory
from core.intent_router import IntentRouter
from plugins.base_plugin import BasePlugin
from plugins.browser_control import BrowserControlPlugin
from plugins.play_music import PlayMusicPlugin
from plugins.plugin_manager import PluginManager


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


class ShreeFeatureTests(unittest.TestCase):
    def test_clean_input_normalizes_command(self):
        self.assertEqual(
            clean_input("Can you please open chrome?"),
            "open chrome",
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

    def test_plugin_manager_registers_browser_control_plugin(self):
        plugin_manager = PluginManager()

        plugin = plugin_manager.get_plugin("browser_control")

        self.assertIsNotNone(plugin)
        self.assertIsInstance(plugin, BrowserControlPlugin)

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
        agent = AgentLoop()
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
