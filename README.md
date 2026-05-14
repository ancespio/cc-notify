# CC-Notify on Lark CLI

> **Claude Code + 飞书 CLI** — 通过 `permissions.ask: ["Bash"]` 强制每次 Bash 弹窗，配合 PermissionRequest + Elicitation + Stop Hook，将所有用户需介入的场景（权限审批、提问、任务完成）实时推送到飞书，支持远程开关。

> **Claude Code + Feishu CLI** — Uses `permissions.ask: ["Bash"]` to force Bash permission dialogs, with PermissionRequest + Elicitation + Stop hooks pushing all user-intervention events to Feishu. Remote toggle supported.

## Abstract / 摘要

Controlling Claude Code on mobile devices typically requires a public IP and monitoring scripts. Tools like cc-connect bridge agents into IM platforms such as Feishu and WeChat, enabling control without a public IP. However, these tools rely on file-based session creation and cannot unify conversation history, making session management chaotic—they function best as pure IM-side bots. The official Claude app supports true mobile continuation but is exclusive to Pro subscribers. For relay work across locations, the most reliable approach remains NAT traversal (Tailscale) + SSH (Termius), which provides multi-device sync, command history, and AI-assisted input. Yet in non-office settings, attention is easily diverted—missed permission requests, elicitations, and task completions stall progress. Termius offers no native notification mechanism. This project proposes a new collaboration paradigm: combining IM tools with Claude Code's Hook interface to deliver stable notifications under complex network conditions. The tool is reliable in Claude Code + Feishu environments and supports remote on/off control via Feishu messages. Ablation experiments suggest compatibility potential with other agent tools and messaging platforms.

> 想在移动设备上控制 Claude Code 往往需要公网 IP。cc-connect 等工具通过 IM 将 Agent 接入飞书/微信，但基于文件的会话机制导致记录无法统一、管理混乱，仅适合纯 IM 端机器人。官方 Claude App 支持移动端接力但仅限 Pro 订阅。目前最可靠的接力方案仍是 Tailscale 内网穿透 + Termius SSH——多端同步、指令保存、AI 智能撰写。但在非办公场景下注意力容易被转移，导致错过权限申请、提问或任务完成通知。Termius 无原生提醒接口。本工作将 IM 工具与 Claude Code Hook 结合，在复杂网络环境下实现稳定通知播报，支持飞书端远程开关，消融实验表明对多 Agent 和多消息平台具有兼容潜力。

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

> 帮我在 Windows 上部署 CC-Notify：1) 确认已安装 `lark-cli`（`npm install -g @larksuite/cli`）并已登录；2) `git clone https://github.com/ancespio/cc-notify.git`；3) `cd cc-notify && pip install pystray Pillow`；4) 运行 `python -c "import subprocess,json,os; lark=os.path.join(os.environ['APPDATA'],'npm','lark-cli.cmd'); r=subprocess.run([lark,'api','GET','/open-apis/authen/v1/user_info'],capture_output=True,text=True,encoding='utf-8'); print(json.loads(r.stdout)['data']['open_id'])"` 获取 open_id，写入 `config.json`（格式 `{"open_id":"ou_xxx","chat_id":""}`）；5) 在 `~/.claude/settings.json` 中添加 `permissions.ask: ["Bash"]` 和 `PermissionRequest`、`Elicitation`、`Stop` 三个 Hook，command 指向 `notify_hook.py` 的绝对路径。

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
# Method 1: Direct launch / 直接启动
pythonw tray.py

# Method 2: Copy VBS template, adjust paths, double-click to run
# 复制 VBS 模板，调整路径，双击运行
copy start_tray.vbs.example start_tray.vbs
```

## Hook Setup / Hook 配置

Add to / 添加到 `~/.claude/settings.json`:

```json
{
  "permissions": {
    "ask": ["Bash"]
  },
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
    ],
    "Stop": [
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

> `permissions.ask: ["Bash"]` 是关键配置——强制每次 Bash 命令弹出权限确认，确保 PermissionRequest Hook 无条件触发。不加则 Bash 有 allow 规则时会跳过 Hook。

> `permissions.ask: ["Bash"]` is required — it forces a permission dialog for every Bash call, ensuring PermissionRequest fires unconditionally. Without it, auto-allowed Bash commands bypass the hook.

> 命令中的 CMD 特殊字符（`|` `&` `;` `<` `>`）会被自动裁剪为 `...`，避免破坏飞书消息传输。通知只做提醒，实际审批仍在终端进行。

> CMD special characters (`|` `&` `;` `<` `>`) in commands are auto-truncated to avoid breaking Feishu message delivery.

**Important**: Hook + permission changes take effect after restarting Claude Code / 修改后需重启 Claude Code。

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
├── notify_hook.py          # Hook script (required / 必需)
├── tray.py                 # Tray app (optional, for remote commands)
├── setup_guide.py          # Auto-install script / 自动安装脚本
├── config.example.json     # Config template / 配置模板
├── start_tray.vbs.example  # VBS template / VBS 模板 (copy to start_tray.vbs)
├── config.json             # (gitignored — your credentials)
├── mode.json               # (gitignored — runtime state)
└── start_tray.vbs          # (gitignored — your local launcher)
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
