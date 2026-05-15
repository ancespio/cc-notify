#!/usr/bin/env python
"""CC-Notify 托盘应用：Windows 常驻托盘图标 + 飞书事件订阅."""
import json
import os
import subprocess
import sys
import threading
import time

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

from PIL import Image, ImageDraw

try:
    import pystray
except ImportError:
    print("请先安装依赖: pip install pystray Pillow")
    sys.exit(1)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MODE_FILE = os.path.join(PROJECT_DIR, "mode.json")
CONFIG_FILE = os.path.join(PROJECT_DIR, "config.json")
LARK_CLI = os.path.join(os.environ.get("APPDATA", ""), "npm", "lark-cli.cmd")


def _get_open_id():
    cfg = load_config()
    return cfg.get("open_id", "")

MODES = {
    "all": ("全部开启", (76, 175, 80)),
    "ssh-only": ("仅SSH会话", (255, 193, 7)),
    "off": ("关闭", (158, 158, 158)),
}


# ── 状态管理 ──────────────────────────────────────────────

def load_mode():
    try:
        with open(MODE_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("mode", "ssh-only")
    except (FileNotFoundError, json.JSONDecodeError):
        return "ssh-only"


def save_mode(mode):
    with open(MODE_FILE, "w", encoding="utf-8") as f:
        json.dump({"mode": mode}, f, ensure_ascii=False)


def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False)


# ── 飞书 API ──────────────────────────────────────────────

