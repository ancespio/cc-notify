# CC-Notify / CC-Notify

> **Claude Code + 飞书 CLI 专用** — 通过 Claude Code Hook 将权限请求和提问事件实时推送到飞书。
> **Claude Code + Feishu CLI only** — Push Claude Code permission requests and elicitation events to Feishu in real time via hooks.

## How It Works / 工作原理

```
Claude Code (local/SSH) → Hook fires (PermissionRequest/Elicitation)
    → notify_hook.py → lark-cli → Feishu Bot → 你的手机
                                                      ↑
tray.py (Windows 托盘) ← lark-cli polling ← /notify on|off 指令
```

The hook script (`notify_hook.py`) and tray app (`tray.py`) are **independent**. Notifications work without the tray; the tray is only needed for remote `/notify` commands.

Hook 脚本和托盘应用**独立运行**——通知由 Hook 触发，不需要托盘；托盘仅用于接收飞书 `/notify` 远程指令。

## One-Liner Setup / 一键安装

Copy this to your AI agent (Claude Code, Cursor, etc.):

> 帮我在 Windows 上部署 CC-Notify：1) 确认已安装 `lark-cli`（`npm install -g @larksuite/cli`）并已登录；2) `git clone https://github.com/ancespio/cc-notify.git`；3) `cd cc-notify && pip install pystray Pillow`；4) 运行 `python -c "import subprocess,json,os; lark=os.path.join(os.environ['APPDATA'],'npm','lark-cli.cmd'); r=subprocess.run([lark,'api','GET','/open-apis/authen/v1/user_info'],capture_output=True,text=True,encoding='utf-8'); print(json.loads(r.stdout)['data']['open_id'])"` 获取 open_id，写入 `config.json`（格式 `{"open_id":"ou_xxx","chat_id":""}`）；5) 在 `~/.claude/settings.json` 的 `hooks` 中添加 PermissionRequest 和 Elicitation 两个 Hook，command 指向 `notify_hook.py` 的绝对路径。

## Prerequisites / 前提

- **Claude Code** (Windows) with hooks enabled
- **[lark-cli](https://github.com/larksuite/cli)** (`npm install -g @larksuite/cli`) — 已认证的飞书 CLI
- **Feishu app with bot** — lark-cli 关联的飞书应用需有 `im:message:p2p_msg:readonly` 和 `im:message:send_as_bot` 权限
- Python 3.7+ with `pystray` and `Pillow` (for tray app / 托盘可选)

## Quick Start / 快速开始

```bash
git clone https://github.com/ancespio/cc-notify.git
cd cc-notify
pip install pystray Pillow

# Get your Feishu open_id / 获取飞书 open_id
python -c "
import subprocess,json,os
lark=os.path.join(os.environ['APPDATA'],'npm','lark-cli.cmd')
r=subprocess.run([lark,'api','GET','/open-apis/authen/v1/user_info'],capture_output=True,text=True,encoding='utf-8')
print(json.loads(r.stdout)['data']['open_id'])
"

# Create config / 创建配置
echo '{"open_id":"ou_YOUR_ID","chat_id":""}' > config.json

# Test / 测试
echo '{"hook_event_name":"PermissionRequest","tool_name":"Bash","tool_input":{"command":"echo test"},"cwd":"."}' | python notify_hook.py

# Start tray (optional / 可选)
pythonw tray.py
```

## Hook Setup / Hook 配置

Add to / 添加到 `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": "*",
        "hooks": [{
          "type": "command",
          "command": "python \"C:/absolute/path/to/cc-notify/notify_hook.py\""
        }]
      }
    ],
    "Elicitation": [
      {
        "matcher": "*",
        "hooks": [{
          "type": "command",
          "command": "python \"C:/absolute/path/to/cc-notify/notify_hook.py\""
        }]
      }
    ]
  }
}
```

**Important**: Hook changes take effect after restarting Claude Code / Hook 修改后需重启 Claude Code。

## Configuration / 配置

### config.json (gitignored)

```json
{
  "open_id": "ou_xxxxxxxxxx",
  "chat_id": ""
}
```

- `open_id` — Your Feishu user ID (see Quick Start for auto-detection)
- `chat_id` — Auto-discovered on first tray run, leave empty

### mode.json (gitignored)

| Mode | Behavior |
|------|----------|
| `all` | Always notify / 始终通知 |
| `ssh-only` | Only when `SSH_TTY` or `SSH_CONNECTION` is set / 仅 SSH 会话 |
| `off` | No notifications / 关闭 |

## Remote Commands / 远程指令

Send in Feishu bot chat (requires tray running) / 需托盘运行：

| Command | Effect |
|---------|--------|
| `/notify on` | All on / 全部开启 |
| `/notify ssh` | SSH-only / 仅 SSH |
| `/notify off` | Disable / 关闭 |
| `/notify status` | Current mode / 查看状态 |

## Files / 文件说明

```
cc-notify/
├── notify_hook.py       # Hook script (required / 必需)
├── tray.py              # Tray app (optional, for remote commands)
├── hook_debug.py        # Debug tool / 诊断工具
├── start_tray.vbs       # Windows silent launcher / 无窗口启动
├── config.example.json  # Config template / 配置模板
├── config.json          # (gitignored — your credentials)
└── mode.json            # (gitignored — runtime state)
```

Runtime directories (`pending/`, `__pycache__/`) are created on demand and gitignored.

## Troubleshooting / 常见问题

| Symptom / 症状 | Cause / 原因 | Fix / 解决 |
|---------------|-------------|-----------|
| No notification / 无通知 | Hook not loaded | Restart Claude Code / 重启 Claude Code |
| Tray icon missing / 无托盘图标 | `pythonw` not found | Use `python tray.py` for debug / 调试模式启动 |
| Garbled Chinese / 中文乱码 | GBK encoding in subprocess | Already fixed in v1.0+ |
| lark-cli not found / lark-cli 找不到 | PATH issue | Uses `%APPDATA%\npm\lark-cli.cmd` by default |

## License / 许可

MIT
