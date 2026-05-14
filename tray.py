#!/usr/bin/env python
"""CC-Notify 托盘应用：Windows 常驻托盘图标 + 飞书远程指令监听."""
import json
import os
import subprocess
import sys
import threading
import time

# Windows 无控制台窗口标志
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
OPEN_ID = "ou_REDACTED"
BOT_APP_ID = "cli_a97608a4cbf89bb4"
LARK_CLI = os.path.join(os.environ.get("APPDATA", ""), "npm", "lark-cli.cmd")

MODES = {
    "all": ("全部开启", (76, 175, 80)),
    "ssh-only": ("仅SSH会话", (255, 193, 7)),
    "off": ("关闭", (158, 158, 158)),
}
POLL_INTERVAL = 1


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


# ── 飞书 API 封装 ──────────────────────────────────────────

def _lark(*args, timeout=10):
    """调用 lark-cli，返回 (ok, data_dict)."""
    try:
        result = subprocess.run(
            [LARK_CLI] + list(args),
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            return False, None
        data = json.loads(result.stdout) if result.stdout.strip() else {}
        return True, data
    except Exception:
        return False, None


def discover_chat_id():
    """通过发一条无声消息来发现 bot-user P2P chat_id."""
    cfg = load_config()
    if cfg.get("chat_id"):
        return cfg["chat_id"]

    content = json.dumps({"text": " "})
    ok, data = _lark(
        "im", "+messages-send", "--as", "bot",
        "--user-id", OPEN_ID,
        "--content", content, "--msg-type", "text",
        timeout=15,
    )
    if ok and data.get("ok"):
        chat_id = data.get("data", {}).get("chat_id", "")
        if chat_id:
            cfg["chat_id"] = chat_id
            save_config(cfg)
            return chat_id
    return ""


def send_reply(message_id, text):
    """作为 bot 回复消息."""
    content = json.dumps({"text": text})
    _lark(
        "im", "+messages-reply", "--as", "bot",
        "--message-id", message_id,
        "--content", content, "--msg-type", "text",
        timeout=10,
    )


# ── 图标生成 ──────────────────────────────────────────────

def make_icon(mode):
    color = MODES.get(mode, MODES["ssh-only"])[1]
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([8, 8, 56, 56], fill=color, outline=(255, 255, 255, 180), width=2)
    letter = {"all": "A", "ssh-only": "S", "off": "X"}.get(mode, "S")
    draw.text((32, 32), letter, fill=(255, 255, 255, 255), anchor="mm")
    return img


# ── 飞书轮询 ──────────────────────────────────────────────

_last_msg_id = None


def feishu_poll(icon_ref):
    """后台线程：每 1s 轮询飞书 Bot 聊天，解析 /notify 指令."""
    global _last_msg_id
    chat_id = discover_chat_id()

    if not chat_id:
        return  # 无法获取 chat_id，静默退出轮询

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
                time.sleep(POLL_INTERVAL)
                continue

            items = data.get("data", {}).get("items", [])
            if not items:
                time.sleep(POLL_INTERVAL)
                continue

            # 去重
            msg_id = items[0].get("message_id", "")
            if msg_id == _last_msg_id:
                time.sleep(POLL_INTERVAL)
                continue
            _last_msg_id = msg_id

            for msg in items:
                sender = msg.get("sender", {}).get("id", "")

                # 只响应义人的指令
                if sender != OPEN_ID:
                    continue

                # 跳过 bot 自己的消息
                if sender == BOT_APP_ID:
                    continue

                body = msg.get("body", {}).get("content", "")
                try:
                    body_data = json.loads(body)
                    text = body_data.get("text", "")
                except (json.JSONDecodeError, TypeError):
                    text = body if isinstance(body, str) else ""

                text = text.strip()
                if not text.startswith("/notify"):
                    continue

                msg_id_cur = msg.get("message_id", "")

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
                    send_reply(msg_id_cur, f"CC-Notify 当前模式: {label}")
                    continue

                if new_mode:
                    save_mode(new_mode)
                    label = MODES[new_mode][0]
                    if icon_ref[0] is not None:
                        icon_ref[0].icon = make_icon(new_mode)
                        icon_ref[0].title = f"CC-Notify: {label}"
                    send_reply(msg_id_cur, f"CC-Notify 已切换为: {label}")

        except Exception:
            pass

        time.sleep(POLL_INTERVAL)


# ── 托盘菜单 ──────────────────────────────────────────────

def _make_radio_callback(mode, icon_ref):
    def cb():
        save_mode(mode)
        if icon_ref[0] is not None:
            icon_ref[0].icon = make_icon(mode)
            icon_ref[0].title = f"CC-Notify: {MODES[mode][0]}"
    return cb


def create_menu(icon_ref):
    current = load_mode()

    def is_checked(mode):
        return lambda item: load_mode() == mode

    return pystray.Menu(
        pystray.MenuItem(
            "通知: 全部开启",
            _make_radio_callback("all", icon_ref),
            checked=is_checked("all"),
            radio=True,
        ),
        pystray.MenuItem(
            "通知: 仅SSH会话",
            _make_radio_callback("ssh-only", icon_ref),
            checked=is_checked("ssh-only"),
            radio=True,
        ),
        pystray.MenuItem(
            "通知: 关闭",
            _make_radio_callback("off", icon_ref),
            checked=is_checked("off"),
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

    poll_thread = threading.Thread(
        target=feishu_poll,
        args=(icon_ref,),
        daemon=True,
    )
    poll_thread.start()

    icon.run()


if __name__ == "__main__":
    main()
