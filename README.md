# Agent-Notify

Agent-Notify v1.0.2 将 Codex 和 Claude Code 的权限申请、结构化提问与任务
完成事件推送到 Bark 或飞书，并可通过飞书远程切换两种渠道的通知模式。

它不依赖 Codex App 自身的远程通知，因此通知是否送达不受线程新旧或桌面端当前
是否打开该对话影响。

## Windows 安装

1. 下载并双击 `Agent-Notify-Setup-v1.0.2.exe`。
2. 选择安装目录，默认是 `C:\Program Files\Agent-Notify`。
3. 安装完成后自动打开五步首次配置向导。
4. 按需配置 Bark、飞书、Agent Hook 与登录自启动；任意渠道均可跳过。
5. 完成向导后重启已安装 Hook 的 Agent。

Bark 与飞书都不是必选项，可以仅启用其中一个、同时启用、全部关闭，或只启用
飞书远程控制。

首次配置 Bark：

1. 在 iPhone 安装 Bark，并复制设备 Key。
2. 在 Bark 标签页启用通知并填写 Key；“显示”开关可反复切换且不会丢失内容。
3. 选择全部通知、仅 SSH 或关闭。
4. 点击“校验图标”，确认远程图片可下载、可解码且尺寸合规。
5. 点击“发送 Bark 测试通知”，检查 iPhone 通知是否使用 Agent-Notify 自有图标。

如果升级后仍看到 `chatgpt://` 或 Bark 官方图标地址，设置页只显示
“旧版配置”提示，不会自动覆盖非空配置。点击“恢复新版默认”可主动改为：

```text
跳转：chatgpt://codex
图标：https://raw.githubusercontent.com/ancespio/Agent-Notify/v1.0.2/assets/agent-notify.png
```

首次配置飞书：

