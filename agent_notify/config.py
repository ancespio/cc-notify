"""Configuration loading with legacy project compatibility."""

from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any

from filelock import FileLock


CONFIG_VERSION = "1.0.2"
DEFAULT_BARK_URL = "chatgpt://codex"
DEFAULT_AGENT_ICON_URL = (
    "https://raw.githubusercontent.com/ancespio/Agent-Notify/"
    "master/assets/agent-notify.png"
)
DEFAULT_BARK_ICON_URL = DEFAULT_AGENT_ICON_URL
LEGACY_BARK_URLS = {"", "chatgpt://"}
LEGACY_AGENT_ICON_URLS = {
    "",
    (
        "https://raw.githubusercontent.com/ancespio/Agent-Notify/"
        "v1.0.0/assets/agent-notify.png"
    ),
    (
        "https://raw.githubusercontent.com/ancespio/Agent-Notify/"
        "v1.0.1/assets/agent-notify.png"
    ),
    (
        "https://raw.githubusercontent.com/ancespio/Agent-Notify/"
        "v1.0.2/assets/agent-notify.png"
    ),
}
VALID_MODES = {"all", "ssh-only", "off"}


DEFAULT_CONFIG: dict[str, Any] = {
    "config_version": CONFIG_VERSION,
    "providers": {
        "bark": {
            "server": "https://api.day.app",
            "device_key": "",
            "group": "Agent-Notify",
            "sound": "",
            "level": "active",
            "url": DEFAULT_BARK_URL,
            "icon": DEFAULT_AGENT_ICON_URL,
            "mode": "all",
            "timeout": 8,
        },
        "feishu": {
            "control_enabled": False,
            "mode": "off",
            "open_id": "",
            "chat_id": "",
            "lark_cli": "",
            "timeout": 10,
        },
    },
    "events": {
        "permission": True,
        "question": True,
        "stop": True,
    },
    "agents": {
        "codex": True,
        "claude": True,
    },
}


