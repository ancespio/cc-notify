import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from agent_notify.config import load_config, update_config
from agent_notify.feishu_control import (
    FeishuController,
    execute_notify_command,
    parse_notify_command,
)


class NotifyCommandTests(unittest.TestCase):
    def test_legacy_command_targets_both_channels(self):
        command = parse_notify_command("/notify ssh")

        self.assertEqual(command.targets, ("bark", "feishu"))
        self.assertEqual(command.action, "ssh-only")

    def test_channel_command_targets_one_channel(self):
        command = parse_notify_command("/notify bark off")

        self.assertEqual(command.targets, ("bark",))
        self.assertEqual(command.action, "off")

    def test_status_commands_are_supported(self):
        self.assertEqual(
            parse_notify_command("/notify status").action, "status"
        )
        self.assertEqual(
            parse_notify_command("/notify feishu status").targets,
            ("feishu",),
        )

    def test_unknown_command_returns_none(self):
        self.assertIsNone(parse_notify_command("/notify maybe"))
        self.assertIsNone(parse_notify_command("hello"))

    def test_command_changes_modes_without_enabling_channels(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            update_config(
                path,
                lambda config: config["providers"]["bark"].update(
                    {"enabled": False}
                ),
            )

            reply = execute_notify_command(path, "/notify on")
            config = load_config(path)

        self.assertIn("Bark", reply)
        self.assertFalse(config["providers"]["bark"]["enabled"])
        self.assertEqual(config["providers"]["bark"]["mode"], "all")
        self.assertEqual(config["providers"]["feishu"]["mode"], "all")

    def test_status_reports_both_channels_and_control(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            update_config(
                path,
                lambda config: config["providers"]["feishu"].update(
                    {"control_enabled": True, "mode": "off"}
                ),
            )

            reply = execute_notify_command(path, "/notify status")

        self.assertIn("Bark", reply)
        self.assertIn("飞书", reply)
        self.assertIn("远程控制：开启", reply)


class FeishuControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"
        update_config(
            self.config_path,
            lambda config: config["providers"]["feishu"].update(
                {
                    "control_enabled": True,
                    "open_id": "ou_owner",
                    "chat_id": "oc_private",
                }
            ),
        )
        self.client = MagicMock()
        self.controller = FeishuController(
            self.config_path,
            self.client,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def message(
        text="/notify bark off",
        message_id="m1",
        sender="ou_owner",
        chat_id="oc_private",
    ):
        return {
            "message_id": message_id,
            "chat_id": chat_id,
            "sender": {"id": sender},
            "body": {"content": json.dumps({"text": text})},
        }

    def test_initial_messages_only_seed_cursor(self):
        self.controller.process_messages([self.message()], initial=True)

        config = load_config(self.config_path)
        self.assertEqual(config["providers"]["bark"]["mode"], "all")
        self.client.reply.assert_not_called()

    def test_authorized_new_command_changes_mode_and_replies(self):
        self.controller.process_messages([self.message()], initial=True)
        self.controller.process_messages(
            [self.message(message_id="m2")],
            initial=False,
        )

        config = load_config(self.config_path)
        self.assertEqual(config["providers"]["bark"]["mode"], "off")
        self.client.reply.assert_called_once()

    def test_wrong_sender_or_chat_is_ignored(self):
        self.controller.process_messages(
            [
                self.message(sender="ou_other"),
                self.message(message_id="m2", chat_id="oc_other"),
            ],
            initial=False,
        )

        config = load_config(self.config_path)
        self.assertEqual(config["providers"]["bark"]["mode"], "all")
        self.client.reply.assert_not_called()

    def test_duplicate_message_is_ignored(self):
        message = self.message()

        self.controller.process_messages([message], initial=False)
        self.controller.process_messages([message], initial=False)

        self.client.reply.assert_called_once()