飞书配置使用 [lark-cli 官方流程](https://github.com/larksuite/cli)。
设置页和首次向导提供对应的分步按钮，命令会在可见 PowerShell 窗口中运行：

1. 点击“1. 安装”，对应：
   `npx @larksuite/cli@latest install`
2. 点击“2. 初始化”，对应：
   `lark-cli config init`
3. 点击“3. 登录”，对应：
   `lark-cli auth login --recommend`
4. 点击“4. 重新检测”，程序执行：
   `lark-cli auth status`
5. 如果版本低于 1.0.53，点击“更新 CLI”，在可见 PowerShell 中执行
   `lark-cli update`。
6. 登录成功后点击“自动获取 open_id”，程序执行：
   `lark-cli api GET /open-apis/authen/v1/user_info --as user --format json`
7. 确认自动填写的 `open_id`，再点击“连接并发送测试消息”。
8. Agent-Notify 从连接消息响应自动保存只读的 `chat_id`，用户无需自行查找。

这些交互命令不会静默执行。Agent-Notify 不接触飞书密码或登录令牌；
`open_id` 自动获取失败时，可以运行上述 `user_info` 命令并手动填写返回结果中的
`open_id`。

安装过程本身不要求填写通知凭据。设置窗口是唯一的配置入口：

- 开始菜单中的“Agent-Notify 设置”
- 托盘菜单中的“打开设置”
- 双击安装目录中的 `Agent-Notify.exe`

安装器会安全合并而不是覆盖：

- `~/.codex/hooks.json`
- `~/.claude/settings.json`

修改已有文件前，Agent-Notify 会在同一目录创建带时间戳的备份。卸载时只移除
Agent-Notify 添加的 Hook。v1.0.2 起，卸载器会询问是否同时删除用户配置、
日志和迁移备份，默认选择删除；选择“否”可保留配置供以后重装使用。

Agent-Notify 不会写入 `AGENTS.md`。从早期版本升级时，只会清理带有
Agent-Notify 标记的旧提问兜底区块，其他用户指令保持不变。

## 安装内容

程序文件安装到用户在安装器中选择的目录：

```text
C:\Program Files\Agent-Notify
```

默认目录内包含：

```text
Agent-Notify/
|-- Agent-Notify.exe
|-- README.txt
|-- LICENSE.txt
|-- install-home.txt
`-- unins000.exe
```

用户配置单独存放在：

```text
%APPDATA%\Agent-Notify\config.json
```

Bark Key 通过 HTTPS 请求体发送，不会放入请求 URL，也不会写入 Hook 输出。
飞书功能通过本机已登录的 `lark-cli` 工作，Agent-Notify 不保存飞书密码。

## Windows 托盘

Agent-Notify 以轻量通知区域进程运行。托盘菜单可以：

- 分别切换 Bark 与飞书的全部通知、仅 SSH、关闭模式。
- 发送 Bark 测试通知。
- 打开设置界面。
- 开启或关闭登录自启动。
- 退出当前托盘进程。

Hook 通知不依赖托盘进程。托盘只负责状态与设置入口；Hook 触发时，Codex 和
Claude Code 会短暂启动同一个可执行文件发送通知。

## 飞书远程控制

飞书通知与飞书远程控制是两个独立开关。即使飞书通知模式设为关闭，远程控制
仍会继续轮询，因此可以从飞书恢复通知。

```text
/notify on|ssh|off
/notify status
/notify bark on|ssh|off|status
/notify feishu on|ssh|off|status
```

`on` 会启用渠道并设为全部通知，`ssh` 会启用渠道并设为仅 SSH，`off`
会关闭通知渠道。飞书远程控制开关始终独立，不会被 `off` 关闭。
`/notify status` 会回复两个渠道的启用状态、模式和远程控制状态。

控制器只接受配置的 `open_id` 在已发现私聊中的命令。启动时只记录已有消息，
不会重放历史 `/notify` 命令；重复消息也只处理一次。

## 支持的事件

| Agent | 权限申请 | 结构化提问 | 本轮完成 |
| --- | --- | --- | --- |
| Codex | 原生 `PermissionRequest` | 原生 `PreToolUse(request_user_input)` | 原生 `Stop` |
| Claude Code | 原生 `PermissionRequest` | `AskUserQuestion` 的 `PreToolUse` 与 MCP `Elicitation` | 原生 `Stop` |

Codex 将结构化提问暴露为内置 `request_user_input` 工具。Agent-Notify 通过
`PreToolUse` 匹配该工具，因此提问通知不依赖模型指令，也不需要修改
`AGENTS.md`。

## 点击通知跳转

Bark 通知默认携带：

```text
chatgpt://codex
```

点击通知后会请求打开 iOS ChatGPT App 的 Codex 入口。跳转地址可在设置界面
或安装器中修改，留空时会恢复 `chatgpt://codex`。

本版本不生成具体线程的 `codex://threads/<session UUID>` 深链。OpenAI 已记录
该协议可由 Codex App 打开，但尚未明确保证 ChatGPT iOS 可以处理它，因此默认
使用 ChatGPT App 的 `chatgpt://codex` 入口。

## 配置

核心配置示例：

```json
{
  "config_version": "1.0.2",
  "providers": {
    "bark": {
      "enabled": true,
      "mode": "all",
      "server": "https://api.day.app",
      "device_key": "YOUR_BARK_DEVICE_KEY",
      "group": "Agent-Notify",
      "url": "chatgpt://codex",
      "icon": "https://raw.githubusercontent.com/ancespio/Agent-Notify/v1.0.2/assets/agent-notify.png",
      "timeout": 8
    },
    "feishu": {
      "enabled": false,
      "control_enabled": false,
      "mode": "all",
      "open_id": "",
      "chat_id": "",
      "lark_cli": "",
      "timeout": 10
    }
  },
  "agents": {
    "codex": true,
    "claude": true
  },
  "events": {
    "permission": true,
    "question": true,
    "stop": true
  }
}
```

`mode` 可取 `all`、`ssh-only`、`off`。设置窗口支持自建 Bark 服务和自定义
通知图标 URL。设置页会限制图标下载大小和超时，仅接受可解码的 PNG、JPEG 或
WebP，并检查图片尺寸。默认远程图标还必须与安装包内
`agent-notify.png` 的 SHA-256 一致。Hook 运行时不会重复联网预检，以免阻塞
Agent；只有手动校验和 Bark 测试通知会执行完整校验。

Windows 程序、托盘、安装器和 Bark 通知默认使用 Agent-Notify 自有图标：
浅色底、深色通知铃、白色终端符号与珊瑚色提醒点。

## 升级迁移

- 沿用 `%APPDATA%\Agent-Notify\config.json`，保留已有 Bark Key 和 Hook 选择。
- v1.0.2 首次加载旧配置时会创建时间戳备份并写入 `config_version`。
- 仅将精确旧默认 `chatgpt://` 和 v1.0.0/v1.0.1 图标迁移为新版默认；
  用户自定义跳转和图标保持不变。
- 旧版顶层 `open_id`、`chat_id` 会迁移到飞书 provider。
- 旧 `mode.json` 会在首次运行时迁移为 Bark 与飞书各自的模式。
- 迁移后所有运行状态均写入 `config.json`。
- Agent-Notify 不会新增 `AGENTS.md` 内容，只清理旧版标记区块。

## Codex 测试

在 Codex 的 Plan 模式中新建线程，并粘贴 `CODEX_TEST_PROMPT.md` 中的提示词。
预期依次收到：

1. `Codex 需要授权`
2. `Codex 正在提问`
3. `Codex 本轮完成`

## 从源码构建

要求：

- Windows 10 或更高版本
- Python 3.10+
- PyInstaller
- Pillow
- pystray
- wxPython
- Inno Setup 6

构建命令：

```powershell
python -m unittest discover -s tests -v
python build_windows.py
iscc installer\Agent-Notify.iss
```

最终安装包生成在：

```text
dist-installer\Agent-Notify-Setup-v1.0.2.exe
```

## 常见问题

- Bark Key 无法查看：v1.0.2 使用隐藏/明文双文本框切换；旧版动态修改
  `TE_PASSWORD` 的方式在 Windows 上无效。
- 图标校验失败：确认 URL 直接返回图片而非 HTML，文件不超过 2 MB，尺寸在
  64 到 4096 像素之间。
- 没有 Bark 通知：检查 Bark 是否启用、Key 是否正确，以及模式是否为关闭。
- 托盘 Bark 测试失败：托盘会显示简短原因，完整脱敏日志位于
  `%APPDATA%\Agent-Notify\agent-notify.log`。
- `lark-cli` 未就绪：依次执行安装、初始化、登录，并用
  `lark-cli auth status` 检查。
- 无法自动获取 `open_id`：运行 README 中的 `user_info` 命令，将返回值里的
  `open_id` 手动填入。
- `chat_id` 为空：点击“连接并发送测试消息”；它由响应自动建立，不需要查询。
- 没有飞书通知：确认 `lark-cli` 已登录、`open_id` 正确并完成连接测试。
- 飞书命令无响应：确认远程控制开关已开启，且消息来自配置的用户私聊。
- 修改 Hook 后无效果：重启 Codex 或 Claude Code；Codex 还需在 `/hooks`
  中信任 Agent-Notify Hook。
- 托盘没有出现：双击 `Agent-Notify.exe` 保存设置，或重新登录 Windows。

## 远程批准限制

Bark 不提供自定义“允许”和“拒绝”通知按钮，因此 Agent-Notify v1.0.2 只负责通知，
批准操作仍需在 Codex 或 Claude Code 中完成。Apple Watch 是否镜像 Bark
通知取决于 iPhone 与 Apple Watch 的通知设置。

## 许可证

Agent-Notify 使用 MIT License，详见 `LICENSE`。
