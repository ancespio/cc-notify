# 当前待改进项

以下项目根据项目复盘和本次重建审查整理，不代表当前版本已经实现。

## P0：可靠性与安全

### 1. 建立真实 Hook 回放夹具

当前测试覆盖了已知字段，但仍主要依赖手工构造的 JSON。应分别保存脱敏的 Codex 与 Claude Code 真实事件样本，覆盖 Windows 本地、SSH、自动审核、拒绝、超时、工具多次调用和多工作区场景，并在每次升级 Agent 后回放。

### 2. 引入事件身份、幂等和去重

当前通知以单个 Hook 事件为单位发送，尚未建立稳定的 `session_id`、`turn_id`、`tool_call_id` 与事件指纹。需要增加幂等键、短期去重缓存和通知合并，避免同一个权限请求因为重试或多 Hook 配置重复推送。

### 3. 重新设计凭据存储

配置文件目前只保证不进入仓库，Bark Key 和飞书身份仍可能以明文存在用户配置目录。Windows 版本应优先使用 Credential Manager，macOS 使用 Keychain；配置文件只保存引用和非敏感选项。

### 4. 完成安装包安全发布链路

当前构建依赖本机 PyInstaller/Inno Setup，安装包未形成可重复构建、代码签名、哈希发布和升级回滚闭环。正式发布前应加入签名证书、构建清单、SBOM、Release 校验和失败回滚。

## P1：通知质量与运维

### 5. 自动审核降噪需要事件级方案

Codex 的 `PermissionRequest` 在自动审核作出决定前触发，Hook 本身没有稳定的“最终已自动批准”字段。简单 `sleep(3)` 会阻塞 Agent；用 `PostToolUse` 抵消又会把长时间运行的命令误判为未批准。当前版本不实现延迟判断，后续应等待官方结果事件，或读取有明确契约的会话事件后再做可取消的异步通知。当前官方候选是 `codex app-server` 的双向 JSON-RPC，而不是 Hook 输出。

### 6. 增加投递状态和重试策略

Bark/飞书发送目前采用 fail-open，适合不阻塞 Agent，但用户无法区分“未配置、网络失败、服务拒绝、Hook 未触发”。应增加脱敏的本地投递队列、指数退避、最大重试次数和托盘诊断页，同时保持 Hook 主线程快速返回。

### 7. [已完成] 移除 lark-cli 与 Shell 差异

飞书通知、连接测试和命令回复已统一使用 `lark-oapi` 的 HTTP OpenAPI，远程控制继续
使用同一 SDK 的 WebSocket 长连接。设置页不再要求安装、初始化或登录外部 `lark-cli`。

### 8. 提升托盘生命周期稳定性

托盘需要覆盖 Explorer 重启、登录自启动竞态、设置保存重启、升级覆盖和旧进程退出失败。应增加 Windows Explorer 重建后的图标恢复测试、单实例监控、健康状态和明确的退出码，避免出现进程仍在但图标消失的情况。

## P2：产品能力

### 9. 远程批准需要独立的安全通道

Bark 没有自定义“允许/拒绝”按钮，不能把普通 URL 当作审批协议。后续若实现远程批准，应使用短时一次性令牌、HTTPS、签名请求、过期时间、审计记录和明确的 allow/deny 回执；不应把凭据或长期权限放入通知 URL。

飞书审批卡片预留完整选项：`拒绝`、`允许一次`、`永久允许`、`忽略`。风险说明
不做本地关键词猜测；只有 Codex/Claude 原生事件提供解释字段时才展示，否则直接
展示工具名、命令或输入摘要。当前阶段只完成消息长连接，尚未把飞书决定回写到
Codex 或 Claude Code。已确认 Codex app-server 的正式候选流程：服务端发送
`item/commandExecution/requestApproval` 或 `item/fileChange/requestApproval`，客户端
用同一个 JSON-RPC 请求 `id` 返回 `decision`；但 app-server 当前属于实验性/开发调试
接口，仍需按本机版本生成 schema 并实现单独的本地 broker，不能把 `PermissionRequest`
Hook 当成异步回写接口。

### 10. 完善跨平台支持

当前托盘和安装器重点面向 Windows。macOS 需要 LaunchAgent、Keychain、菜单栏应用和签名；Linux/SSH 场景需要 systemd 或用户级后台服务，并分别验证终端编码和路径规则。

### 11. 建立持续集成和回归门禁

当前单元测试已在本机运行通过。后续应加入 Windows/macOS 矩阵、Python 版本矩阵、静态检查、敏感信息扫描、构建产物 smoke test 和真实 Hook fixture 回放；真实 Bark/飞书联调必须使用隔离账号，不把个人凭据放进 CI。

### 12. 收敛文档与发布自动化

安装器、README、测试提示词和 Release 说明应由同一版本元数据生成，减少版本号、安装包名、图标地址和哈希漂移。历史设计文档继续保留，但必须明确标记为历史，不能成为当前行为的第二份规范。

## 暂不处理

- 不在 Hook 内加入固定 3 秒睡眠。
- 不通过 `AGENTS.md` 模拟 Codex 结构化提问。
- 不在 Bark 或 Apple Watch 上伪造原生审批按钮。
- 不把个人飞书 `open_id`、`chat_id`、Bark Key 或本机路径写入示例、测试和公开历史。
