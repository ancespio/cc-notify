#!/usr/bin/env python
"""CC-Notify Hook: 监听 Claude Code PermissionRequest，飞书卡片推送 + 远程审批."""
import json
import os
import subprocess
import sys
import time
import uuid

MODE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mode.json")
PENDING_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pending")
OPEN_ID = "ou_REDACTED"
LARK_CLI = os.path.join(os.environ.get("APPDATA", ""), "npm", "lark-cli.cmd")
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
APPROVE_TIMEOUT = 60


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
    ev = event.get("hook_event_name") or event.get("event") or event.get("hook_event") or ""
    return ev.lower() in ("permissionrequest", "permission_request")


def _lark_send_card(card):
    """发送交互卡片."""
    content = json.dumps(card, ensure_ascii=False)
    subprocess.run(
        [LARK_CLI, "im", "+messages-send", "--as", "bot",
         "--user-id", OPEN_ID, "--content", content, "--msg-type", "interactive"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        encoding="utf-8", errors="replace",
        timeout=10, creationflags=CREATE_NO_WINDOW,
    )


def _lark_send_text(text):
    """发送纯文本消息."""
    content = json.dumps({"text": text})
    subprocess.run(
        [LARK_CLI, "im", "+messages-send", "--as", "bot",
         "--user-id", OPEN_ID, "--content", content, "--msg-type", "text"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        encoding="utf-8", errors="replace",
        timeout=10, creationflags=CREATE_NO_WINDOW,
    )


def wait_for_decision(req_id, timeout=APPROVE_TIMEOUT):
    """轮询 pending 文件，等待 tray 写入决策."""
    decision_file = os.path.join(PENDING_DIR, f"{req_id}.json")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with open(decision_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            os.remove(decision_file)
            return data.get("decision", "")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(1)
    try:
        os.remove(decision_file)
    except FileNotFoundError:
        pass
    return ""


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
    req_id = uuid.uuid4().hex[:8]

    # 写 pending 文件
    os.makedirs(PENDING_DIR, exist_ok=True)
    pending_file = os.path.join(PENDING_DIR, f"{req_id}.json")
    with open(pending_file, "w", encoding="utf-8") as f:
        json.dump({
            "req_id": req_id, "tool_name": tool_name,
            "args_summary": args_summary, "workspace": workspace,
            "decision": "",
        }, f, ensure_ascii=False)

    # 发送交互卡片
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🔐 Claude Code 需要授权"},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "fields": [
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**工作区**\n{workspace}"}},
                    {"is_short": True, "text": {"tag": "lark_md", "content": f"**工具**\n{tool_name}"}},
                ]
            },
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**命令**\n{args_summary[:300]}"}
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": "直接回复本条消息：`允许` / `始终允许` / `拒绝`"}
            },
        ],
    }
    _lark_send_card(card)

    # 等待审批
    decision = wait_for_decision(req_id)

    if decision == "allow":
        print(json.dumps({"decision": "allow"}))
    elif decision == "deny":
        print(json.dumps({"decision": "deny"}))
    else:
        print(json.dumps({}))


if __name__ == "__main__":
    main()
