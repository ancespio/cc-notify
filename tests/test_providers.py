import json
import unittest
from unittest.mock import patch

from agent_notify.config import DEFAULT_BARK_ICON_URL
from agent_notify.events import NormalizedEvent
from agent_notify.providers import BarkProvider, FeishuProvider, dispatch


def sample_event(kind="permission"):
    return NormalizedEvent(
        source="codex",
        kind=kind,
        workspace="demo",
        tool_name="shell_command",
        summary="git status",
    )


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return b'{"code": 200}'


class BarkProviderTests(unittest.TestCase):
    @patch("agent_notify.providers.urlopen", return_value=FakeResponse())
    def test_bark_posts_json_without_key_in_url(self, urlopen_mock):
        provider = BarkProvider(
            {
                "enabled": True,
                "server": "https://api.day.app",
                "device_key": "secret-key",
                "group": "Agent-Notify",
                "url": "chatgpt://",
                "icon": DEFAULT_BARK_ICON_URL,
            }
        )

        self.assertTrue(provider.send(sample_event()))
        request = urlopen_mock.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))

        self.assertEqual(request.full_url, "https://api.day.app/push")
        self.assertEqual(payload["device_key"], "secret-key")
        self.assertEqual(payload["group"], "Agent-Notify")
        self.assertEqual(payload["url"], "chatgpt://")
        self.assertEqual(payload["icon"], DEFAULT_BARK_ICON_URL)
        self.assertIn("Codex", payload["title"])

    def test_bark_disabled_or_missing_key_is_skipped(self):
        self.assertFalse(BarkProvider({"enabled": False}).send(sample_event()))
        self.assertFalse(BarkProvider({"enabled": True}).send(sample_event()))


class FeishuProviderTests(unittest.TestCase):
    @patch("agent_notify.providers.subprocess.run")
    def test_feishu_uses_argument_list(self, run_mock):
        run_mock.return_value.returncode = 0
        provider = FeishuProvider(
            {
                "enabled": True,
                "open_id": "ou_test",
                "lark_cli": "lark-cli",
            }
        )

        self.assertTrue(provider.send(sample_event()))
        command = run_mock.call_args.args[0]
        self.assertEqual(command[0], "lark-cli")
        self.assertIn("ou_test", command)


class DispatchTests(unittest.TestCase):
    def test_provider_failure_does_not_escape(self):
        class BrokenProvider:
            def send(self, event):
                raise OSError("network down")

        results = dispatch(sample_event(), [BrokenProvider()])

        self.assertEqual(results, [False])


if __name__ == "__main__":
    unittest.main()
