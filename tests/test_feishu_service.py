import json
import unittest
from types import SimpleNamespace

from agents_notify.feishu_service import FeishuWebSocketService


class FeishuWebSocketServiceTests(unittest.TestCase):
    def test_normalize_message_keeps_controller_shape(self):
        data = SimpleNamespace(
            event=SimpleNamespace(
                sender=SimpleNamespace(
                    sender_id=SimpleNamespace(open_id="ou_owner")
                ),
                message=SimpleNamespace(
                    message_id="om_1",
                    chat_id="oc_private",
                    content=json.dumps({"text": "/notify status"}),
                ),
            )
        )
        message = FeishuWebSocketService.normalize_message(data)

        self.assertEqual(message["message_id"], "om_1")
        self.assertEqual(message["chat_id"], "oc_private")
        self.assertEqual(message["sender"]["id"], "ou_owner")
        self.assertEqual(
            json.loads(message["body"]["content"])["text"],
            "/notify status",
        )
    def test_normalize_message_ignores_events_without_message(self):
        self.assertIsNone(
            FeishuWebSocketService.normalize_message(
                SimpleNamespace(event=SimpleNamespace(message=None))
            )
        )
