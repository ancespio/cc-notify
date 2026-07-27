# Agents-Notify 重建说明

## 重建来源

v1.0.4 在保留既有 Git 历史的基础上，根据以下材料重建并复核：

1. v1.0.2 的 Agents-Notify 源码、测试和安装器定义。
2. 已核验的 Codex、Claude Code 与飞书开放平台接口约束。
3. 脱敏后的本地联调结果和回归测试。

构建产物、运行时配置、日志、迁移备份和本地试验素材不会进入公开仓库。

## 当前实现

- 产品名、Python 包和默认图标统一为 `Agents-Notify`。
- Codex 支持 `PermissionRequest`、`PreToolUse(request_user_input)` 和 `Stop`。
- Claude Code 支持 `PermissionRequest`、`AskUserQuestion` 的 `PreToolUse`、MCP `Elicitation` 和 `Stop`。
- Bark 与飞书通知各自只有 `all`、`ssh-only`、`off` 三种模式。
- 飞书遥控由 `control_enabled` 独立控制，关闭通知后仍可恢复通知。
- 飞书遥控通过官方 `lark-oapi` WebSocket 长连接接收 `im.message.receive_v1`，不再轮询消息历史；飞书通知、连接测试和命令回复通过同一 SDK 调用 HTTP OpenAPI。
- 配置使用锁、备份和原子替换；旧单数品牌目录和旧 `mode.json` 只作为一次性迁移源。
- Hook 失败采用 fail-open，诊断日志必须脱敏。
- 不写入 `AGENTS.md` 提问兜底，也不提供 Bark/Apple Watch 直接审批。

## 运行入口

```powershell
# 运行 Hook：从 stdin 读取 Codex 或 Claude Code Hook JSON
python desktop_hook.py --hook

# 打开设置页
python desktop_hook.py

# 启动托盘
python desktop_hook.py --tray

# 运行测试
python -m unittest discover -s tests -v
```

飞书通知与遥控需要 `lark-oapi` 和企业自建应用的 App ID/App Secret；不再要求用户
安装、初始化或登录外部 `lark-cli`。设置页通过 App ID/App Secret 和 `open_id`
发送测试消息，并从响应保存 `chat_id`。
