"""Idempotent Codex and Claude Code hook installation helpers."""

import json
from pathlib import Path
from typing import Any


QUESTION_MARKER_START = "<!-- agent-notify:question-hook:start -->"
QUESTION_MARKER_END = "<!-- agent-notify:question-hook:end -->"
LEGACY_PROJECT_FRAGMENT = "cc" + "-notify"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _command(python_executable: str, script_path: Path) -> str:
    return f'"{python_executable}" "{script_path}"'


def _executable_command(executable: Path, *args: str) -> str:
    suffix = "".join(f" {arg}" for arg in args)
    return f'"{executable}"{suffix}'


def _windows_command(command: str) -> str:
    return f"& {command}"


def _is_agent_notify_group(group: Any) -> bool:
    if not isinstance(group, dict):
        return False
    for hook in group.get("hooks", []):
        if not isinstance(hook, dict):
            continue
        if str(hook.get("statusMessage", "")).startswith("Agent-Notify"):
            return True
        command = str(hook.get("command", "")).replace("\\", "/").lower()
        if "notify_hook.py" in command and (
            LEGACY_PROJECT_FRAGMENT in command or "agent-notify" in command
        ):
            return True
    return False


def _merge_group(
    groups: Any, new_group: dict[str, Any]
) -> list[dict[str, Any]]:
    existing = groups if isinstance(groups, list) else []
    kept = [group for group in existing if not _is_agent_notify_group(group)]
    kept.append(new_group)
    return kept


def _codex_group(
    event_name: str, script_path: Path, python_executable: str
) -> dict[str, Any]:
    command = _command(python_executable, script_path)
    group: dict[str, Any] = {
        "hooks": [
            {
                "type": "command",
                "command": command,
                "commandWindows": _windows_command(command),
                "timeout": 15,
                "statusMessage": f"Agent-Notify: sending {event_name} alert",
            }
        ]
    }
    if event_name == "PermissionRequest":
        group["matcher"] = "*"
    elif event_name == "PreToolUse":
        group["matcher"] = "^request_user_input$"
    return group


def _codex_executable_group(
    event_name: str, hook_executable: Path
) -> dict[str, Any]:
    command = _executable_command(hook_executable, "--hook")
    group: dict[str, Any] = {
        "hooks": [
            {
                "type": "command",
                "command": command,
                "commandWindows": _windows_command(command),
                "timeout": 15,
                "statusMessage": f"Agent-Notify: sending {event_name} alert",
            }
        ]
    }
    if event_name == "PermissionRequest":
        group["matcher"] = "*"
    elif event_name == "PreToolUse":
        group["matcher"] = "^request_user_input$"
    return group


def _claude_group(
    event_name: str, script_path: Path, python_executable: str
) -> dict[str, Any]:
    group: dict[str, Any] = {
        "hooks": [
            {
                "type": "command",
                "command": python_executable,
                "args": [str(script_path)],
                "timeout": 15,
                "statusMessage": f"Agent-Notify: sending {event_name} alert",
            }
        ]
    }
    if event_name == "PreToolUse":
        group["matcher"] = "AskUserQuestion"
    elif event_name != "Stop":
        group["matcher"] = "*"
    return group


def _claude_executable_group(
    event_name: str, hook_executable: Path
) -> dict[str, Any]:
    group: dict[str, Any] = {
        "hooks": [
            {
                "type": "command",
                "command": str(hook_executable),
                "args": ["--hook"],
                "timeout": 15,
                "statusMessage": f"Agent-Notify: sending {event_name} alert",
            }
        ]
    }
    if event_name == "PreToolUse":
        group["matcher"] = "AskUserQuestion"
    elif event_name != "Stop":
        group["matcher"] = "*"
    return group


def install_codex_hooks(
    path: Path, script_path: Path, python_executable: str
) -> None:
    data = _read_json(path)
    hooks = data.setdefault("hooks", {})
    for event_name in ("PermissionRequest", "PreToolUse", "Stop"):
        hooks[event_name] = _merge_group(
            hooks.get(event_name),
            _codex_group(event_name, script_path, python_executable),
        )
    _write_json(path, data)


def install_codex_executable_hooks(
    path: Path, hook_executable: Path
) -> None:
    data = _read_json(path)
    hooks = data.setdefault("hooks", {})
    for event_name in ("PermissionRequest", "PreToolUse", "Stop"):
        hooks[event_name] = _merge_group(
            hooks.get(event_name),
            _codex_executable_group(event_name, hook_executable),
        )
    _write_json(path, data)


def install_claude_hooks(
    path: Path, script_path: Path, python_executable: str
) -> None:
    data = _read_json(path)
    hooks = data.setdefault("hooks", {})
    for event_name in (
        "PermissionRequest",
        "PreToolUse",
        "Elicitation",
        "Stop",
    ):
        hooks[event_name] = _merge_group(
            hooks.get(event_name),
            _claude_group(event_name, script_path, python_executable),
        )
    _write_json(path, data)


def install_claude_executable_hooks(
    path: Path, hook_executable: Path
) -> None:
    data = _read_json(path)
    hooks = data.setdefault("hooks", {})
    for event_name in (
        "PermissionRequest",
        "PreToolUse",
        "Elicitation",
        "Stop",
    ):
        hooks[event_name] = _merge_group(
            hooks.get(event_name),
            _claude_executable_group(event_name, hook_executable),
        )
    _write_json(path, data)


def _replace_instruction_block(path: Path, block: str | None) -> None:
    try:
        current = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        current = ""

    start = current.find(QUESTION_MARKER_START)
    end = current.find(QUESTION_MARKER_END)
    if start >= 0 and end >= start:
        end += len(QUESTION_MARKER_END)
        current = current[:start].rstrip() + current[end:]

    updated = current.rstrip()
    if block:
        if updated:
            updated += "\n\n"
        updated += block
    if updated:
        updated += "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(updated, encoding="utf-8")


def _remove_agent_notify_groups(data: dict[str, Any]) -> None:
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return
    for event_name in list(hooks):
        groups = hooks.get(event_name)
        if not isinstance(groups, list):
            continue
        kept = [group for group in groups if not _is_agent_notify_group(group)]
        if kept:
            hooks[event_name] = kept
        else:
            del hooks[event_name]
    if not hooks:
        data.pop("hooks", None)


def remove_codex_hooks(path: Path) -> None:
    data = _read_json(path)
    _remove_agent_notify_groups(data)
    _write_json(path, data)


def remove_claude_hooks(path: Path) -> None:
    data = _read_json(path)
    _remove_agent_notify_groups(data)
    _write_json(path, data)


def remove_agent_instructions(path: Path) -> None:
    _replace_instruction_block(path, None)
