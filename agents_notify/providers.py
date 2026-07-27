"""Notification providers for Bark and Feishu."""

import json
from typing import Any, Iterable, Mapping
from urllib.request import Request, urlopen

from .events import NormalizedEvent
from .feishu_service import FeishuApiClient


class BarkServiceError(OSError):
    """Bark accepted the HTTP request but rejected the push."""


def format_notification(event: NormalizedEvent) -> tuple[str, str]:
    agent = "Codex" if event.source == "codex" else "Claude Code"
    labels = {
        "permission": ("需要授权", "请求"),
        "question": ("正在提问", "问题"),
        "stop": ("本轮完成", "摘要"),
    }
    action, detail_label = labels[event.kind]
    title = f"{agent} {action}"
    lines = [f"工作区: {event.workspace}"]
    if event.tool_name:
        lines.append(f"工具: {event.tool_name}")
    if event.summary:
        lines.append(f"{detail_label}: {event.summary}")
    return title, "\n".join(lines)


class BarkProvider:
    def __init__(self, config: Mapping[str, Any]):
        self.config = dict(config)

    def send(self, event: NormalizedEvent) -> bool:
        device_key = str(self.config.get("device_key") or "").strip()
        if not device_key:
            return False

        server = str(
            self.config.get("server") or "https://api.day.app"
        ).rstrip("/")
        endpoint = server if server.endswith("/push") else server + "/push"
        title, body = format_notification(event)
        payload = {
            "device_key": device_key,
            "title": title,
            "body": body,
            "group": self.config.get("group") or "Agents-Notify",
        }
        for key in ("sound", "level", "url", "icon"):
            if self.config.get(key):
                payload[key] = self.config[key]

        request = Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urlopen(request, timeout=float(self.config.get("timeout", 8))) as response:
            raw = response.read()
        if not raw:
            return True
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return True
        if data.get("code", 200) != 200:
            message = str(
                data.get("message")
                or data.get("error")
                or f"Bark service returned code {data.get('code')}"
            )
            raise BarkServiceError(message)
        return True


class FeishuProvider:
    def __init__(self, config: Mapping[str, Any]):
        self.config = dict(config)
        self._client: FeishuApiClient | None = None

    def send(self, event: NormalizedEvent) -> bool:
        app_id = str(self.config.get("app_id") or "").strip()
        app_secret = str(self.config.get("app_secret") or "").strip()
        open_id = str(self.config.get("open_id") or "").strip()
        if not app_id or not app_secret or not open_id:
            return False
        title, body = format_notification(event)
        if self._client is None:
            self._client = FeishuApiClient(
                app_id,
                app_secret,
                timeout=float(self.config.get("timeout", 10)),
            )
        self._client.send_text(
            open_id,
            f"{title}\n{'-' * 10}\n{body}",
        )
        return True


def dispatch(
    event: NormalizedEvent, providers: Iterable[Any]
) -> list[bool]:
    results = []
    for provider in providers:
        try:
            results.append(bool(provider.send(event)))
        except Exception:
            results.append(False)
    return results
