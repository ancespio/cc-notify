# Codex Agent-Notify 测试提示词

在 **Plan mode** 新线程中粘贴以下内容：

```text
这是 Agent-Notify 的完整通知测试。不要修改、创建或删除任何文件。

请严格按以下顺序执行：

1. 使用 shell_command 发起一次明确的权限申请，命令为：
   Get-Date
   必须设置 sandbox_permissions=require_escalated，并将 justification 写为：
   “允许执行 Agent-Notify 权限通知测试吗？”

2. 权限请求处理后，使用 request_user_input 发出一个结构化单选题：
   标题：通知测试
   问题：你在 iPhone 上收到了 Agent-Notify 的提问通知吗？
   选项：
   - 收到了
   - 没收到

3. 等我选择后，只回复：
   Agent-Notify 三阶段测试完成。

不要执行其他工具，不要提前结束对话。
```

预期依次收到：

1. `Codex 需要授权`
2. `Codex 正在提问`
3. `Codex 本轮完成`
