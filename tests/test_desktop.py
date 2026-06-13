import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_notify.desktop import (
    apply_install_request,
    app_data_dir,
    backup_file,
    connect_feishu,
    save_bark_settings,
    save_provider_settings,
    send_test_notification,
    sync_hooks,
    user_home,
)
from agent_notify.config import DEFAULT_AGENT_ICON_URL


class DesktopServiceTests(unittest.TestCase):
    @patch("agent_notify.desktop.BarkProvider")
    @patch("agent_notify.desktop.validate_icon_url")
    def test_bark_test_validates_icon_before_sending(
        self, validate_icon, provider_class
    ):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            save_bark_settings(
                path,
                "device-key",
                "https://api.day.app",
                icon="https://example.com/icon.png",
            )
            provider_class.return_value.send.return_value = True

            self.assertTrue(send_test_notification(path))

        validate_icon.assert_called_once_with(
            "https://example.com/icon.png",
            expected_sha256=None,
        )
        provider_class.return_value.send.assert_called_once()

    def test_app_data_dir_uses_roaming_appdata(self):
        path = app_data_dir({"APPDATA": "C:/Users/Test/AppData/Roaming"})

        self.assertEqual(
            path, Path("C:/Users/Test/AppData/Roaming/Agent-Notify")
        )

    def test_user_home_supports_test_override(self):
        path = user_home(
            {"AGENT_NOTIFY_HOME": "C:/Temp/AgentNotifyTest"}
        )

        self.assertEqual(path, Path("C:/Temp/AgentNotifyTest"))

    def test_save_bark_settings_hides_feishu_from_active_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"

            save_bark_settings(
                path,
                "device-key",
                "https://api.day.app",
                "https://example.com/custom",
                "https://example.com/icon.png",
                codex=True,
                claude=False,
            )
            config = json.loads(path.read_text(encoding="utf-8"))

        self.assertTrue(config["providers"]["bark"]["enabled"])
        self.assertEqual(
            config["providers"]["bark"]["device_key"], "device-key"
        )
        self.assertEqual(
            config["providers"]["bark"]["url"],
            "https://example.com/custom",
        )
        self.assertEqual(
            config["providers"]["bark"]["icon"],
            "https://example.com/icon.png",
        )
        self.assertTrue(config["agents"]["codex"])
        self.assertFalse(config["agents"]["claude"])
        self.assertFalse(config["providers"]["feishu"]["enabled"])

    def test_save_bark_settings_restores_defaults_when_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"

            save_bark_settings(
                path,
                "device-key",
                "https://api.day.app",
                "",
                "",
            )
            config = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(
            config["providers"]["bark"]["url"],
            "chatgpt://",
        )
        self.assertEqual(
            config["providers"]["bark"]["icon"],
            DEFAULT_AGENT_ICON_URL,
        )

    def test_backup_file_creates_timestamped_copy(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "hooks.json"
            path.write_text('{"hooks": {}}', encoding="utf-8")

            backup = backup_file(path)

            self.assertIsNotNone(backup)
            self.assertTrue(backup.exists())
            self.assertEqual(backup.read_text(encoding="utf-8"), '{"hooks": {}}')
            self.assertIn(".agent-notify-backup-", backup.name)

    def test_apply_install_request_configures_bark_and_selected_hooks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = root / "install-request.json"
            config = root / "appdata" / "config.json"
            home = root / "home"
            hook_exe = root / "Agent-Notify.exe"
            request.write_text(
                json.dumps(
                    {
                        "device_key": "bark-key",
                        "server": "https://api.day.app",
                        "url": "https://example.com/installed",
                        "icon": "https://example.com/installed.png",
                        "codex": True,
                        "claude": False,
                    }
                ),
                encoding="utf-8",
            )

            changed = apply_install_request(
                request, config, home, hook_exe
            )

            saved = json.loads(config.read_text(encoding="utf-8"))
            codex = json.loads(
                (home / ".codex" / "hooks.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                saved["providers"]["bark"]["device_key"], "bark-key"
            )
            self.assertEqual(
                saved["providers"]["bark"]["url"],
                "https://example.com/installed",
            )
            self.assertEqual(
                saved["providers"]["bark"]["icon"],
                "https://example.com/installed.png",
            )
            self.assertTrue(saved["agents"]["codex"])
            self.assertFalse(saved["agents"]["claude"])
            self.assertIn("PermissionRequest", codex["hooks"])
            self.assertIn("PreToolUse", codex["hooks"])
            self.assertFalse((home / ".claude" / "settings.json").exists())
            self.assertFalse((home / ".codex" / "AGENTS.md").exists())
            self.assertEqual(len(changed), 1)

    def test_save_provider_settings_allows_control_without_notifications(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"

            save_provider_settings(
                path,
                bark={
                    "enabled": False,
                    "device_key": "",
                    "server": "https://api.day.app",
                    "url": "chatgpt://",
                    "icon": "",
                    "mode": "off",
                },
                feishu={
                    "enabled": False,
                    "control_enabled": True,
                    "mode": "all",
                    "open_id": "ou_owner",
                    "chat_id": "oc_private",
                    "lark_cli": "lark-cli",
                },
                agents={"codex": True, "claude": False},
            )
            config = json.loads(path.read_text(encoding="utf-8"))

        self.assertFalse(config["providers"]["bark"]["enabled"])
        self.assertFalse(config["providers"]["feishu"]["enabled"])
        self.assertTrue(
            config["providers"]["feishu"]["control_enabled"]
        )
        self.assertEqual(config["providers"]["feishu"]["open_id"], "ou_owner")
        self.assertTrue(config["agents"]["codex"])
        self.assertFalse(config["agents"]["claude"])

    def test_connect_feishu_persists_discovered_chat_id(self):
        class Client:
            def connect(self, open_id):
                self.open_id = open_id
                return "oc_discovered"

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            client = Client()

            chat_id = connect_feishu(path, "ou_owner", client)
            config = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(chat_id, "oc_discovered")
        self.assertEqual(client.open_id, "ou_owner")
        self.assertEqual(
            config["providers"]["feishu"]["chat_id"], "oc_discovered"
        )

    def test_install_removes_legacy_question_instruction(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / "home"
            agents = home / ".codex" / "AGENTS.md"
            agents.parent.mkdir(parents=True)
            agents.write_text(
                "# User rules\n\n"
                "Keep this.\n\n"
                "<!-- agent-notify:question-hook:start -->\n"
                "old fallback\n"
                "<!-- agent-notify:question-hook:end -->\n",
                encoding="utf-8",
            )

            from agent_notify.desktop import install_hooks

            changed = install_hooks(
                home, root / "Agent-Notify.exe", codex=True, claude=False
            )

            text = agents.read_text(encoding="utf-8")
            self.assertIn("Keep this.", text)
            self.assertNotIn("agent-notify:question-hook", text)
            self.assertIn(agents, changed)

    def test_sync_hooks_removes_only_disabled_agent_notify_hooks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / "home"
            executable = root / "Agent-Notify.exe"

            sync_hooks(
                home,
                executable,
                codex=True,
                claude=True,
            )
            sync_hooks(
                home,
                executable,
                codex=True,
                claude=False,
            )

            codex = json.loads(
                (home / ".codex" / "hooks.json").read_text(encoding="utf-8")
            )
            claude = json.loads(
                (home / ".claude" / "settings.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertIn("PermissionRequest", codex["hooks"])
        self.assertNotIn("hooks", claude)


if __name__ == "__main__":
    unittest.main()
