import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call

from agents_notify.config import load_config
from agents_notify.tray_app import (
    LEGACY_RUN_VALUE_NAME,
    RUN_VALUE_NAME,
    _make_icon,
    autostart_command,
    build_feishu_controller,
    feishu_control_missing_fields,
    is_autostart_enabled,
    migrate_legacy_autostart,
    notification_status_text,
    restart_tray,
    set_feishu_control,
    set_provider_mode,
    settings_command,
    set_autostart,
    self_launch_environment,
)


class TrayAppTests(unittest.TestCase):
    def test_tray_uses_custom_icon_for_enabled_and_disabled_states(self):
        enabled = _make_icon(True)
        disabled = _make_icon(False)

        self.assertEqual(enabled.size, (64, 64))
        self.assertEqual(disabled.size, (64, 64))
        self.assertNotEqual(enabled.getpixel((32, 32)), (0, 0, 0, 0))
        self.assertNotEqual(
            enabled.convert("RGBA").tobytes(),
            disabled.convert("RGBA").tobytes(),
        )

    def test_autostart_command_quotes_executable(self):
        command = autostart_command(
            Path("C:/Program Files/Agents-Notify/Agents-Notify.exe")
        )

        self.assertEqual(
            command,
            '"C:\\Program Files\\Agents-Notify\\Agents-Notify.exe" --tray',
        )

    def test_set_autostart_writes_and_removes_run_value(self):
        registry = MagicMock()
        registry.HKEY_CURRENT_USER = object()
        registry.REG_SZ = 1
        key = registry.CreateKey.return_value.__enter__.return_value
        executable = Path(
            "C:/Program Files/Agents-Notify/Agents-Notify.exe"
        )

        set_autostart(True, executable, registry)
        set_autostart(False, executable, registry)

        registry.SetValueEx.assert_called_once_with(
            key, RUN_VALUE_NAME, 0, registry.REG_SZ,
            autostart_command(executable),
        )
        self.assertEqual(
            registry.DeleteValue.call_args_list,
            [
                call(key, LEGACY_RUN_VALUE_NAME),
                call(key, RUN_VALUE_NAME),
                call(key, LEGACY_RUN_VALUE_NAME),
            ],
        )

    def test_migrate_legacy_autostart_replaces_old_run_value(self):
        registry = MagicMock()
        registry.HKEY_CURRENT_USER = object()
        registry.REG_SZ = 1
        old_key = registry.OpenKey.return_value.__enter__.return_value
        new_key = registry.CreateKey.return_value.__enter__.return_value
        executable = Path(
            "C:/Program Files/Agents-Notify/Agents-Notify.exe"
        )
        registry.QueryValueEx.return_value = (
            '"C:\\Program Files\\Agent-Notify\\Agent-Notify.exe" --tray',
            1,
        )

        self.assertTrue(migrate_legacy_autostart(executable, registry))

        registry.QueryValueEx.assert_called_once_with(
            old_key, LEGACY_RUN_VALUE_NAME
        )
        registry.SetValueEx.assert_called_once_with(
            new_key,
            RUN_VALUE_NAME,
            0,
            registry.REG_SZ,
            autostart_command(executable),
        )

    def test_settings_command_starts_same_executable_without_arguments(self):
        executable = Path(
            "C:/Program Files/Agents-Notify/Agents-Notify.exe"
        )

        self.assertEqual(settings_command(executable), [str(executable)])

    def test_frozen_self_launch_resets_pyinstaller_environment(self):
        environment = self_launch_environment(
            {"KEEP": "value"}, frozen=True
        )

        self.assertEqual(environment["KEEP"], "value")
        self.assertEqual(
            environment["PYINSTALLER_RESET_ENVIRONMENT"], "1"
        )

    def test_is_autostart_enabled_requires_matching_command(self):
        registry = MagicMock()
        registry.HKEY_CURRENT_USER = object()
        key = registry.OpenKey.return_value.__enter__.return_value
        executable = Path(
            "C:/Program Files/Agents-Notify/Agents-Notify.exe"
        )
        registry.QueryValueEx.return_value = (
            autostart_command(executable),
            1,
        )

        self.assertTrue(
            is_autostart_enabled(executable, registry)
        )
        registry.QueryValueEx.return_value = ("other.exe", 1)
        self.assertFalse(
            is_autostart_enabled(executable, registry)
        )

    def test_set_provider_mode_updates_only_selected_channel(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"

            set_provider_mode(path, "bark", "off")
            config = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(config["providers"]["bark"]["mode"], "off")
        self.assertEqual(config["providers"]["feishu"]["mode"], "off")

    def test_notification_status_text_lists_both_modes_and_control(self):
        text = notification_status_text(
            {
                "providers": {
                    "bark": {"mode": "all"},
                    "feishu": {
                        "mode": "ssh-only",
                        "control_enabled": True,
                    },
                }
            }
        )

        self.assertEqual(
            text,
            "Agents-Notify | Bark：全部通知 | 飞书：仅 SSH | 遥控：开启",
        )

    def test_feishu_control_missing_fields_reports_prerequisites(self):
        missing = feishu_control_missing_fields(
            {
                "app_id": "",
                "app_secret": "",
                "open_id": "",
                "chat_id": "",
            }
        )

        self.assertEqual(
            missing, ("app_id", "app_secret", "open_id", "chat_id")
        )

    def test_set_feishu_control_rejects_incomplete_configuration(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"

            with self.assertRaisesRegex(ValueError, "app_id"):
                set_feishu_control(path, True)

            config = load_config(path)

        self.assertFalse(
            config["providers"]["feishu"]["control_enabled"]
        )

    def test_set_feishu_control_can_be_enabled_and_disabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "providers": {
                            "feishu": {
                                "app_id": "cli_app",
                                "app_secret": "secret_app",
                                "open_id": "ou_owner",
                                "chat_id": "oc_private",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            set_feishu_control(path, True)
            enabled = json.loads(path.read_text(encoding="utf-8"))
            set_feishu_control(path, False)
            disabled = json.loads(path.read_text(encoding="utf-8"))

        self.assertTrue(
            enabled["providers"]["feishu"]["control_enabled"]
        )
        self.assertFalse(
            disabled["providers"]["feishu"]["control_enabled"]
        )

    def test_feishu_controller_is_created_only_when_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "providers": {
                        "feishu": {
                            "control_enabled": True,
                            "app_id": "cli_app",
                            "app_secret": "secret_app",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            controller = build_feishu_controller(path)

        self.assertIsNotNone(controller)
        self.assertEqual(controller.client.app_id, "cli_app")
        self.assertEqual(controller.client.app_secret, "secret_app")

    def test_restart_tray_stops_then_launches_current_executable(self):
        executable = Path("C:/Program Files/Agents-Notify/Agents-Notify.exe")
        launcher = MagicMock()
        states = iter((True, True, False))
        sleeper = MagicMock()

        restart_tray(
            executable,
            stop_signal=lambda: True,
            launcher=launcher,
            sleeper=sleeper,
            tray_running=lambda: next(states),
            frozen=True,
        )

        launcher.assert_called_once_with(
            [str(executable), "--tray"],
            close_fds=True,
            env=self_launch_environment(os.environ, frozen=True),
        )
        self.assertEqual(sleeper.call_count, 2)

    def test_restart_tray_does_not_launch_while_old_instance_remains(self):
        launcher = MagicMock()

        with self.assertRaisesRegex(TimeoutError, "托盘"):
            restart_tray(
                Path("C:/Agents-Notify.exe"),
                stop_signal=lambda: True,
                launcher=launcher,
                sleeper=lambda _seconds: None,
                tray_running=lambda: True,
                frozen=True,
            )

        launcher.assert_not_called()


if __name__ == "__main__":
    unittest.main()