def _lark(*args, timeout=10):
    try:
        result = subprocess.run(
            [LARK_CLI] + list(args),
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            return False, None
        data = json.loads(result.stdout) if result.stdout.strip() else {}
        return True, data
    except Exception:
        return False, None


def send_reply(message_id, text):
    open_id = _get_open_id()
    if not open_id:
        return
    _lark(
        "im", "+messages-reply", "--as", "bot",
        "--message-id", message_id,
        "--text", text, "--msg-type", "text",
        timeout=10,
    )


# ── 图标 ──────────────────────────────────────────────────

def make_icon(mode):
    color = MODES.get(mode, MODES["ssh-only"])[1]
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([8, 8, 56, 56], fill=color, outline=(255, 255, 255, 180), width=2)
    letter = {"all": "A", "ssh-only": "S", "off": "X"}.get(mode, "S")
    draw.text((32, 32), letter, fill=(255, 255, 255, 255), anchor="mm")
    return img


# ── 消息去重 ──────────────────────────────────────────────

_processed_msgs = set()  # 已处理的消息 ID


def _is_duplicate(msg_id):
    if msg_id in _processed_msgs:
        return True
    _processed_msgs.add(msg_id)
    # 限制内存
    if len(_processed_msgs) > 500:
        _processed_msgs.clear()
    return False


# ── 命令处理 ──────────────────────────────────────────────

def handle_command(text, msg_id, icon_ref):
    """解析并执行命令，返回是否已处理."""
    text = text.strip()

    # 去重
    if _is_duplicate(msg_id):
        return True

    # ── 审批指令（中文，匹配最新 pending）──
    if text in ("允许", "始终允许", "拒绝"):
        decision = "deny" if text == "拒绝" else "allow"
        pending_dir = os.path.join(PROJECT_DIR, "pending")
        try:
            files = [f for f in os.listdir(pending_dir) if f.endswith(".json")]
        except FileNotFoundError:
            files = []

        if not files:
            send_reply(msg_id, "当前没有待审批的请求")
            return True

        files.sort(key=lambda f: os.path.getmtime(os.path.join(pending_dir, f)), reverse=True)
        pending_file = os.path.join(pending_dir, files[0])

        # 读取-修改-写入，带重试
        for attempt in range(3):
            try:
                with open(pending_file, "r", encoding="utf-8") as f:
                    pd = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                # 文件已被 hook 清理
                if attempt == 2:
                    send_reply(msg_id, "请求已过期")
                break

            if pd.get("decision"):
                # 已有决策
                if attempt == 2:
                    send_reply(msg_id, "该请求已处理")
                break

            pd["decision"] = decision
            try:
                with open(pending_file, "w", encoding="utf-8") as f:
                    json.dump(pd, f, ensure_ascii=False)
                label = "已批准" if decision == "allow" else "已拒绝"
                send_reply(msg_id, f"{label}: {pd.get('tool_name')} - {pd.get('args_summary', '')[:50]}")
                break
            except Exception:
                if attempt == 2:
                    send_reply(msg_id, "写入失败，请重试")
                time.sleep(0.1)

        return True

    # ── 旧格式 /approve <id> /deny <id>（兼容）──
    if text.startswith("/approve ") or text.startswith("/deny "):
        parts = text.split()
        if len(parts) >= 2:
            cmd, req_id = parts[0], parts[1]
            decision = "allow" if cmd == "/approve" else "deny"
            pending_file = os.path.join(PROJECT_DIR, "pending", f"{req_id}.json")
            if os.path.exists(pending_file):
                try:
                    with open(pending_file, "r", encoding="utf-8") as f:
                        pd = json.load(f)
                    pd["decision"] = decision
                    with open(pending_file, "w", encoding="utf-8") as f:
                        json.dump(pd, f, ensure_ascii=False)
                    label = "批准" if decision == "allow" else "拒绝"
                    send_reply(msg_id, f"已{label}: {pd.get('tool_name')} - {pd.get('args_summary', '')[:50]}")
                except Exception:
                    send_reply(msg_id, "审批处理失败")
            else:
                send_reply(msg_id, f"请求 {req_id} 不存在或已过期")
        return True

    # ── /notify ──
    if not text.startswith("/notify"):
        return False

    new_mode = None
    if text == "/notify on":
        new_mode = "all"
    elif text == "/notify ssh":
        new_mode = "ssh-only"
    elif text == "/notify off":
        new_mode = "off"
    elif text == "/notify status":
        current = load_mode()
        label = MODES.get(current, ("未知",))[0]
        send_reply(msg_id, f"CC-Notify 当前模式: {label}")
        return True

    if new_mode:
        save_mode(new_mode)
        label = MODES[new_mode][0]
        if icon_ref[0] is not None:
            icon_ref[0].icon = make_icon(new_mode)
            icon_ref[0].title = f"CC-Notify: {label}"
        send_reply(msg_id, f"CC-Notify 已切换为: {label}")
    return True


# ── 事件订阅 (实时) ──────────────────────────────────────

def feishu_events(icon_ref):
    """后台线程：lark-cli event consume 实时监听飞书消息."""
    open_id = _get_open_id()
    if not open_id:
        return
    while True:
        try:
            proc = subprocess.Popen(
                [LARK_CLI, "event", "consume", "im.message.receive_v1", "--as", "bot"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=CREATE_NO_WINDOW,
            )
            for line in proc.stdout:
                line = line.strip()
                if not line:
                    continue
                # 跳过日志行
                if line.startswith("[event]"):
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                msg_type = event.get("type", "")
                if msg_type != "im.message.receive_v1":
                    continue

                sender = event.get("sender_id", "")
                if sender != open_id:
                    continue

                content_str = event.get("content", "")
                try:
                    body = json.loads(content_str)
                    text = body.get("text", "")
                except (json.JSONDecodeError, TypeError):
                    text = content_str if isinstance(content_str, str) else ""

                msg_id = event.get("message_id", "")
                handle_command(text, msg_id, icon_ref)

        except Exception:
            pass

        # 事件订阅断开后等待重连
        time.sleep(5)


# ── 轮询回退 ──────────────────────────────────────────────

def feishu_poll(icon_ref):
    """后台线程：HTTP 轮询作为事件订阅的备用."""
    open_id = _get_open_id()
    if not open_id:
        return
    cfg = load_config()
    chat_id = cfg.get("chat_id", "")
    if not chat_id:
        # 发一条哑消息来发现
        ok, data = _lark(
            "im", "+messages-send", "--as", "bot",
            "--user-id", open_id,
            "--content", json.dumps({"text": " "}), "--msg-type", "text",
            timeout=15,
        )
        if ok and data.get("ok"):
            chat_id = data.get("data", {}).get("chat_id", "")
            if chat_id:
                cfg["chat_id"] = chat_id
                save_config(cfg)

    if not chat_id:
        return

    last_msg_id = None
    while True:
        try:
            params = json.dumps({
                "container_id_type": "chat",
                "container_id": chat_id,
                "page_size": 5,
                "sort_type": "ByCreateTimeDesc",
            })
            ok, data = _lark(
                "api", "GET", "/open-apis/im/v1/messages",
                "--params", params, "--as", "bot",
                timeout=10,
            )
            if not ok or not data:
                time.sleep(1)
                continue

            items = data.get("data", {}).get("items", [])
            if not items:
                time.sleep(1)
                continue

            msg_id = items[0].get("message_id", "")
            if msg_id == last_msg_id:
                time.sleep(1)
                continue
            last_msg_id = msg_id

            for msg in items:
                sender = msg.get("sender", {}).get("id", "")
                if sender != open_id:
                    continue

                body = msg.get("body", {}).get("content", "")
                try:
                    body_data = json.loads(body)
                    text = body_data.get("text", "")
                except (json.JSONDecodeError, TypeError):
                    text = body if isinstance(body, str) else ""

                msg_id_cur = msg.get("message_id", "")
                handle_command(text, msg_id_cur, icon_ref)

        except Exception:
            pass
        time.sleep(1)


# ── 托盘菜单 ──────────────────────────────────────────────

def _make_radio_callback(mode, icon_ref):
    def cb():
        save_mode(mode)
        if icon_ref[0] is not None:
            icon_ref[0].icon = make_icon(mode)
            icon_ref[0].title = f"CC-Notify: {MODES[mode][0]}"
    return cb


def create_menu(icon_ref):
    return pystray.Menu(
        pystray.MenuItem(
            "通知: 全部开启",
            _make_radio_callback("all", icon_ref),
            checked=lambda item: load_mode() == "all",
            radio=True,
        ),
        pystray.MenuItem(
            "通知: 仅SSH会话",
            _make_radio_callback("ssh-only", icon_ref),
            checked=lambda item: load_mode() == "ssh-only",
            radio=True,
        ),
        pystray.MenuItem(
            "通知: 关闭",
            _make_radio_callback("off", icon_ref),
            checked=lambda item: load_mode() == "off",
            radio=True,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", lambda: icon_ref[0].stop()),
    )


# ── 主入口 ────────────────────────────────────────────────

def main():
    mode = load_mode()
    icon_ref = [None]

    icon = pystray.Icon(
        "cc-notify",
        make_icon(mode),
        f"CC-Notify: {MODES[mode][0]}",
        menu=create_menu(icon_ref),
    )
    icon_ref[0] = icon

    # 轮询（事件订阅需在飞书开发者后台配置，暂用轮询）
    poll_thread = threading.Thread(target=feishu_poll, args=(icon_ref,), daemon=True)
    poll_thread.start()

    # 看门狗：定期刷新图标防 Windows 系统托盘重建后消失
    def icon_watchdog():
        while True:
            time.sleep(60)
            try:
                if icon_ref[0] is not None:
                    icon_ref[0].visible = True
            except Exception:
                pass
    watchdog = threading.Thread(target=icon_watchdog, daemon=True)
    watchdog.start()

    icon.run()


if __name__ == "__main__":
    main()
