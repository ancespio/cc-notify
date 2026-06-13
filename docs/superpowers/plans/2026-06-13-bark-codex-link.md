# Bark 点击跳转 Codex 实施计划

> **供智能体执行：** 必须使用 `superpowers:subagent-driven-development`
>（推荐）或 `superpowers:executing-plans` 按任务逐项实施。步骤使用
> `- [ ]` 复选框跟踪。

**目标：** 让 Bark 通知默认打开 Codex，并允许用户在安装器和桌面配置程序中修改跳转地址。

**架构：** 在配置模块定义唯一的默认 Codex URL，桌面服务负责将安装请求和
界面值规范化后持久化，现有 Bark provider 继续通过 `url` 字段发送。安装器和
Tkinter 配置界面只负责采集值，不引入线程深链推断。

**技术栈：** Python 3、`unittest`、Tkinter、PyInstaller、Inno Setup 6、Bark HTTP API。

---

### 任务 1：锁定默认 URL 与持久化行为

**文件：**
- 修改：`tests/test_runtime.py`
- 修改：`tests/test_desktop.py`
- 修改：`tests/test_providers.py`
- 修改：`agent_notify/config.py`
- 修改：`agent_notify/desktop.py`

- [ ] **步骤 1：先写失败测试**

在配置测试中断言默认 URL，在桌面服务测试中传入自定义 URL 并断言落盘，在
provider 测试中断言 Bark JSON 请求体包含该 URL：

```python
self.assertEqual(
    config["providers"]["bark"]["url"],
    "https://chatgpt.com/codex",
)

save_bark_settings(
    path,
    "device-key",
    "https://api.day.app",
    "https://example.com/custom",
)
self.assertEqual(
    config["providers"]["bark"]["url"],
    "https://example.com/custom",
)

self.assertEqual(payload["url"], "https://chatgpt.com/codex")
```

- [ ] **步骤 2：运行测试并确认按预期失败**

运行：

```powershell
python -m unittest tests.test_runtime tests.test_desktop tests.test_providers -v
```

预期：因为默认 URL 仍为空且 `save_bark_settings` 尚不接收 URL 参数而失败。

- [ ] **步骤 3：实现最小配置逻辑**

在 `agent_notify/config.py` 增加：

```python
DEFAULT_BARK_URL = "https://chatgpt.com/codex"
```

将 Bark 默认配置的 `url` 改为该常量。将桌面服务签名扩展为：

```python
def save_bark_settings(
    path: Path,
    device_key: str,
    server: str,
    url: str = DEFAULT_BARK_URL,
) -> dict:
```

保存时使用：

```python
bark["url"] = url.strip() or DEFAULT_BARK_URL
```

`apply_install_request` 将请求中的 `url` 传给该函数。

- [ ] **步骤 4：重新运行测试并确认通过**

运行同一步骤 2，预期全部通过。

### 任务 2：接入 Windows 配置界面与安装器

**文件：**
- 修改：`desktop_app.py`
- 修改：`installer/Agent-Notify.iss`
- 修改：`tests/test_packaging.py`

- [ ] **步骤 1：先写安装器失败测试**

断言安装器版本、字段标题、默认地址和请求 JSON 均已更新：

```python
self.assertIn('#define AppVersion "2.1.1"', script)
self.assertIn("点击通知跳转", script)
self.assertIn("https://chatgpt.com/codex", script)
self.assertIn('","url":"', script)
```

- [ ] **步骤 2：运行测试并确认按预期失败**

运行：

```powershell
python -m unittest tests.test_packaging -v
```

预期：当前安装器仍为 2.1.0，且没有跳转地址字段。

- [ ] **步骤 3：实现界面与安装器字段**

桌面配置程序增加 `url_var`，显示“点击通知跳转”输入框，并在保存时传入 URL。
安装器 Bark 页面增加第三个输入框，默认值和可选参数如下：

```pascal
BarkPage.Add('点击通知跳转：', False);
BarkPage.Values[2] := ExpandConstant(
  '{param:BARKURL|https://chatgpt.com/codex}'
);
```

安装请求 JSON 增加：

```pascal
'","url":"' + JsonEscape(BarkPage.Values[2]) +
```

将版本提升到 `2.1.1`。

- [ ] **步骤 4：运行安装器与完整单元测试**

```powershell
python -m unittest discover -s tests -v
```

预期：全部通过。

### 任务 3：更新中文文档与示例配置

**文件：**
- 修改：`README.md`
- 修改：`config.example.json`

- [ ] **步骤 1：更新示例配置**

将示例中的 URL 改为：

```json
"url": "https://chatgpt.com/codex"
```

- [ ] **步骤 2：将 README 改为中文**

保留现有安装、托盘、事件、构建和限制说明，新增：

- 点击 Bark 通知默认进入 `https://chatgpt.com/codex`。
- 系统支持 Universal Link 时可能打开 ChatGPT，否则进入浏览器。
- 可在安装器或桌面配置程序修改地址。
- 本版本不生成具体线程的 `codex://threads/<session UUID>` 深链。

- [ ] **步骤 3：检查品牌和文档内容**

```powershell
rg -n "cc-notify|url.*\"\"" README.md config.example.json agent_notify
```

预期：除明确迁移说明外没有旧品牌，示例和默认配置不再使用空 URL。

### 任务 4：构建并验证 2.1.1 安装包

**文件：**
- 构建产物：`dist/Agent-Notify.exe`
- 构建产物：`dist-installer/Agent-Notify-Setup.exe`
- 发布副本：`../../outputs/Agent-Notify-Setup.exe`

- [ ] **步骤 1：运行完整测试和静态检查**

```powershell
python -m unittest discover -s tests -v
git diff --check
```

预期：全部测试通过，且无空白错误。

- [ ] **步骤 2：构建单文件程序**

```powershell
python build_windows.py
```

预期：生成 `dist/Agent-Notify.exe`。

- [ ] **步骤 3：编译安装程序**

```powershell
iscc installer\Agent-Notify.iss
```

预期：生成 `dist-installer/Agent-Notify-Setup.exe`。

- [ ] **步骤 4：执行冻结程序冒烟测试并复制发布包**

```powershell
dist\Agent-Notify.exe --smoke-test
Copy-Item dist-installer\Agent-Notify-Setup.exe ..\..\outputs\Agent-Notify-Setup.exe -Force
Get-FileHash ..\..\outputs\Agent-Notify-Setup.exe -Algorithm SHA256
```

预期：冒烟测试退出码为 0，发布目录包含最新安装包并输出 SHA-256。
