import json
import unittest
from unittest.mock import patch

from agents_notify.config import DEFAULT_BARK_ICON_URL
from agents_notify.events import NormalizedEvent
from agents_notify.providers import (
    BarkProvider,
    BarkServiceError,
    FeishuProvider,
    dispatch,
)


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
    @patch("agents_notify.providers.urlopen", return_value=FakeResponse())
    def test_bark_posts_json_without_key_in_url(self, urlopen_mock):
        provider = BarkProvider(
            {
                "mode": "off",
                "server": "https://api.day.app",
                "device_key": "secret-key",
                "group": "Agents-Notify",
                "url": "chatgpt://",
                "icon": DEFAULT_BARK_ICON_URL,
            }
        )

        self.assertTrue(provider.send(sample_event()))
        request = urlopen_mock.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))

        self.assertEqual(request.full_url, "https://api.day.app/push")
        self.assertEqual(payload["device_key"], "secret-key")
        self.assertEqual(payload["group"], "Agents-Notify")
        self.assertEqual(payload["url"], "chatgpt://")
        self.assertEqual(payload["icon"], DEFAULT_BARK_ICON_URL)
        self.assertIn("Codex", payload["title"])

    def test_bark_missing_key_is_skipped(self):
        self.assertFalse(BarkProvider({"mode": "all"}).send(sample_event()))

    @patch("agents_notify.providers.urlopen")
    def test_bark_error_response_preserves_service_message(self, urlopen):
        response = FakeResponse()
        response.read = lambda: json.dumps(
            {"code": 400, "message": "invalid device key"}
        ).encode("utf-8")
        urlopen.return_value = response
        provider = BarkProvider(
            {
                "server": "https://api.day.app",
                "device_key": "secret-key",
            }
        )

        with self.assertRaisesRegex(
            BarkServiceError, "invalid device key"
        ):
            provider.send(sample_event())


class FeishuProviderTests(unittest.TestCase):
    @patch("agents_notify.providers.FeishuApiClient")
    def test_feishu_uses_http_openapi(self, client_class):
        provider = FeishuProvider(
            {
                "mode": "off",
                "app_id": "cli_app",
                "app_secret": "secret_app",
                "open_id": "ou_test",
            }
        )

        self.assertTrue(provider.send(sample_event()))
        client_class.return_value.send_text.assert_called_once()
        args = client_class.return_value.send_text.call_args.args
        self.assertEqual(args[0], "ou_test")
        self.assertIn("Codex 需要授权", args[1])


class DispatchTests(unittest.TestCase):
    def test_provider_failure_does_not_escape(self):
        class BrokenProvider:
            def send(self, event):
                raise OSError("network down")

        results = dispatch(sample_event(), [BrokenProvider()])

        self.assertEqual(results, [False])


if __name__ == "__main__":
    unittest.main()
