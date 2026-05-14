# CC-Notify / CC-Notify

> Claude Code 权限飞书通知系统 — Windows 托盘应用 + Hook 脚本，Claude Code 需要授权或提问时实时推送到手机。
> Claude Code permission notification via Feishu — Windows tray app + hook scripts that push real-time alerts to your phone.

## Features / 功能

- **Permission alerts / 权限通知**: `PermissionRequest` 事件触发飞书通知
- **Elicitation alerts / 提问通知**: `Elicitation` 事件触发飞书通知
- **Windows tray app / 托盘应用**: 系统托盘图标，右键切换通知模式
- **Remote control / 远程控制**: 飞书内 `/notify on|off|ssh|status` 切换模式
- **SSH-aware / SSH 感知**: 自动检测 SSH 会话，提示语区分 Termius / 本地终端

## Prerequisites / 环境要求

- Python 3.7+ with `pystray` and `Pillow`
- [lark-cli](https://github.com/larksuite/cli) installed and authenticated (`npm install -g @larksuite/cli`)
- Feishu bot with IM message permissions / 飞书机器人需有 IM 消息权限

## Quick Start / 快速开始

```bash
# Install Python dependencies / 安装依赖
pip install pystray Pillow

# Create config from template / 从模板创建配置
cp config.example.json config.json
# Edit config.json: set your Feishu open_id / 填入飞书 open_id

# Test the hook script / 测试 Hook 脚本
echo '{"hook_event_name":"PermissionRequest","tool_name":"Bash","tool_input":{"command":"echo test"},"cwd":"."}' | python notify_hook.py

# Start the tray app (silent) / 无窗口启动
start_tray.vbs

# Or debug with visible console / 调试模式
python tray.py
```

## Configuration / 配置

### config.json

```json
{
  "open_id": "ou_xxxxxxxxxx",
  "chat_id": ""
}
```

- `open_id`: Feishu user open_id. Find via / 通过以下命令获取：
  `lark-cli api GET /open-apis/authen/v1/user_info`
- `chat_id`: Auto-discovered on first run / 首次运行时自动发现

### mode.json

```json
{"mode": "ssh-only"}
```

| Mode / 模式 | Behavior / 行为 |
|-------------|-----------------|
| `all` | Always send / 始终发送 |
| `ssh-only` | Only when `SSH_TTY` or `SSH_CONNECTION` is set / 仅 SSH 会话 |
| `off` | No notifications / 关闭通知 |

### Claude Code Hook Setup / Hook 配置

Add to / 添加到 `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": "*",
        "hooks": [{
          "type": "command",
          "command": "python \"C:/path/to/cc-notify/notify_hook.py\""
        }]
      }
    ],
    "Elicitation": [
      {
        "matcher": "*",
        "hooks": [{
          "type": "command",
          "command": "python \"C:/path/to/cc-notify/notify_hook.py\""
        }]
      }
    ]
  }
}
```

## Remote Commands / 远程指令

Send in Feishu bot chat / 在飞书机器人聊天中发送：

| Command / 指令 | Effect / 效果 |
|----------------|---------------|
| `/notify on` | Enable all / 全部开启 |
| `/notify ssh` | SSH-only mode / 仅 SSH |
| `/notify off` | Disable / 关闭 |
| `/notify status` | Show current mode / 查看当前模式 |

## Project Structure / 项目结构

```
cc-notify/
├── tray.py              # Windows tray app / 托盘应用
├── notify_hook.py       # Claude Code hook script / Hook 脚本
├── hook_debug.py        # Hook diagnostics / 诊断脚本
├── start_tray.vbs       # Silent launcher / 无窗口启动器
├── config.example.json  # Config template / 配置模板
├── config.json          # Local config (gitignored)
├── mode.json            # Notification mode (gitignored)
└── pending/             # Approval queue (gitignored)
```

## License / 许可

MIT
