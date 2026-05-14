#!/usr/bin/env python
"""CC-Notify 一键安装 — 给 AI Agent 执行的完整部署脚本.
Usage:
    python setup_guide.py --dry-run    # 仅打印步骤，不修改文件
    python setup_guide.py              # 执行安装
"""
import json
import os
import subprocess
import sys

DRY_RUN = "--dry-run" in sys.argv
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LARK = os.path.join(os.environ.get("APPDATA", ""), "npm", "lark-cli.cmd")
SETTINGS = os.path.join(os.environ.get("USERPROFILE", ""), ".claude", "settings.json")


def run(cmd, **kw):
    if DRY_RUN:
        print(f"  [dry-run] {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        return True, ""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                           encoding="utf-8", errors="replace")
        return r.returncode == 0, r.stdout.strip()
    except Exception as e:
        return False, str(e)


def step(msg):
    print(f"\n{'[DRY-RUN] ' if DRY_RUN else ''}{msg}")


def main():
    errors = []

    # 1. Check lark-cli
    step("1/5 检查 lark-cli...")
    ok, out = run([LARK, "auth", "status"])
    if not ok:
        errors.append("lark-cli 未安装或未登录。请先: npm install -g @larksuite/cli && lark-cli auth login")
    else:
        print(f"  lark-cli OK")

    # 2. Check Python deps
    step("2/5 检查 Python 依赖...")
    ok, _ = run([sys.executable, "-c", "import pystray; import PIL"])
    if not ok:
        run([sys.executable, "-m", "pip", "install", "pystray", "Pillow"])
    print(f"  pystray, Pillow OK")

    # 3. Get open_id
    step("3/5 获取 Feishu open_id...")
    ok, out = run([LARK, "api", "GET", "/open-apis/authen/v1/user_info", "--params", "{}"])
    open_id = ""
    if ok:
        try:
            open_id = json.loads(out)["data"]["open_id"]
            print(f"  open_id: {open_id}")
        except (json.JSONDecodeError, KeyError):
            errors.append("无法解析 open_id")
    else:
        errors.append("无法获取 open_id，请确认 lark-cli 已登录")

    # 4. Write config.json
    step("4/5 写入 config.json...")
    config_file = os.path.join(SCRIPT_DIR, "config.json")
    if not DRY_RUN:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump({"open_id": open_id, "chat_id": ""}, f, ensure_ascii=False)
        print(f"  已写入: {config_file}")

    # 5. Update Claude Code hooks
    step("5/5 配置 Claude Code hooks...")
    hook_cmd = f"python \"{os.path.join(SCRIPT_DIR, 'notify_hook.py')}\""
    hook_entry = {
        "type": "command",
        "command": hook_cmd,
    }
    hook_block = {
        "matcher": "*",
        "hooks": [hook_entry],
    }

    try:
        if os.path.exists(SETTINGS):
            with open(SETTINGS, "r", encoding="utf-8") as f:
                settings = json.load(f)
        else:
            settings = {}

        if "hooks" not in settings:
            settings["hooks"] = {}
        settings["hooks"]["PermissionRequest"] = [hook_block]
        settings["hooks"]["Elicitation"] = [hook_block]

        if not DRY_RUN:
            with open(SETTINGS, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            print(f"  已更新: {SETTINGS}")
    except Exception as e:
        errors.append(f"Hook 配置失败: {e}")

    # Summary
    print("\n" + "=" * 50)
    if errors:
        print("安装完成，但有以下问题：")
        for e in errors:
            print(f"  ❌ {e}")
    else:
        print("全部完成！重启 Claude Code 后生效。")
        print("启动托盘: pythonw " + os.path.join(SCRIPT_DIR, "tray.py"))
    print("=" * 50)


if __name__ == "__main__":
    main()
