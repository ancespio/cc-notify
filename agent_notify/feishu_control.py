"""Feishu remote notification-mode control through lark-cli."""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
from typing import Any, Iterable

from .config import load_config, update_config


CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
MODE_LABELS = {
    "all": "全部通知",
    "ssh-only": "仅 SSH",
    "off": "关闭",
}
RECOMMENDED_LARK_CLI_VERSION = "1.0.53"


@dataclass(frozen=True)
class NotifyCommand:
    targets: tuple[str, ...]
    action: str


@dataclass(frozen=True)
class LarkAuthStatus:
    authenticated: bool
    executable: str
    detail: str


def parse_notify_command(text: str) -> NotifyCommand | None:
    parts = text.strip().lower().split()
    if not parts or parts[0] != "/notify":
        return None
    if len(parts) == 2 and parts[1] in {"on", "ssh", "off"}:
        return NotifyCommand(
            ("bark", "feishu"),
            {"on": "all", "ssh": "ssh-only", "off": "off"}[parts[1]],
        )
    if len(parts) == 2 and parts[1] == "status":
        return NotifyCommand(("bark", "feishu"), "status")
    if (
        len(parts) == 3
        and parts[1] in {"bark", "feishu"}
        and parts[2] in {"on", "ssh", "off", "status"}
    ):
        action = {
            "on": "all",
            "ssh": "ssh-only",
            "off": "off",
            "status": "status",
        }[parts[2]]
        return NotifyCommand((parts[1],), action)
    return None


def _provider_status(name: str, settings: dict[str, Any]) -> str:
    label = "Bark" if name == "bark" else "飞书"
    enabled = "开启" if settings.get("enabled") else "关闭"
    mode = MODE_LABELS.get(settings.get("mode", "all"), "全部通知")
    return f"{label}：{enabled}，模式 {mode}"


def execute_notify_command(config_path: Path, text: str) -> str:
    command = parse_notify_command(text)
    if command is None:
        return (
            "用法：/notify on|ssh|off|status，或 "
            "/notify bark|feishu on|ssh|off|status"
        )
    if command.action != "status":
        enabled = command.action != "off"
        update_config(
            config_path,
            lambda config: [
                config["providers"][name].update(
                    {
                        "enabled": enabled,
                        "mode": command.action,
                    }
                )
                for name in command.targets
            ],
        )
    config = load_config(config_path)
    lines = [
        _provider_status(name, config["providers"][name])
        for name in command.targets
    ]
    if set(command.targets) == {"bark", "feishu"}:
        control = config["providers"]["feishu"].get(
            "control_enabled", False
        )
        lines.append(f"远程控制：{'开启' if control else '关闭'}")
    return "\n".join(lines)


