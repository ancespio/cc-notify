# Bark 点击跳转 Codex 设计

## 目标

让每条 Agent-Notify Bark 通知在点击后打开 Codex，同时保留可靠的网页
回退能力，并允许用户自行修改跳转地址。

## 行为

- Bark 通知默认跳转到 `https://chatgpt.com/codex`。
- Windows 安装器显示“点击通知跳转”字段，并预填默认地址。
- 桌面配置程序提供相同字段。
- 非空的自定义地址保存到 `config.json` 的
  `providers.bark.url`。
- 字段留空时恢复默认 Codex 地址。
- Bark 通知通过官方支持的 `url` 参数携带跳转地址。

## 深链边界

本版本不生成 `codex://threads/<session UUID>`。OpenAI 已记录该协议可由
Codex App 打开，但没有保证 iOS 上的 ChatGPT 会处理它。HTTPS Codex
地址在系统支持时可以作为 Universal Link 打开 App，否则会安全地回退到
浏览器。

本次跳转不定位具体线程。只有在 OpenAI 公布受支持的移动端线程链接格式后，
才考虑将本地 Hook 的会话 UUID 映射为移动端 Codex 线程。

## 兼容性

已有配置中明确设置的 Bark URL 保持不变。已有配置缺少 URL 或 URL 为空时，
在重新保存设置或再次安装后写入默认 Codex 地址。

通知仍采用 fail-open。用户填写的自定义地址无效时，不阻塞 Codex 或
Claude Code 的 Hook 执行。

## 测试

- 默认配置包含 `https://chatgpt.com/codex`。
- Bark 请求体包含配置的 `url`。
- 桌面设置可以保存默认或自定义跳转地址。
- 安装请求可以持久化跳转地址。
- 安装器显示该字段并递增应用版本。
- README 使用中文说明点击行为、浏览器回退和暂不支持具体线程深链。
