import json
import tempfile
import unittest
from pathlib import Path

from agent_notify.installer import (
    QUESTION_MARKER_END,
    QUESTION_MARKER_START,
    install_claude_hooks,
    install_claude_executable_hooks,
    install_codex_hooks,
    install_codex_executable_hooks,
    remove_agent_instructions,
    remove_claude_hooks,
    remove_codex_hooks,
)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name)
        self.script = self.home / "Agent-Notify" / "notify_hook.py"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_codex_hook_merge_preserves_existing_and_is_idempotent(self):
        path = self.home / ".codex" / "hooks.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": [
                            {
                                "hooks": [
                                    {"type": "command", "command": "python existing.py"}
                                ]
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        install_codex_hooks(path, self.script, "python")
        install_codex_hooks(path, self.script, "python")
        data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(len(data["hooks"]["PermissionRequest"]), 1)
        self.assertEqual(len(data["hooks"]["PreToolUse"]), 1)
        self.assertEqual(
            data["hooks"]["PreToolUse"][0]["matcher"],
            "^request_user_input$",
        )
        self.assertEqual(len(data["hooks"]["Stop"]), 2)
        own = [
            group
            for group in data["hooks"]["Stop"]
            if "Agent-Notify" in group["hooks"][0].get("statusMessage", "")
        ]
        self.assertEqual(len(own), 1)

    def test_legacy_cc_notify_hook_is_replaced(self):
        legacy_name = "cc" + "-notify"
        path = self.home / ".codex" / "hooks.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": (
                                            f'python "C:/tools/{legacy_name}/notify_hook.py"'
                                        ),
                                    }
                                ]
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )

        install_codex_hooks(path, self.script, "python")
        data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(len(data["hooks"]["Stop"]), 1)
        command = data["hooks"]["Stop"][0]["hooks"][0]["command"]
        self.assertNotIn(legacy_name, command)

    def test_claude_hook_merge_adds_all_events_without_overwriting(self):
        path = self.home / ".claude" / "settings.json"
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps({"hooks": {"Stop": [{"hooks": [{"command": "keep-me"}]}]}}),
            encoding="utf-8",
        )

        install_claude_hooks(path, self.script, "python")
        install_claude_hooks(path, self.script, "python")
        data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(len(data["hooks"]["PermissionRequest"]), 1)
        self.assertEqual(len(data["hooks"]["PreToolUse"]), 1)
        self.assertEqual(len(data["hooks"]["Elicitation"]), 1)
        self.assertEqual(len(data["hooks"]["Stop"]), 2)
        self.assertEqual(data["hooks"]["PreToolUse"][0]["matcher"], "AskUserQuestion")
        hook = data["hooks"]["Elicitation"][0]["hooks"][0]
        self.assertEqual(hook["command"], "python")
        self.assertEqual(hook["args"], [str(self.script)])

    def test_writes_utf8_without_bom(self):
        path = self.home / ".codex" / "hooks.json"

        install_codex_hooks(path, self.script, "python")

        self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_executable_hooks_use_installed_hook_binary(self):
        codex_path = self.home / ".codex" / "hooks.json"
        claude_path = self.home / ".claude" / "settings.json"
        hook_exe = Path("C:/Program Files/Agent-Notify/Agent-Notify-Hook.exe")

        install_codex_executable_hooks(codex_path, hook_exe)
        install_claude_executable_hooks(claude_path, hook_exe)

        codex = json.loads(codex_path.read_text(encoding="utf-8"))
        claude = json.loads(claude_path.read_text(encoding="utf-8"))
        codex_hook = codex["hooks"]["PermissionRequest"][0]["hooks"][0]
        codex_question = codex["hooks"]["PreToolUse"][0]
        claude_hook = claude["hooks"]["PreToolUse"][0]["hooks"][0]
        self.assertEqual(codex_question["matcher"], "^request_user_input$")
        self.assertEqual(
            codex_hook["commandWindows"],
            '& "C:\\Program Files\\Agent-Notify\\Agent-Notify-Hook.exe" --hook',
        )
        self.assertEqual(claude_hook["command"], str(hook_exe))
        self.assertEqual(claude_hook["args"], ["--hook"])

    def test_remove_hooks_preserves_unrelated_entries(self):
        codex_path = self.home / ".codex" / "hooks.json"
        claude_path = self.home / ".claude" / "settings.json"
        hook_exe = Path("C:/Program Files/Agent-Notify/Agent-Notify-Hook.exe")
        codex_path.parent.mkdir(parents=True)
        claude_path.parent.mkdir(parents=True)
        existing = {
            "hooks": {
                "Stop": [
                    {"hooks": [{"type": "command", "command": "keep-me"}]}
                ]
            }
        }
        codex_path.write_text(json.dumps(existing), encoding="utf-8")
        claude_path.write_text(json.dumps(existing), encoding="utf-8")

        install_codex_executable_hooks(codex_path, hook_exe)
        install_claude_executable_hooks(claude_path, hook_exe)
        remove_codex_hooks(codex_path)
        remove_claude_hooks(claude_path)

        codex = json.loads(codex_path.read_text(encoding="utf-8"))
        claude = json.loads(claude_path.read_text(encoding="utf-8"))
        self.assertEqual(codex["hooks"]["Stop"][0]["hooks"][0]["command"], "keep-me")
        self.assertEqual(claude["hooks"]["Stop"][0]["hooks"][0]["command"], "keep-me")
        self.assertNotIn("PermissionRequest", codex["hooks"])
        self.assertNotIn("PreToolUse", claude["hooks"])

    def test_remove_question_instruction_preserves_user_content(self):
        path = self.home / ".codex" / "AGENTS.md"
        path.parent.mkdir(parents=True)
        path.write_text(
            "# User rules\n\n"
            "Keep this.\n\n"
            f"{QUESTION_MARKER_START}\n"
            "legacy fallback\n"
            f"{QUESTION_MARKER_END}\n",
            encoding="utf-8",
        )

        remove_agent_instructions(path)

        text = path.read_text(encoding="utf-8")
        self.assertIn("Keep this.", text)
        self.assertNotIn(QUESTION_MARKER_START, text)


if __name__ == "__main__":
    unittest.main()
