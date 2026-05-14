#!/usr/bin/env python
"""CC-Notify Hook: 监听 Claude Code PermissionRequest，飞书推送 + 远程审批."""
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
APPROVE_TIMEOUT = 60  # 等待飞书审批的最长秒数


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


def _lark_send(text):
    subprocess.run(
        [LARK_CLI, "im", "+messages-send", "--as", "bot",
         "--user-id", OPEN_ID, "--text", text, "--msg-type", "text"],
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
    # 超时，删掉 pending 文件
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

    # 生成唯一请求 ID，写入 pending
    req_id = uuid.uuid4().hex[:8]
    os.makedirs(PENDING_DIR, exist_ok=True)
    pending_file = os.path.join(PENDING_DIR, f"{req_id}.json")
    with open(pending_file, "w", encoding="utf-8") as f:
        json.dump({
            "req_id": req_id,
            "tool_name": tool_name,
            "args_summary": args_summary,
            "workspace": workspace,
            "decision": "",
        }, f, ensure_ascii=False)

    # 发送飞书通知，带上审批指令
    text = (
        f"🔐 Claude Code 需要授权\n"
        f"━━━━━━━━━━\n"
        f"工作区: {workspace}\n"
        f"工具: {tool_name}\n"
        f"命令: {args_summary}\n"
        f"━━━━━━━━━━\n"
        f"回复 /approve {req_id} 批准\n"
        f"回复 /deny {req_id} 拒绝"
    )
    _lark_send(text)

    # 等待飞书审批
    decision = wait_for_decision(req_id)

    if decision == "allow":
        print(json.dumps({"decision": "allow"}))
    elif decision == "deny":
        print(json.dumps({"decision": "deny"}))
    else:
        # 超时或无决策 → 回退到终端交互式审批
        print(json.dumps({}))


if __name__ == "__main__":
    main()
