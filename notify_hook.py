#!/usr/bin/env python
"""CC-Notify Hook: 监听 Claude Code PermissionRequest，通过飞书推送通知."""
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
    cwd = event.get("cwd", "") or os.getcwd()
    return os.path.basename(cwd)


def is_permission_request(event):
    """兼容 Claude Code 不同版本的 event 字段格式."""
    ev = event.get("hook_event_name") or event.get("event") or event.get("hook_event") or ""
    return ev.lower() in ("permissionrequest", "permission_request")


def send_feishu(tool_name, args_summary, workspace):
    text = (
        f"<at user_id=\"{OPEN_ID}\">@义人</at>\n"
        f"🔐 Claude Code 需要授权\n"
        f"━━━━━━━━━━\n"
        f"工作区: {workspace}\n"
        f"工具: {tool_name}\n"
        f"命令: {args_summary}\n"
        f"━━━━━━━━━━\n"
        f"请打开 Termius 批准或拒绝"
    )
    content = json.dumps({"text": text})
    subprocess.run(
        [
            LARK_CLI, "im", "+messages-send",
            "--as", "bot",
            "--user-id", OPEN_ID,
            "--content", content,
            "--msg-type", "text",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
        creationflags=CREATE_NO_WINDOW,
    )


def main():
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({}))
        return

    if not is_permission_request(event):
        print(json.dumps({}))
        return

    mode = load_mode()
    if mode == "off":
        print(json.dumps({}))
        return
    if mode == "ssh-only" and not is_ssh_session():
        print(json.dumps({}))
        return

    tool_name = event.get("tool_name") or event.get("toolName") or "unknown"
    tool_input = event.get("tool_input") or event.get("arguments") or {}
    if isinstance(tool_input, dict):
        args_summary = tool_input.get("command") or tool_input.get("description") or json.dumps(tool_input, ensure_ascii=False)
    else:
        args_summary = str(tool_input)
    if len(args_summary) > 200:
        args_summary = args_summary[:197] + "..."

    workspace = extract_workspace(event)
    send_feishu(tool_name, args_summary, workspace)

    # 空决策 = 交由终端交互式审批
    print(json.dumps({}))


if __name__ == "__main__":
    main()
