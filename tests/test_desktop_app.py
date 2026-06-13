import json
import tempfile
import unittest
from pathlib import Path

import wx

from agent_notify.config import DEFAULT_BARK_ICON_URL
from desktop_app import (
    SecretField,
    SettingsValues,
    apply_settings,
    legacy_bark_warnings,
    load_settings_values,
    validate_settings,
)


class DesktopAppServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = wx.App(False)

    @classmethod
    def tearDownClass(cls):
        cls.app.Destroy()

    def test_secret_field_switches_without_losing_edited_value(self):
        frame = wx.Frame(None)
        field = SecretField(frame, "first-secret")
        try:
            field.show_plain_text(True)
            self.assertEqual(field.GetValue(), "first-secret")
            field.plain_ctrl.SetValue("edited-secret")
            field.show_plain_text(False)
            self.assertEqual(field.GetValue(), "edited-secret")
            field.show_plain_text(True)
            self.assertEqual(field.GetValue(), "edited-secret")
        finally:
            frame.Destroy()

    def test_legacy_bark_defaults_are_warned_but_not_changed(self):
        warnings = legacy_bark_warnings(
            "chatgpt://codex",
            (
                "https://raw.githubusercontent.com/Finb/Bark/master/"
                "Bark/Assets.xcassets/AppIcon.appiconset/bark.png"
            ),
        )

        self.assertIn("跳转", warnings)
        self.assertIn("图标", warnings)

    def test_load_settings_values_reads_all_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "providers": {
                            "bark": {
                                "enabled": True,
                                "device_key": "secret",
                                "server": "https://bark.example",
                                "url": "chatgpt://",
                                "icon": "https://example.com/bark.png",
                                "mode": "ssh-only",
                            },
                            "feishu": {
                                "enabled": False,
                                "control_enabled": True,
                                "mode": "off",
                                "open_id": "ou_owner",
                                "chat_id": "oc_private",
                                "lark_cli": "lark-cli",
                            },
                        },
                        "agents": {
                            "codex": True,
                            "claude": False,
                        },
                    }
                ),
                encoding="utf-8",
            )

            values = load_settings_values(path)

        self.assertEqual(values.device_key, "secret")
        self.assertTrue(values.bark_enabled)
        self.assertEqual(values.bark_mode, "ssh-only")
        self.assertEqual(values.server, "https://bark.example")
        self.assertEqual(values.url, "chatgpt://")
        self.assertEqual(values.icon, "https://example.com/bark.png")
        self.assertTrue(values.codex)
        self.assertFalse(values.claude)
        self.assertFalse(values.feishu_enabled)
        self.assertTrue(values.feishu_control_enabled)
        self.assertEqual(values.feishu_mode, "off")
        self.assertEqual(values.open_id, "ou_owner")
        self.assertEqual(values.chat_id, "oc_private")
        self.assertEqual(values.lark_cli, "lark-cli")

    def test_apply_settings_saves_config_and_syncs_hook_selection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = root / "config.json"
            home = root / "home"
            executable = root / "Agent-Notify.exe"
            values = SettingsValues(
                bark_enabled=False,
                device_key="new-key",
                server="https://api.day.app",
                url="",
                icon="",
                bark_mode="off",
                feishu_enabled=False,
                feishu_control_enabled=True,
                feishu_mode="all",
                open_id="ou_owner",
                chat_id="oc_private",
                lark_cli="lark-cli",
                codex=False,
                claude=True,
            )

            changed = apply_settings(
                values,
                config,
                home,
                executable,
            )

            saved = json.loads(config.read_text(encoding="utf-8"))
            bark = saved["providers"]["bark"]
            self.assertEqual(bark["device_key"], "new-key")
            self.assertEqual(bark["url"], "chatgpt://")
            self.assertEqual(bark["icon"], DEFAULT_BARK_ICON_URL)
            self.assertFalse(bark["enabled"])
            self.assertTrue(
                saved["providers"]["feishu"]["control_enabled"]
            )
            self.assertFalse(saved["agents"]["codex"])
            self.assertTrue(saved["agents"]["claude"])
            self.assertFalse((home / ".codex" / "hooks.json").exists())
            self.assertTrue((home / ".claude" / "settings.json").exists())
            self.assertEqual(len(changed), 1)

    def test_enabled_bark_requires_key(self):
        values = SettingsValues(
            bark_enabled=True,
            device_key="",
            server="https://api.day.app",
            url="chatgpt://",
            icon=DEFAULT_BARK_ICON_URL,
            bark_mode="all",
            feishu_enabled=False,
            feishu_control_enabled=False,
            feishu_mode="all",
            open_id="",
            chat_id="",
            lark_cli="",
            codex=True,
            claude=True,
        )

        with self.assertRaisesRegex(ValueError, "Bark Key"):
            validate_settings(values)

    def test_feishu_features_require_open_id_and_cli(self):
        values = SettingsValues(
            bark_enabled=False,
            device_key="",
            server="https://api.day.app",
            url="chatgpt://",
            icon=DEFAULT_BARK_ICON_URL,
            bark_mode="off",
            feishu_enabled=False,
            feishu_control_enabled=True,
            feishu_mode="all",
            open_id="",
            chat_id="",
            lark_cli="",
            codex=True,
            claude=True,
        )

        with self.assertRaisesRegex(ValueError, "open_id"):
            validate_settings(values)

        values.open_id = "ou_owner"
        with self.assertRaisesRegex(ValueError, "lark-cli"):
            validate_settings(values)

    def test_all_notifications_may_be_disabled(self):
        values = SettingsValues(
            bark_enabled=False,
            device_key="",
            server="https://api.day.app",
            url="chatgpt://",
            icon=DEFAULT_BARK_ICON_URL,
            bark_mode="off",
            feishu_enabled=False,
            feishu_control_enabled=False,
            feishu_mode="off",
            open_id="",
            chat_id="",
            lark_cli="",
            codex=True,
            claude=True,
        )

        validate_settings(values)


if __name__ == "__main__":
    unittest.main()
