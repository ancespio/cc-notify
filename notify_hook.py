#!/usr/bin/env python
"""CC-Notify Hook: 监听 Claude Code 权限/提问事件，飞书推送通知."""
import json
import os
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_FILE = os.path.join(PROJECT_DIR, "mode.json")
CONFIG_FILE = os.path.join(PROJECT_DIR, "config.json")
LARK_CLI = os.path.join(os.environ.get("APPDATA", ""), "npm", "lark-cli.cmd")


def _load_open_id():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("open_id", "")
    except (FileNotFoundError, json.JSONDecodeError):
        return ""
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
    """返回事件类型: permission / elicitation / stop / unknown."""
    ev = event.get("hook_event_name") or event.get("event") or event.get("hook_event") or ""
    ev = ev.lower()
    if ev in ("permissionrequest", "permission_request"):
        return "permission"
    if ev in ("elicitation", "elicitation_request"):
        return "elicitation"
    if ev in ("stop",):
        return "stop"
    return "unknown"


def extract_tool(event):
    return event.get("tool_name") or event.get("toolName") or "unknown"


def sanitize(s):
    """裁剪到第一个 CMD 特殊字符前，避免被当作命令分隔符."""
    for ch in ("|", "&", ";", "<", ">"):
        idx = s.find(ch)
        if idx > 0:
            return s[:idx] + " ..."
    return s


def extract_summary(event, etype):
    """从事件中提取命令/问题摘要."""
    if etype == "elicitation":
        prompt = event.get("prompt") or event.get("question") or ""
        return sanitize(str(prompt)[:200])
    tool_input = event.get("tool_input") or event.get("arguments") or {}
    if isinstance(tool_input, dict):
        raw = tool_input.get("command") or tool_input.get("description") or ""
        return sanitize(raw if raw else json.dumps(tool_input, ensure_ascii=False))
    return sanitize(str(tool_input))


def _lark_send(open_id, text):
    content = json.dumps({"text": text})
    subprocess.run(
        [LARK_CLI, "im", "+messages-send", "--as", "bot",
         "--user-id", open_id, "--content", content, "--msg-type", "text"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        encoding="utf-8", errors="replace",
        timeout=10, creationflags=CREATE_NO_WINDOW,
    )


def main():
    # 强制 UTF-8 读 stdin，避免 GBK 乱码
    try:
        sys.stdin.reconfigure(encoding="utf-8")
    except Exception:
        pass

    try:
        raw = sys.stdin.read()
        event = json.loads(raw)
    except json.JSONDecodeError:
        print(json.dumps({}))
        return

    etype = event_type(event)
    if etype == "unknown":
        print(json.dumps({}))
        return

    open_id = _load_open_id()
    if not open_id:
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
    ssh = is_ssh_session()
    hint = "请打开 Termius 处理" if ssh else "请到本地终端处理"

    if etype == "stop":
        text = (
            f"✅ Claude Code 本轮完成\n"
            f"━━━━━━━━━━\n"
            f"工作区: {workspace}\n"
            f"━━━━━━━━━━\n"
            f"{hint}"
        )
    elif etype == "elicitation":
        summary = extract_summary(event, etype)
        if len(summary) > 200:
            summary = summary[:197] + "..."
        text = (
            f"💬 Claude Code 向你提问\n"
            f"━━━━━━━━━━\n"
            f"工作区: {workspace}\n"
            f"问题: {summary}\n"
            f"━━━━━━━━━━\n"
            f"{hint}"
        )
    else:
        tool_name = extract_tool(event)
        summary = extract_summary(event, etype)
        if len(summary) > 200:
            summary = summary[:197] + "..."
        text = (
            f"🔐 Claude Code 需要授权\n"
            f"━━━━━━━━━━\n"
            f"工作区: {workspace}\n"
            f"工具: {tool_name}\n"
            f"命令: {summary}\n"
            f"━━━━━━━━━━\n"
            f"{hint}"
        )

    _lark_send(open_id, text)
    print(json.dumps({}))


if __name__ == "__main__":
    main()
