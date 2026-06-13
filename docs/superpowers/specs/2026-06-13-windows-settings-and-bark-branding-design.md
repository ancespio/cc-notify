# Agent-Notify 2.2.0 设置界面与 Bark 品牌设计

## 目标

将 Agent-Notify 从“主要由 Hook 调用的命令行程序”补全为可直接使用的
Windows 应用，同时统一 Windows 与 iPhone 通知中的 Bark 图标，并让用户在
安装完成后随时修改 Bark 与 Hook 配置。

## 程序入口

`Agent-Notify.exe` 继续承担单文件入口，但根据参数执行不同职责：

- 无参数双击：打开原生设置窗口。
- `--hook`：静默处理 Codex 或 Claude Code Hook。
- `--tray`：启动通知区域图标。
- 安装、卸载、测试和自启动参数：执行对应后台操作后退出。

程序使用 PyInstaller 的无控制台模式构建。Hook 与托盘不得弹出命令行窗口，
双击程序也不得出现一闪而过的控制台。

设置模块采用 wxPython，并由无参数入口延迟导入。Hook 路径不加载 wxPython，
避免增加每次 Hook 通知的启动负担。

## 设置窗口

设置窗口提供以下字段：

- Bark Key，默认隐藏，可切换显示。
- Bark 服务器。
- 点击通知跳转地址，默认 `chatgpt://`。
- Bark 通知图标 URL。
- Codex Hook 开关。
- Claude Code Hook 开关。

窗口提供以下操作：

- “保存并应用”：保存配置，并根据当前 Agent 选择安装或移除对应 Hook。
- “发送测试通知”：先保存当前 Bark 配置，再发送测试通知。
- “关闭”：关闭设置窗口，不影响托盘和 Hook。

窗口底部显示：

- 程序安装目录。
- 用户配置路径 `%APPDATA%\Agent-Notify\config.json`。
- 最近一次操作状态。

重新打开窗口时读取已有配置。Agent 选择也持久化，不能每次都无条件恢复为
全部选中。

## 托盘与安装器

托盘菜单新增“打开设置”，通过无参数启动当前 `Agent-Notify.exe` 打开设置
窗口。托盘进程仍然只负责状态、测试通知、自启动和设置入口；Hook 通知不依赖
托盘常驻。

安装器继续允许用户选择安装目录，默认目录为：

```text
C:\Program Files\Agent-Notify
```

安装器完成后：

- 创建开始菜单“Agent-Notify 设置”快捷方式。
- 启动托盘进程。
- 启用当前用户登录自启动。
- 安装所选 Agent Hook。

重复运行安装器仍可升级和修改配置，但日常修改应优先使用设置窗口。

## ChatGPT 跳转

Bark 的默认 `url` 改为：

```text
chatgpt://
```

该方案以打开 ChatGPT iOS App 为优先，不提供网页回退。用户未安装 ChatGPT
或系统不识别该 URL Scheme 时，点击通知可能没有响应。设置窗口和安装器都允许
用户改回 HTTPS 地址或填写其他自定义地址。

本版本不尝试生成具体 Codex 线程深链。

## Bark 图标

Windows EXE、托盘、安装器和卸载项统一使用 Bark 官方应用图标：

```text
https://raw.githubusercontent.com/Finb/Bark/master/Bark/Assets.xcassets/AppIcon.appiconset/bark.png
```

构建时将该 PNG 固化为项目资源，并生成 Windows ICO。运行时不依赖网络加载
Windows 图标。

Bark 推送的默认 `icon` 使用上述公网 PNG 地址。Bark 会在 iPhone 端缓存相同
图标 URL。用户可在设置窗口覆盖该地址。

Bark 项目采用 MIT 许可证。项目中保留 Bark LICENSE 副本和图标来源说明。

## 配置兼容

配置继续保存在：

```text
%APPDATA%\Agent-Notify\config.json
```

默认值调整为：

```json
{
  "providers": {
    "bark": {
      "url": "chatgpt://",
      "icon": "https://raw.githubusercontent.com/Finb/Bark/master/Bark/Assets.xcassets/AppIcon.appiconset/bark.png"
    }
  },
  "agents": {
    "codex": true,
    "claude": true
  }
}
```

旧配置中缺失或为空的 `url`、`icon` 使用新默认值。已有非空自定义值保持不变。
Bark Key 不写入日志、命令行或 Hook 输出。

## 错误处理

- Hook 通知继续 fail-open，任何设置、网络或 provider 错误都不能阻塞 Agent。
- 设置窗口保存失败时显示错误对话框，不覆盖有效配置。
- 测试通知失败时保留配置，并显示可读错误。
- Hook 更新前继续创建带时间戳的配置备份。
- 图标资源缺失时构建必须失败，不生成使用临时图标的发布包。

## 测试与验收

- 无参数入口打开设置窗口，`--hook` 不打开窗口。
- 发布 EXE 为无控制台程序。
- 设置窗口可读写 Bark Key、服务器、跳转地址、图标 URL 和 Agent 选择。
- 保存后可新增或移除单个 Agent Hook，且不会破坏其他 Hook。
- 托盘“打开设置”启动同一个 EXE。
- 默认 Bark 请求体包含 `chatgpt://` 和官方 Bark 图标 URL。
- EXE、托盘、安装器和卸载项使用同一 Bark 图标。
- 默认安装目录与实际配置路径在 README 和设置窗口中明确显示。
- 旧配置迁移、网络失败和重复安装保持安全。
- Windows 冻结 EXE 的设置、Hook、托盘和测试通知入口分别通过冒烟测试。