class LarkCliClient:
    def __init__(
        self,
        executable: str,
        timeout: float = 10,
        runner=subprocess.run,
    ):
        self.executable = executable or "lark-cli"
        self.timeout = timeout
        self.runner = runner

    def _run(self, *args: str, timeout: float | None = None) -> dict:
        result = self.runner(
            [self.executable, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout or self.timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            raise OSError(result.stderr.strip() or "lark-cli failed")
        if not result.stdout.strip():
            return {}
        return json.loads(result.stdout)

    def auth_status(self) -> LarkAuthStatus:
        try:
            result = self.runner(
                [self.executable, "auth", "status"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception as exc:
            return LarkAuthStatus(False, self.executable, str(exc))
        detail = (
            result.stdout.strip()
            if result.returncode == 0
            else result.stderr.strip() or result.stdout.strip()
        )
        return LarkAuthStatus(
            result.returncode == 0,
            self.executable,
            detail,
        )

    @staticmethod
    def _find_open_id(value: Any) -> str:
        if isinstance(value, dict):
            candidate = value.get("open_id")
            if candidate:
                return str(candidate)
            for nested in value.values():
                found = LarkCliClient._find_open_id(nested)
                if found:
                    return found
        elif isinstance(value, list):
            for nested in value:
                found = LarkCliClient._find_open_id(nested)
                if found:
                    return found
        return ""

    def current_open_id(self) -> str:
        response = self._run(
            "api",
            "GET",
            "/open-apis/authen/v1/user_info",
            "--as",
            "user",
            "--format",
            "json",
        )
        open_id = self._find_open_id(response)
        if not open_id:
            raise OSError("飞书当前用户信息未返回 open_id。")
        return open_id

    def setup_command(self, step: str) -> list[str]:
        executable = self.executable.replace("'", "''")
        commands = {
            "install": "npx @larksuite/cli@latest install",
            "config": f"& '{executable}' config init",
            "login": f"& '{executable}' auth login --recommend",
            "update": f"& '{executable}' update",
        }
        if step not in commands:
            raise ValueError(f"未知的 lark-cli 配置步骤：{step}")
        command = commands[step]
        script = (
            f"{command}; $exitCode = $LASTEXITCODE; "
            "Write-Host ''; "
            "Write-Host '完成后按 Enter 返回 Agent-Notify。'; "
            "Read-Host | Out-Null; exit $exitCode"
        )
        return [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ]

    def version(self) -> str:
        result = self.runner(
            [self.executable, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            raise OSError(result.stderr.strip() or "lark-cli version failed")
        match = re.search(r"(\d+\.\d+\.\d+)", result.stdout)
        if not match:
            raise OSError("无法识别 lark-cli 版本。")
        return match.group(1)

    def connect(self, open_id: str) -> str:
        content = json.dumps(
            {"text": "Agent-Notify 连接成功"},
            ensure_ascii=False,
        )
        response = self._run(
            "im",
            "+messages-send",
            "--as",
            "bot",
            "--user-id",
            open_id,
            "--content",
            content,
            "--msg-type",
            "text",
            timeout=15,
        )
        return str(response.get("data", {}).get("chat_id") or "")

    def fetch_messages(self, chat_id: str) -> list[dict[str, Any]]:
        params = json.dumps(
            {
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": 20,
                "sort_type": "ByCreateTimeDesc",
            }
        )
        response = self._run(
            "api",
            "GET",
            "/open-apis/im/v1/messages",
            "--params",
            params,
            "--as",
            "bot",
        )
        return list(response.get("data", {}).get("items", []))

    def reply(self, message_id: str, text: str) -> None:
        content = json.dumps({"text": text}, ensure_ascii=False)
        self._run(
            "im",
            "+messages-reply",
            "--as",
            "bot",
            "--message-id",
            message_id,
            "--content",
            content,
            "--msg-type",
            "text",
        )


class FeishuController:
    def __init__(
        self,
        config_path: Path,
        client: LarkCliClient,
        stop_event: threading.Event | None = None,
    ):
        self.config_path = config_path
        self.client = client
        self.stop_event = stop_event or threading.Event()
        self._processed: set[str] = set()

    @staticmethod
    def _message_text(message: dict[str, Any]) -> str:
        content = message.get("body", {}).get("content", "")
        try:
            parsed = json.loads(content)
            return str(parsed.get("text") or "")
        except (json.JSONDecodeError, TypeError):
            return str(content or "")

    def process_messages(
        self,
        messages: Iterable[dict[str, Any]],
        initial: bool = False,
    ) -> None:
        config = load_config(self.config_path)
        feishu = config["providers"]["feishu"]
        open_id = str(feishu.get("open_id") or "")
        chat_id = str(feishu.get("chat_id") or "")
        for message in messages:
            message_id = str(message.get("message_id") or "")
            if not message_id or message_id in self._processed:
                continue
            self._processed.add(message_id)
            if len(self._processed) > 500:
                self._processed = {message_id}
            if initial:
                continue
            sender = str(message.get("sender", {}).get("id") or "")
            if sender != open_id or str(message.get("chat_id") or "") != chat_id:
                continue
            text = self._message_text(message)
            if not text.strip().lower().startswith("/notify"):
                continue
            reply = execute_notify_command(self.config_path, text)
            try:
                self.client.reply(message_id, reply)
            except Exception:
                pass

    def run(self) -> None:
        initialized = False
        delay = 1.0
        while not self.stop_event.is_set():
            config = load_config(self.config_path)
            settings = config["providers"]["feishu"]
            if not settings.get("control_enabled"):
                return
            chat_id = str(settings.get("chat_id") or "")
            if not chat_id:
                return
            try:
                messages = self.client.fetch_messages(chat_id)
                self.process_messages(messages, initial=not initialized)
                initialized = True
                delay = 1.0
            except Exception:
                delay = min(delay * 2, 15.0)
            self.stop_event.wait(delay)
