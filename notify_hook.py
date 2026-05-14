#!/usr/bin/env python
"""CC-Notify Hook: 监听 Claude Code 权限/提问事件，飞书推送通知."""
import json
import os
import subprocess
import sys

MODE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mode.json")
OPEN_ID = "ou_REDACTED"
LARK_CLI = os.path.join(os.environ.get("APPDATA", ""), "npm", "lark-cli.cmd")
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def load_mode():
    try:
        with open(MODE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("mode", "ssh-only")
    except (FileNotFoundError, json.JSONDecodeError):
        return "ssh-only"


def is_ssh_session():
    return bool(os.environ.get("SSH_TTY") or os.environ.get("SSH_CONNECTION"))


def extract_workspace(event):
    return os.path.basename(event.get("cwd", "") or os.getcwd())


def event_type(event):
    """返回事件类型: permission / elicitation / unknown."""
    ev = event.get("hook_event_name") or event.get("event") or event.get("hook_event") or ""
    ev = ev.lower()
    if ev in ("permissionrequest", "permission_request"):
        return "permission"
    if ev in ("elicitation", "elicitation_request"):
        return "elicitation"
    return "unknown"


def extract_tool(event):
    return event.get("tool_name") or event.get("toolName") or "unknown"


def extract_summary(event, etype):
    """从事件中提取命令/问题摘要."""
    if etype == "elicitation":
        prompt = event.get("prompt") or event.get("question") or ""
        return str(prompt)[:200]
    tool_input = event.get("tool_input") or event.get("arguments") or {}
    if isinstance(tool_input, dict):
        return (tool_input.get("command") or tool_input.get("description") or
                json.dumps(tool_input, ensure_ascii=False))
    return str(tool_input)


def _lark_send(text):
    content = json.dumps({"text": text})
    subprocess.run(
        [LARK_CLI, "im", "+messages-send", "--as", "bot",
         "--user-id", OPEN_ID, "--content", content, "--msg-type", "text"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        encoding="utf-8", errors="replace",
        timeout=10, creationflags=CREATE_NO_WINDOW,
    )


def main():
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({}))
        return

    etype = event_type(event)
    if etype == "unknown":
        print(json.dumps({}))
        return

    mode = load_mode()
    if mode == "off":
        print(json.dumps({}))
        return
    if mode == "ssh-only" and not is_ssh_session():
        print(json.dumps({}))
        return

    workspace = extract_workspace(event)
    tool_name = extract_tool(event)
    summary = extract_summary(event, etype)
    if len(summary) > 200:
        summary = summary[:197] + "..."

    if etype == "elicitation":
        text = (
            f"💬 Claude Code 向你提问\n"
            f"━━━━━━━━━━\n"
            f"工作区: {workspace}\n"
            f"问题: {summary}\n"
            f"━━━━━━━━━━\n"
            f"请打开 Termius 回复"
        )
    else:
        text = (
            f"🔐 Claude Code 需要授权\n"
            f"━━━━━━━━━━\n"
            f"工作区: {workspace}\n"
            f"工具: {tool_name}\n"
            f"命令: {summary}\n"
            f"━━━━━━━━━━\n"
            f"请打开 Termius 批准或拒绝"
        )

    _lark_send(text)
    print(json.dumps({}))


if __name__ == "__main__":
    main()
