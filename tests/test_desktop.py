import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents_notify.desktop import (
    BarkTestError,
    apply_install_request,
    app_data_dir,
    backup_file,
    connect_feishu,
    legacy_app_data_dir,
    migrate_legacy_brand_data,
    save_bark_settings,
    save_provider_settings,
    send_feishu_test_notification,
    send_test_notification,
    sync_hooks,
    user_home,
)
from agents_notify.config import DEFAULT_AGENT_ICON_URL


class DesktopServiceTests(unittest.TestCase):
    @patch("agents_notify.desktop.BarkProvider")
    @patch("agents_notify.desktop.validate_icon_url")
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

    def test_bark_test_reports_configuration_stage(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"

            with self.assertRaises(BarkTestError) as caught:
                send_test_notification(path)

        self.assertEqual(caught.exception.stage, "configuration")
        self.assertIn("Bark Key", str(caught.exception))

    @patch("agents_notify.desktop.validate_icon_url")
    def test_bark_test_reports_icon_stage(self, validate_icon):
        validate_icon.side_effect = OSError("remote icon is unavailable")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            save_bark_settings(path, "device-key", "https://api.day.app")

            with self.assertRaises(BarkTestError) as caught:
                send_test_notification(path)

        self.assertEqual(caught.exception.stage, "icon")
        self.assertNotIn("device-key", str(caught.exception))

    @patch("agents_notify.desktop.BarkProvider")
    @patch("agents_notify.desktop.validate_icon_url")
    def test_bark_test_reports_push_stage(
        self, _validate_icon, provider_class
    ):
        provider_class.return_value.send.return_value = False
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            save_bark_settings(path, "device-key", "https://api.day.app")

            with self.assertRaises(BarkTestError) as caught:
                send_test_notification(path)

        self.assertEqual(caught.exception.stage, "push")

    def test_app_data_dir_uses_roaming_appdata(self):
        path = app_data_dir({"APPDATA": "C:/Users/Test/AppData/Roaming"})

        self.assertEqual(
            path, Path("C:/Users/Test/AppData/Roaming/Agents-Notify")
        )

    def test_legacy_app_data_dir_uses_old_brand(self):
        path = legacy_app_data_dir(
            {"APPDATA": "C:/Users/Test/AppData/Roaming"}
        )

        self.assertEqual(
            path, Path("C:/Users/Test/AppData/Roaming/Agent-Notify")
        )

    def test_brand_migration_copies_old_config_and_preserves_secrets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_dir = root / "Agent-Notify"
            new_dir = root / "Agents-Notify"
            old_dir.mkdir()
            old_config = {
                "config_version": "1.0.2",
                "providers": {
                    "bark": {
                        "device_key": "secret-bark-key",
                        "group": "Agent-Notify",
                        "icon": (
                            "https://raw.githubusercontent.com/ancespio/"
                            "Agent-Notify/master/assets/agent-notify.png"
                        ),
                        "mode": "ssh-only",
                    },
                    "feishu": {
                        "control_enabled": True,
                        "mode": "all",
                        "open_id": "ou_secret",
                        "chat_id": "oc_secret",
                    },
                },
                "agents": {"codex": True, "claude": False},
            }
            (old_dir / "config.json").write_text(
                json.dumps(old_config), encoding="utf-8"
            )
            (old_dir / "mode.json").write_text(
                '{"mode": "ssh-only"}', encoding="utf-8"
            )

            migrated = migrate_legacy_brand_data(new_dir, old_dir)
            first_text = (new_dir / "config.json").read_text(
                encoding="utf-8"
            )
            migrate_legacy_brand_data(new_dir, old_dir)
            second_text = (new_dir / "config.json").read_text(
                encoding="utf-8"
            )
            old_config_still_exists = (old_dir / "config.json").exists()
            migrated_mode = (new_dir / "mode.json").read_text(
                encoding="utf-8"
            )

        self.assertTrue(migrated)
        self.assertEqual(first_text, second_text)
        config = json.loads(first_text)
        self.assertEqual(
            config["providers"]["bark"]["device_key"],
            "secret-bark-key",
        )
        self.assertEqual(config["providers"]["feishu"]["open_id"], "ou_secret")
        self.assertEqual(config["providers"]["feishu"]["chat_id"], "oc_secret")
        self.assertEqual(config["providers"]["bark"]["group"], "Agents-Notify")
        self.assertIn(
            "Agents-Notify/master/assets/agents-notify.png",
            config["providers"]["bark"]["icon"],
        )
        self.assertTrue(old_config_still_exists)
        self.assertEqual(migrated_mode, '{"mode": "ssh-only"}')

    def test_brand_migration_preserves_custom_icon_and_existing_new_config(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_dir = root / "Agent-Notify"
            new_dir = root / "Agents-Notify"
            old_dir.mkdir()
            new_dir.mkdir()
            (old_dir / "config.json").write_text(
                json.dumps(
                    {
                        "providers": {
                            "bark": {
                                "device_key": "old-key",
                                "icon": "https://example.com/custom.png",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            (new_dir / "config.json").write_text(
                json.dumps(
                    {
                        "providers": {
                            "bark": {
                                "device_key": "new-key",
                                "icon": "https://example.com/new.png",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            migrated = migrate_legacy_brand_data(new_dir, old_dir)
            config = json.loads(
                (new_dir / "config.json").read_text(encoding="utf-8")
            )

        self.assertFalse(migrated)
        self.assertEqual(config["providers"]["bark"]["device_key"], "new-key")
        self.assertEqual(
            config["providers"]["bark"]["icon"],
            "https://example.com/new.png",
        )

    def test_brand_migration_applies_legacy_mode_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            old_dir = root / "Agent-Notify"
            new_dir = root / "Agents-Notify"
            old_dir.mkdir()
            (old_dir / "config.json").write_text(
                json.dumps(
                    {
                        "providers": {
                            "bark": {"device_key": "keep-key"},
                            "feishu": {},
                        }
                    }
                ),
                encoding="utf-8",
            )
            (old_dir / "mode.json").write_text(
                '{"mode": "ssh-only"}', encoding="utf-8"
            )

            migrate_legacy_brand_data(new_dir, old_dir)
            config = json.loads(
                (new_dir / "config.json").read_text(encoding="utf-8")
            )

        self.assertEqual(config["providers"]["bark"]["mode"], "ssh-only")
        self.assertEqual(config["providers"]["feishu"]["mode"], "ssh-only")

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
        self.assertNotIn("enabled", config["providers"]["bark"])
        self.assertNotIn("enabled", config["providers"]["feishu"])
        self.assertEqual(config["providers"]["feishu"]["mode"], "off")

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
            "chatgpt://codex",
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
            self.assertIn(".agents-notify-backup-", backup.name)

    def test_apply_install_request_configures_bark_and_selected_hooks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request = root / "install-request.json"
            config = root / "appdata" / "config.json"
            home = root / "home"
            hook_exe = root / "Agents-Notify.exe"
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
                    "device_key": "",
                    "server": "https://api.day.app",
                    "url": "chatgpt://",
                    "icon": "",
                    "mode": "off",
                },
                feishu={
                    "control_enabled": True,
                    "mode": "off",
                    "open_id": "ou_owner",
                    "chat_id": "oc_private",
                },
                agents={"codex": True, "claude": False},
            )
            config = json.loads(path.read_text(encoding="utf-8"))

        self.assertNotIn("enabled", config["providers"]["bark"])
        self.assertNotIn("enabled", config["providers"]["feishu"])
        self.assertTrue(
            config["providers"]["feishu"]["control_enabled"]
        )
        self.assertEqual(config["providers"]["feishu"]["open_id"], "ou_owner")
        self.assertTrue(config["agents"]["codex"])
        self.assertFalse(config["agents"]["claude"])

    @patch("agents_notify.desktop.FeishuProvider")
    def test_feishu_test_uses_real_notification_even_when_mode_is_off(
        self, provider_class
    ):
        provider_class.return_value.send.return_value = True
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            save_provider_settings(
                path,
                bark={"mode": "off"},
                feishu={
                    "mode": "off",
                    "control_enabled": False,
                    "app_id": "cli_app",
                    "app_secret": "secret_app",
                    "open_id": "ou_owner",
                    "chat_id": "oc_private",
                },
                agents={"codex": True, "claude": True},
            )

            self.assertTrue(send_feishu_test_notification(path))

        event = provider_class.return_value.send.call_args.args[0]
        self.assertEqual(event.kind, "stop")
        self.assertIn("飞书测试", event.summary)

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

            from agents_notify.desktop import install_hooks

            changed = install_hooks(
                home, root / "Agents-Notify.exe", codex=True, claude=False
            )

            text = agents.read_text(encoding="utf-8")
            self.assertIn("Keep this.", text)
            self.assertNotIn("agent-notify:question-hook", text)
            self.assertIn(agents, changed)

    def test_sync_hooks_removes_only_disabled_agents_notify_hooks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            home = root / "home"
            executable = root / "Agents-Notify.exe"

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
