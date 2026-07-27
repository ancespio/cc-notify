# Agents-Notify

Agents-Notify v1.0.4 将 Codex 和 Claude Code 的权限申请、结构化提问与任务
完成事件推送到 Bark 或飞书，并可通过飞书远程切换两种渠道的通知模式。

它不依赖 Codex App 自身的远程通知，因此通知是否送达不受线程新旧或桌面端当前
是否打开该对话影响。

重建说明见 [`docs/REBUILD.md`](docs/REBUILD.md)，待改进项见
[`docs/IMPROVEMENTS.md`](docs/IMPROVEMENTS.md)。

## Windows 安装

1. 下载并双击 `Agents-Notify-Setup-v1.0.4.exe`。
2. 选择安装目录，默认是 `C:\Program Files\Agents-Notify`。
3. 安装完成后自动打开五步首次配置向导。
4. 按需配置 Bark、飞书、Agent Hook 与登录自启动；任意渠道均可跳过。
5. 完成向导后重启已安装 Hook 的 Agent。

官方下载：
[Agents-Notify v1.0.4](https://github.com/ancespio/Agents-Notify/releases/tag/v1.0.4)

安装包 SHA-256：
`CF36D2817ADEB5CEB0CF47DD06FCDAC842652A49B94FBFAB6E186D62BDCAE54`

Bark 与飞书都不是必选项，可以将任一渠道设为全部通知、仅 SSH 或关闭，也可以
在两种通知均关闭时只启用飞书远程控制。

首次配置 Bark：

1. 在 iPhone 安装 Bark，并复制设备 Key。
2. 在 Bark 标签页填写 Key；“显示”开关可反复切换且不会丢失内容。
3. 选择全部通知、仅 SSH 或关闭。
4. 点击“校验图标”，确认远程图片可下载、可解码且尺寸合规。
5. 点击“发送 Bark 测试通知”，检查 iPhone 通知是否使用 Agents-Notify 自有图标。

如果升级后仍看到 `chatgpt://` 或 Bark 官方图标地址，设置页只显示
“旧版配置”提示，不会自动覆盖非空配置。点击“恢复新版默认”可主动改为：

```text
跳转：chatgpt://codex
图标：https://raw.githubusercontent.com/ancespio/Agents-Notify/master/assets/agents-notify.png
```

### 获取并填写飞书 App ID/App Secret

飞书远程控制使用的是企业自建的“应用机器人”，不是群聊中只有 Webhook 的
“自定义机器人”。HTTP 消息 API 和 WebSocket 事件长连接使用同一个应用，
不需要安装或登录 `lark-cli`。

1. 打开[飞书开发者后台](https://open.feishu.cn/app)，创建或进入一个企业自建应用。
2. 在“应用能力 > 添加应用能力”中添加“机器人”。
3. 在“权限管理 > API 权限”中以应用身份开通：
   - `im:message.p2p_msg:readonly`：读取用户发给机器人的单聊消息；
   - `im:message:send_as_bot`：以应用的身份发消息。
4. 进入“凭证与基础信息 > 应用凭证”，复制 App ID 和 App Secret。
5. 打开 Agents-Notify 设置页的“飞书”标签，将两项分别写入“飞书 App ID”和
   “飞书 App Secret”。App Secret 会以密码框显示。再填写你的 `open_id`；
   它是通知接收人和远程控制授权人的飞书用户标识，不是邮箱或手机号。

推荐始终通过设置页写入。需要手动编辑时，先退出托盘进程，再编辑：

```text
%APPDATA%\Agents-Notify\config.json
```

对应字段为：

```json
{
  "providers": {
    "feishu": {
      "app_id": "cli_xxx",
      "app_secret": "YOUR_APP_SECRET"
    }
  }
}
```

App Secret 等同应用密码。当前版本将它明文保存在本机配置文件中，请勿把该文件
上传、提交或发给他人；如果在飞书后台重置 App Secret，也必须同步更新本机配置。

### 连接飞书机器人

1. 在设置页填写 App ID、App Secret 和 `open_id`。
2. 点击“发送测试消息并生成 chat_id”。程序通过飞书 HTTP OpenAPI 发送测试消息，
   并自动保存返回的 `chat_id`。
3. 如果要启用远程控制，勾选“启用飞书远程控制”并保存设置，保持托盘进程运行。
4. 回到飞书开发者后台的“事件与回调 > 事件配置”，选择“使用长连接接收事件”，
   添加 `im.message.receive_v1`。飞书要求保存订阅方式时已有长连接在线。
5. 在“版本管理与发布”中创建并发布新版本，使机器人能力、权限和事件配置生效。
6. 在飞书中私聊该机器人并发送 `/notify status`；收到状态回复即表示连接完成。

Agents-Notify 使用同一组 App ID/App Secret 同时完成两件事：WebSocket 长连接接收事件，
HTTP OpenAPI 发送通知和回复。前者不需要轮询消息历史，后者每发送或回复一条消息都会
消耗飞书 API 调用额度。

同一个 App ID 不要同时启动多个独立的长连接消费者；飞书会把每个事件随机交给
其中一个客户端，而不是向所有客户端广播。

安装过程本身不要求填写通知凭据。设置窗口是唯一的配置入口：

- 开始菜单中的“Agents-Notify 设置”
- 托盘菜单中的“打开设置”
- 双击安装目录中的 `Agents-Notify.exe`

安装器会安全合并而不是覆盖：

- `~/.codex/hooks.json`
- `~/.claude/settings.json`

修改已有文件前，Agents-Notify 会在同一目录创建带时间戳的备份。卸载时只移除
Agents-Notify 添加的 Hook。v1.0.2 起，卸载器会询问是否同时删除用户配置、
日志和迁移备份，默认选择删除；选择“否”可保留配置供以后重装使用。

Agents-Notify 不会写入 `AGENTS.md`。从早期版本升级时，只会清理带有
`Agents-Notify` 或旧 `Agent-Notify` 标记的提问兜底区块，其他用户指令
保持不变。

## 安装内容

程序文件安装到用户在安装器中选择的目录：

```text
C:\Program Files\Agents-Notify
```

默认目录内包含：

```text
Agents-Notify/
|-- Agents-Notify.exe
|-- README.txt
|-- LICENSE.txt
|-- install-home.txt
`-- unins000.exe
```

用户配置单独存放在：

```text
%APPDATA%\Agents-Notify\config.json
```

Bark Key 通过 HTTPS 请求体发送，不会放入请求 URL，也不会写入 Hook 输出。
飞书遥控通过官方 `lark-oapi` 长连接接收消息，通知测试、主动通知和命令回复也通过
同一个 SDK 调用飞书 HTTP OpenAPI；不再依赖本机 `lark-cli`。

## Windows 托盘

Agents-Notify 以轻量通知区域进程运行。托盘菜单可以：

- 分别切换 Bark 与飞书的全部通知、仅 SSH、关闭模式。
- 发送 Bark 测试通知。
- 开启或关闭飞书远程控制；配置不完整时会直接打开飞书设置页。
- 发送飞书测试通知。
- 打开设置界面。
- 开启或关闭登录自启动。
- 退出当前托盘进程。

Hook 通知不依赖托盘进程。托盘只负责状态与设置入口；Hook 触发时，Codex 和
Claude Code 会短暂启动同一个可执行文件发送通知。托盘悬停提示会直接显示
Bark、飞书各自的模式及飞书遥控状态；飞书命令修改配置后也会立即刷新。

## 飞书远程控制

飞书通知与飞书远程控制是两个独立开关。即使飞书通知模式设为关闭，远程控制
仍会保持 WebSocket 长连接，因此可以从飞书恢复通知；它不再轮询消息历史。

```text
/notify on|ssh|off
/notify status
/notify bark on|ssh|off|status
/notify feishu on|ssh|off|status
```

`on` 将模式设为全部通知，`ssh` 将模式设为仅 SSH，`off` 将模式设为关闭。
模式本身就是通知开关，不再有单独的“启用渠道”配置。飞书远程控制始终独立，
不会被 `off` 关闭。`/notify status` 会回复两个渠道的模式和远程控制状态。

控制器只接受配置的 `open_id` 在配置私聊中的命令。WebSocket 只接收启动后的
新事件，不会重放历史 `/notify` 命令；重复事件也只处理一次。需要在飞书开放
平台订阅 `im.message.receive_v1` 并发布应用。

## 支持的事件

| Agent | 权限申请 | 结构化提问 | 本轮完成 |
| --- | --- | --- | --- |
| Codex | 原生 `PermissionRequest` | 原生 `PreToolUse(request_user_input)` | 原生 `Stop` |
| Claude Code | 原生 `PermissionRequest` | `AskUserQuestion` 的 `PreToolUse` 与 MCP `Elicitation` | 原生 `Stop` |

Codex 将结构化提问暴露为内置 `request_user_input` 工具。Agents-Notify 通过
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
  "config_version": "1.0.4",
  "providers": {
    "bark": {
      "mode": "all",
      "server": "https://api.day.app",
      "device_key": "YOUR_BARK_DEVICE_KEY",
      "group": "Agents-Notify",
      "url": "chatgpt://codex",
      "icon": "https://raw.githubusercontent.com/ancespio/Agents-Notify/master/assets/agents-notify.png",
      "timeout": 8
    },
    "feishu": {
      "control_enabled": false,
      "mode": "off",
      "app_id": "",
      "app_secret": "",
      "open_id": "",
      "chat_id": "",
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
`agents-notify.png` 的 SHA-256 一致。Hook 运行时不会重复联网预检，以免阻塞
Agent；只有手动校验和 Bark 测试通知会执行完整校验。

Windows 程序、托盘、安装器和 Bark 通知默认使用 Agents-Notify 自有图标：
浅色底、深色通知铃、白色终端符号与珊瑚色提醒点。

## 升级迁移

- 从旧版 `Agent-Notify` 升级时，首次运行会将
  `%APPDATA%\Agent-Notify\config.json` 复制到新的
  `%APPDATA%\Agents-Notify\config.json`。
- Bark Key、飞书身份、通知模式、遥控状态和 Agent Hook 选择保持不变；旧目录
  留作回退副本，不再作为运行时配置源。
- 旧官方图标地址、Hook 可执行文件路径和登录自启动项会更新为
  `Agents-Notify`；自定义图标地址保持不变。
- 沿用原 Inno Setup AppId，因此覆盖升级可以继续使用旧物理安装目录；全新安装
  默认使用 `C:\Program Files\Agents-Notify`。
- v1.0.2 加载含旧字段或旧默认值的配置时会创建时间戳备份；迁移可重复执行且
  不会重复修改已完成迁移的配置。
- 旧 `enabled=false` 会迁移为 `mode=off`；`enabled=true` 会保留有效模式，
  缺少模式时使用 `all`，随后删除 `enabled`。
- 仅将精确旧默认 `chatgpt://` 和 v1.0.0/v1.0.1/v1.0.2 图标迁移为
  `master` 图标地址；
  用户自定义跳转和图标保持不变。
- 旧版顶层 `open_id`、`chat_id` 会迁移到飞书 provider。
- 旧 `mode.json` 会在首次运行时迁移为 Bark 与飞书各自的模式。
- 迁移后所有运行状态均写入 `config.json`。
- Agents-Notify 不会新增 `AGENTS.md` 内容，只清理新旧品牌的历史标记区块。

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
iscc installer\Agents-Notify.iss
```

最终安装包生成在：

```text
dist-installer\Agents-Notify-Setup-v1.0.4.exe
```

## 常见问题

- Bark Key 无法查看：v1.0.2 使用隐藏/明文双文本框切换；旧版动态修改
  `TE_PASSWORD` 的方式在 Windows 上无效。
- 图标校验失败：确认 URL 直接返回图片而非 HTML，文件不超过 2 MB，尺寸在
  64 到 4096 像素之间。
- 没有 Bark 通知：检查 Key 是否正确，以及模式是否为关闭。
- 托盘 Bark 测试失败：托盘会显示简短原因，完整脱敏日志位于
  `%APPDATA%\Agents-Notify\agents-notify.log`。
- `open_id` 未知：从飞书事件数据或通讯录 API 获取用户的 `open_id`，不要填写邮箱、
  手机号或其他类型的用户 ID。
- `chat_id` 为空：点击“发送测试消息并生成 chat_id”；它由响应自动建立，不需要查询。
- 没有飞书通知：确认 App ID/App Secret、`open_id`、消息权限和连接测试均正确。
- 飞书命令无响应：确认远程控制开关已开启，且消息来自配置的用户私聊。
- 修改 Hook 后无效果：重启 Codex 或 Claude Code；Codex 还需在 `/hooks`
  中信任 Agents-Notify Hook。
- 托盘没有出现：双击 `Agents-Notify.exe` 保存设置，或重新登录 Windows。

## 远程批准限制

Bark 不提供自定义“允许”和“拒绝”通知按钮，因此 Agents-Notify v1.0.4 中 Bark 仍只负责通知，
批准操作仍需在 Codex 或 Claude Code 中完成。Codex 官方的 `PermissionRequest` Hook
目前只适合观测和播报；官方 `codex app-server` 另有实验性的双向 JSON-RPC 审批协议，
但 Agents-Notify 当前尚未接入该协议。Apple Watch 是否镜像 Bark
通知取决于 iPhone 与 Apple Watch 的通知设置。

## 许可证

Agents-Notify 使用 MIT License，详见 `LICENSE`。