def _backup_config(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = path.with_name(
        f"{path.name}.agent-notify-backup-{stamp}"
    )
    shutil.copy2(path, backup)
    return backup


def _migrate_raw(raw: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    migrated = deepcopy(raw)
    changed = migrated.get("config_version") != CONFIG_VERSION

    providers = migrated.setdefault("providers", {})
    if not isinstance(providers, dict):
        providers = {}
        migrated["providers"] = providers
        changed = True
    bark = providers.setdefault("bark", {})
    if not isinstance(bark, dict):
        bark = {}
        providers["bark"] = bark
        changed = True
    feishu = providers.setdefault("feishu", {})
    if not isinstance(feishu, dict):
        feishu = {}
        providers["feishu"] = feishu
        changed = True

    for name, settings in (("bark", bark), ("feishu", feishu)):
        if "enabled" not in settings:
            continue
        enabled = bool(settings.pop("enabled"))
        if not enabled:
            settings["mode"] = "off"
        elif "mode" not in settings:
            settings["mode"] = "all"
        changed = True

    current_url = str(bark.get("url") or "").strip()
    current_icon = str(bark.get("icon") or "").strip()
    if current_url in LEGACY_BARK_URLS:
        bark["url"] = DEFAULT_BARK_URL
        changed = True
    if current_icon in LEGACY_AGENT_ICON_URLS:
        bark["icon"] = DEFAULT_AGENT_ICON_URL
        changed = True

    if migrated.get("open_id") or migrated.get("chat_id"):
        feishu.setdefault("mode", "all")
        feishu.setdefault("open_id", migrated.get("open_id", ""))
        feishu.setdefault("chat_id", migrated.get("chat_id", ""))
        migrated.pop("open_id", None)
        migrated.pop("chat_id", None)
        changed = True

    migrated["config_version"] = CONFIG_VERSION
    return migrated, changed


def _merge_dict(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
        ):
            _merge_dict(base[key], value)
        else:
            base[key] = value


def normalize_config(raw: Any) -> dict[str, Any]:
    config = deepcopy(DEFAULT_CONFIG)
    if not isinstance(raw, dict):
        return config
    supported = {
        key: value
        for key, value in raw.items()
        if key not in {"open_id", "chat_id"}
    }
    _merge_dict(config, supported)
    bark = config["providers"]["bark"]
    bark.pop("enabled", None)
    bark["url"] = str(bark.get("url") or "").strip() or DEFAULT_BARK_URL
    bark["icon"] = (
        str(bark.get("icon") or "").strip() or DEFAULT_AGENT_ICON_URL
    )
    bark["mode"] = _normalize_mode(bark.get("mode"))
    feishu = config["providers"]["feishu"]
    feishu.pop("enabled", None)
    feishu["mode"] = _normalize_mode(feishu.get("mode"))
    feishu["control_enabled"] = bool(feishu.get("control_enabled", False))

    if raw.get("open_id") and "providers" not in raw:
        feishu["mode"] = "all"
        feishu["open_id"] = raw.get("open_id", "")
        feishu["chat_id"] = raw.get("chat_id", "")
    return config


def _normalize_mode(value: Any) -> str:
    mode = str(value or "all")
    return mode if mode in VALID_MODES else "all"


def _read_raw(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        raw = {}
    return raw if isinstance(raw, dict) else {}


def _write_atomic(path: Path, config: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    handle, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def load_config(
    path: Path, legacy_mode_path: Path | None = None
) -> dict[str, Any]:
    if not path.exists() and legacy_mode_path is None:
        return normalize_config({})
    lock = FileLock(str(path) + ".lock")
    with lock:
        raw = _read_raw(path)
        migrated_raw, needs_migration = _migrate_raw(raw)
        raw = migrated_raw
        providers = raw.get("providers")
        has_provider_modes = (
            isinstance(providers, dict)
            and isinstance(providers.get("bark"), dict)
            and "mode" in providers["bark"]
            and isinstance(providers.get("feishu"), dict)
            and "mode" in providers["feishu"]
        )
        config = normalize_config(raw)
        migrated_mode = False
        if legacy_mode_path is not None and not has_provider_modes:
            try:
                legacy = json.loads(
                    legacy_mode_path.read_text(encoding="utf-8")
                )
                mode = _normalize_mode(legacy.get("mode"))
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                mode = "all"
            config["providers"]["bark"]["mode"] = mode
            config["providers"]["feishu"]["mode"] = mode
            migrated_mode = True
        if path.exists() and (needs_migration or migrated_mode):
            _backup_config(path)
            _write_atomic(path, config)
        return config


def update_config(
    path: Path,
    updater,
    legacy_mode_path: Path | None = None,
) -> dict[str, Any]:
    lock = FileLock(str(path) + ".lock")
    with lock:
        raw = _read_raw(path)
        migrated_raw, needs_migration = _migrate_raw(raw)
        config = normalize_config(migrated_raw)
        if legacy_mode_path is not None:
            providers = raw.get("providers", {})
            if not (
                isinstance(providers, dict)
                and isinstance(providers.get("bark"), dict)
                and "mode" in providers["bark"]
                and isinstance(providers.get("feishu"), dict)
                and "mode" in providers["feishu"]
            ):
                try:
                    legacy = json.loads(
                        legacy_mode_path.read_text(encoding="utf-8")
                    )
                    mode = _normalize_mode(legacy.get("mode"))
                except (
                    FileNotFoundError,
                    json.JSONDecodeError,
                    OSError,
                ):
                    mode = "all"
                config["providers"]["bark"]["mode"] = mode
                config["providers"]["feishu"]["mode"] = mode
        if path.exists() and needs_migration:
            _backup_config(path)
        updater(config)
        config = normalize_config(config)
        _write_atomic(path, config)
        return config


def load_mode(path: Path) -> str:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        mode = raw.get("mode", "all")
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        mode = "all"
    return _normalize_mode(mode)
