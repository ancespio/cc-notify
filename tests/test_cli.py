import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import desktop_hook


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "notify_hook.py"
DESKTOP_HOOK = ROOT / "desktop_hook.py"
SETUP = ROOT / "setup_guide.py"


class HookCliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp = Path(self.temp_dir.name)
        config = {
            "providers": {
                "bark": {"enabled": False},
                "feishu": {"enabled": False},
            },
            "events": {
                "permission": True,
                "question": True,
                "stop": True,
            },
        }
        self.config_path = self.temp / "config.json"
        self.config_path.write_text(json.dumps(config), encoding="utf-8")
        self.env = os.environ.copy()
        self.env["AGENT_NOTIFY_CONFIG"] = str(self.config_path)
        self.env["AGENT_NOTIFY_MODE"] = str(self.temp / "mode.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_hook(self, args=None, stdin=""):
        return subprocess.run(
            [sys.executable, str(HOOK), *(args or [])],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=self.env,
            timeout=10,
        )

    def test_invalid_json_is_silent_and_fail_open(self):
        result = self.run_hook(stdin="{not json")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_question_argument_is_silent_and_fail_open(self):
        result = self.run_hook(["--question", "Choose A or B"])

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")

    def test_hook_payload_is_silent(self):
        result = self.run_hook(
            stdin=json.dumps(
                {
                    "hook_event_name": "PermissionRequest",
                    "source": "codex",
                    "cwd": str(ROOT),
                    "tool_name": "shell_command",
                    "tool_input": {"command": "git status"},
                }
            )
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")


class SetupCliTests(unittest.TestCase):
    def test_setup_installs_both_agents_idempotently(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            home = temp / "home"
            config = temp / "config.json"
            agents = home / ".codex" / "AGENTS.md"
            agents.parent.mkdir(parents=True)
            agents.write_text(
                "# User rules\n\n"
                "Keep this.\n\n"
                "<!-- agent-notify:question-hook:start -->\n"
                "legacy fallback\n"
                "<!-- agent-notify:question-hook:end -->\n",
                encoding="utf-8",
            )
            command = [
                sys.executable,
                str(SETUP),
                "--home",
                str(home),
                "--config",
                str(config),
                "--bark-key",
                "test-key",
            ]

            first = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8"
            )
            second = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8"
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            codex = json.loads(
                (home / ".codex" / "hooks.json").read_text(encoding="utf-8")
            )
            claude = json.loads(
                (home / ".claude" / "settings.json").read_text(encoding="utf-8")
            )
            installed = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(len(codex["hooks"]["PermissionRequest"]), 1)
            self.assertEqual(len(claude["hooks"]["Elicitation"]), 1)
            self.assertEqual(
                installed["providers"]["bark"]["device_key"], "test-key"
            )
            agents_text = agents.read_text(encoding="utf-8")
            self.assertIn("Keep this.", agents_text)
            self.assertNotIn("agent-notify:question-hook", agents_text)


class DesktopHookCliTests(unittest.TestCase):
    def test_parse_args_accepts_settings_tray_and_autostart_actions(self):
        args = desktop_hook.parse_args(
            [
                "--tray",
                "--smoke-test",
                "--settings-smoke-test",
                "--onboarding",
                "--onboarding-smoke-test",
                "--enable-autostart",
                "--disable-autostart",
                "--stop-tray",
            ]
        )

        self.assertTrue(args.tray)
        self.assertTrue(args.smoke_test)
        self.assertTrue(args.settings_smoke_test)
        self.assertTrue(args.onboarding)
        self.assertTrue(args.onboarding_smoke_test)
        self.assertTrue(args.enable_autostart)
        self.assertTrue(args.disable_autostart)
        self.assertTrue(args.stop_tray)

    def test_no_arguments_open_settings(self):
        args = desktop_hook.parse_args([])

        self.assertTrue(desktop_hook.should_open_settings(args))

    def test_hook_argument_does_not_open_settings(self):
        args = desktop_hook.parse_args(["--hook"])

        self.assertFalse(desktop_hook.should_open_settings(args))

    @patch("desktop_hook.run_settings_app", return_value=0)
    def test_settings_smoke_test_opens_real_app(self, run_app_mock):
        result = desktop_hook.main(["--settings-smoke-test"])

        self.assertEqual(result, 0)
        run_app_mock.assert_called_once_with(smoke_test=True)

    @patch("desktop_hook.run_settings_app", return_value=0)
    def test_onboarding_opens_wizard(self, run_app_mock):
        result = desktop_hook.main(["--onboarding"])

        self.assertEqual(result, 0)
        run_app_mock.assert_called_once_with(
            smoke_test=False, onboarding=True
        )

    @patch("desktop_hook.run_settings_app", return_value=0)
    def test_onboarding_smoke_test_opens_real_wizard(self, run_app_mock):
        result = desktop_hook.main(["--onboarding-smoke-test"])

        self.assertEqual(result, 0)
        run_app_mock.assert_called_once_with(
            smoke_test=True, onboarding=True
        )

    def test_command_smoke_test_returns_success(self):
        result = desktop_hook.main(["--smoke-test"])

        self.assertEqual(result, 0)

    def test_install_failure_returns_nonzero(self):
        result = subprocess.run(
            [
                sys.executable,
                str(DESKTOP_HOOK),
                "--install-request",
                "missing-request.json",
                "--home",
                str(ROOT / "work" / "missing-home"),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
