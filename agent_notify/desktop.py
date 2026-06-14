"""Windows desktop installation and Bark configuration services."""

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
from typing import Mapping, Optional

from .config import (
    DEFAULT_AGENT_ICON_URL,
    DEFAULT_BARK_URL,
    load_config,
    update_config,
)
from .events import NormalizedEvent
from .installer import (
    install_claude_executable_hooks,
    install_codex_executable_hooks,
    remove_agent_instructions,
    remove_claude_hooks,
    remove_codex_hooks,
)
from .icon_validation import validate_icon_url
from .providers import BarkProvider, FeishuProvider
from .resources import resource_path


class BarkTestError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


def app_data_dir(environ: Optional[Mapping[str, str]] = None) -> Path:
    values = environ or os.environ
    base = values.get("APPDATA")
    if base:
        return Path(base) / "Agent-Notify"
    return Path.home() / ".agent-notify"


def user_home(environ: Optional[Mapping[str, str]] = None) -> Path:
    values = environ or os.environ
    override = values.get("AGENT_NOTIFY_HOME")
    return Path(override) if override else Path.home()


def backup_file(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = path.with_name(
        f"{path.name}.agent-notify-backup-{stamp}"
    )
    shutil.copy2(path, backup)
    return backup


def save_bark_settings(
    path: Path,
    device_key: str,
    server: str,
    url: str = DEFAULT_BARK_URL,
    icon: str = DEFAULT_AGENT_ICON_URL,
    codex: bool = True,
    claude: bool = True,
) -> dict:
    return update_config(
        path,
        lambda config: (
            config["providers"]["bark"].update(
                {
                    "device_key": device_key.strip(),
                    "server": server.strip().rstrip("/")
                    or "https://api.day.app",
                    "url": url.strip() or DEFAULT_BARK_URL,
                    "icon": icon.strip() or DEFAULT_AGENT_ICON_URL,
                    "mode": "all",
                }
            ),
            config["agents"].update(
                {"codex": bool(codex), "claude": bool(claude)}
            ),
        ),
    )


def save_provider_settings(
    path: Path,
    bark: Mapping[str, object],
    feishu: Mapping[str, object],
    agents: Mapping[str, object],
) -> dict:
    def apply(config: dict) -> None:
        bark_settings = config["providers"]["bark"]
        bark_settings.update(
            {
                "device_key": str(bark.get("device_key") or "").strip(),
                "server": str(
                    bark.get("server") or "https://api.day.app"
                ).rstrip("/"),
                "url": str(bark.get("url") or "").strip()
                or DEFAULT_BARK_URL,
                "icon": str(bark.get("icon") or "").strip()
                or DEFAULT_AGENT_ICON_URL,
                "mode": str(bark.get("mode") or "all"),
            }
        )
        feishu_settings = config["providers"]["feishu"]
        feishu_settings.update(
            {
                "control_enabled": bool(
                    feishu.get("control_enabled")
                ),
                "mode": str(feishu.get("mode") or "all"),
                "open_id": str(feishu.get("open_id") or "").strip(),
                "chat_id": str(feishu.get("chat_id") or "").strip(),
                "lark_cli": str(feishu.get("lark_cli") or "").strip(),
            }
        )
        config["agents"].update(
            {
                "codex": bool(agents.get("codex")),
                "claude": bool(agents.get("claude")),
            }
        )

    return update_config(path, apply)


def connect_feishu(config_path: Path, open_id: str, client) -> str:
    value = open_id.strip()
    if not value:
        raise ValueError("请填写飞书 open_id。")
    chat_id = str(client.connect(value) or "").strip()
    if not chat_id:
        raise OSError("飞书未返回 chat_id。")
    update_config(
        config_path,
        lambda config: config["providers"]["feishu"].update(
            {"open_id": value, "chat_id": chat_id}
        ),
    )
    return chat_id


def install_hooks(
    home: Path,
    hook_executable: Path,
    codex: bool,
    claude: bool,
) -> list[Path]:
    changed = []
    if codex:
        hooks_path = home / ".codex" / "hooks.json"
        agents_path = home / ".codex" / "AGENTS.md"
        backup_file(hooks_path)
        install_codex_executable_hooks(hooks_path, hook_executable)
        changed.append(hooks_path)
        if agents_path.exists():
            backup_file(agents_path)
            remove_agent_instructions(agents_path)
            changed.append(agents_path)
    if claude:
        settings_path = home / ".claude" / "settings.json"
        backup_file(settings_path)
        install_claude_executable_hooks(settings_path, hook_executable)
        changed.append(settings_path)
    return changed


def sync_hooks(
    home: Path,
    hook_executable: Path,
    codex: bool,
    claude: bool,
) -> list[Path]:
    changed = []
    codex_hooks = home / ".codex" / "hooks.json"
    codex_agents = home / ".codex" / "AGENTS.md"
    claude_settings = home / ".claude" / "settings.json"

    if codex:
        backup_file(codex_hooks)
        install_codex_executable_hooks(codex_hooks, hook_executable)
        changed.append(codex_hooks)
    elif codex_hooks.exists():
        backup_file(codex_hooks)
        remove_codex_hooks(codex_hooks)
        changed.append(codex_hooks)

    if codex_agents.exists():
        backup_file(codex_agents)
        remove_agent_instructions(codex_agents)
        changed.append(codex_agents)

    if claude:
        backup_file(claude_settings)
        install_claude_executable_hooks(claude_settings, hook_executable)
        changed.append(claude_settings)
    elif claude_settings.exists():
        backup_file(claude_settings)
        remove_claude_hooks(claude_settings)
        changed.append(claude_settings)

    return changed


def remove_hooks(home: Path) -> list[Path]:
    changed = []
    codex_hooks = home / ".codex" / "hooks.json"
    codex_agents = home / ".codex" / "AGENTS.md"
    claude_settings = home / ".claude" / "settings.json"
    for path, remover in (
        (codex_hooks, remove_codex_hooks),
        (codex_agents, remove_agent_instructions),
        (claude_settings, remove_claude_hooks),
    ):
        if not path.exists():
            continue
        backup_file(path)
        remover(path)
        changed.append(path)
    return changed


def send_test_notification(config_path: Path) -> bool:
    config = load_config(config_path)
    bark = config["providers"]["bark"]
    if not str(bark.get("device_key") or "").strip():
        raise BarkTestError(
            "configuration", "请先配置有效的 Bark Key。"
        )
    if not str(bark.get("server") or "").strip():
        raise BarkTestError(
            "configuration", "请先配置 Bark 服务器地址。"
        )
    icon_url = str(bark.get("icon") or "").strip()
    expected_sha256 = None
    if icon_url == DEFAULT_AGENT_ICON_URL:
        icon_path = resource_path("assets/agent-notify.png")
        if icon_path.is_file():
            import hashlib

            expected_sha256 = hashlib.sha256(
                icon_path.read_bytes()
            ).hexdigest()
    if icon_url:
        try:
            validate_icon_url(
                icon_url,
                expected_sha256=expected_sha256,
            )
        except Exception as exc:
            raise BarkTestError(
                "icon", f"通知图标校验失败：{exc}"
            ) from exc
    provider = BarkProvider(bark)
    try:
        sent = provider.send(
            NormalizedEvent(
                source="codex",
                kind="stop",
                workspace="Agent-Notify",
                summary="Bark 测试通知发送成功。",
            )
        )
    except Exception as exc:
        raise BarkTestError(
            "push", f"Bark 推送请求失败：{exc}"
        ) from exc
    if not sent:
        raise BarkTestError(
            "push", "Bark 服务未返回成功状态，请检查 Key 和服务器。"
        )
    return True


def send_feishu_test_notification(config_path: Path) -> bool:
    config = load_config(config_path)
    feishu = config["providers"]["feishu"]
    if not str(feishu.get("open_id") or "").strip():
        raise ValueError("请先配置飞书 open_id。")
    if not str(feishu.get("lark_cli") or "").strip():
        raise ValueError("请先配置 lark-cli 路径。")
    provider = FeishuProvider(feishu)
    sent = provider.send(
        NormalizedEvent(
            source="codex",
            kind="stop",
            workspace="Agent-Notify",
            summary="飞书测试通知发送成功。",
        )
    )
    if not sent:
        raise OSError("飞书测试消息发送失败，请检查登录和身份配置。")
    return True


def apply_install_request(
    request_path: Path,
    config_path: Path,
    home: Path,
    hook_executable: Path,
) -> list[Path]:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    device_key = str(request.get("device_key") or "").strip()
    if not device_key:
        raise ValueError("Bark device key is required.")
    save_bark_settings(
        config_path,
        device_key,
        str(request.get("server") or "https://api.day.app"),
        str(request.get("url") or DEFAULT_BARK_URL),
        str(request.get("icon") or DEFAULT_AGENT_ICON_URL),
        bool(request.get("codex")),
        bool(request.get("claude")),
    )
    return sync_hooks(
        home,
        hook_executable,
        bool(request.get("codex")),
        bool(request.get("claude")),
    )
