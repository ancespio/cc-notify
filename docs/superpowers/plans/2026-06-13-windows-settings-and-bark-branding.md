# Agent-Notify 2.2.0 设置界面与 Bark 品牌实施计划

> **供智能体执行：** 必须使用 `superpowers:subagent-driven-development`
>（推荐）或 `superpowers:executing-plans` 按任务逐项实施。步骤使用
> `- [ ]` 复选框跟踪。

**目标：** 提供可双击打开的 wxPython 设置窗口，统一使用 Bark 官方图标，
并将 Bark 默认跳转改为 `chatgpt://`。

**架构：** 配置与 Hook 修改集中在 `agent_notify.desktop`，wxPython 界面只
采集和展示数据。`desktop_hook.py` 根据参数路由，只有无参数或
`--settings-smoke-test` 时延迟导入 GUI；Hook 和托盘路径保持轻量静默。

**技术栈：** Python 3.13、wxPython 4.2、PyInstaller、pystray、Pillow、
Inno Setup 6、`unittest`。

---

### 任务 1：配置默认值与 Agent 选择持久化

**文件：**
- 修改：`agent_notify/config.py`
- 修改：`agent_notify/desktop.py`
- 修改：`tests/test_runtime.py`
- 修改：`tests/test_desktop.py`
- 修改：`tests/test_providers.py`

- [ ] **步骤 1：编写失败测试**

断言默认配置包含：

```python
self.assertEqual(bark["url"], "chatgpt://")
self.assertEqual(bark["icon"], DEFAULT_BARK_ICON_URL)
self.assertTrue(config["agents"]["codex"])
self.assertTrue(config["agents"]["claude"])
```

断言保存函数可以持久化 Bark Key、服务器、URL、图标和 Agent 选择，并且
空 URL、空图标恢复默认值。

- [ ] **步骤 2：运行相关测试并确认失败**

```powershell
python -m unittest tests.test_runtime tests.test_desktop tests.test_providers -v
```

预期：旧默认 URL、空图标和缺少 `agents` 配置导致失败。

- [ ] **步骤 3：实现配置与 Hook 同步服务**

增加常量：

```python
DEFAULT_BARK_URL = "chatgpt://"
DEFAULT_BARK_ICON_URL = (
    "https://raw.githubusercontent.com/ancespio/Agent-Notify/"
    "v1.0.0/assets/agent-notify.png"
)
```

将 `save_bark_settings` 扩展为保存 `icon`、`codex` 和 `claude`。新增
`sync_hooks`：选中的 Agent 安装 Agent-Notify Hook，未选中的 Agent 只移除
Agent-Notify 自己的 Hook。`apply_install_request` 复用同一服务。

- [ ] **步骤 4：重新运行测试并确认通过**

运行步骤 2 的命令，预期全部通过。

### 任务 2：wxPython 设置窗口和入口路由

**文件：**
- 重写：`desktop_app.py`
- 修改：`desktop_hook.py`
- 修改：`agent_notify/tray_app.py`
- 修改：`tests/test_cli.py`
- 修改：`tests/test_tray_app.py`
- 新建：`tests/test_desktop_app.py`

- [ ] **步骤 1：编写入口和 UI 模型失败测试**

断言：

```python
desktop_hook.main([])  # 调用 run_settings_app()
desktop_hook.main(["--hook"])  # 不调用 GUI
```

为设置表单提取可测试的 `SettingsValues` 数据类和保存函数，断言字段完整、
安装目录与配置路径可展示。

- [ ] **步骤 2：运行测试并确认失败**

```powershell
python -m unittest tests.test_cli tests.test_tray_app tests.test_desktop_app -v
```

预期：无参数入口尚未打开设置，托盘没有设置命令，wxPython 界面尚未实现。

- [ ] **步骤 3：实现 wxPython 设置窗口**

窗口包含 Bark Key、显示 Key、服务器、跳转地址、通知图标 URL、Codex 和
Claude Code 复选框，以及“保存并应用”“发送测试通知”“关闭”按钮。

保存动作调用配置与 Hook 同步服务；测试通知在线程中发送，并通过
`wx.CallAfter` 更新 UI。状态区显示安装目录和配置路径。

- [ ] **步骤 4：实现入口与托盘菜单**

`desktop_hook.py` 无参数时延迟导入 `desktop_app.run_app`。新增
`--settings-smoke-test`，用于创建并销毁真实窗口。托盘菜单增加“打开设置”，
以无参数方式启动当前 EXE。

- [ ] **步骤 5：运行相关测试并确认通过**

运行步骤 2 的命令，预期全部通过。

### 任务 3：Agent-Notify 自有图标

**文件：**
- 新建：`assets/agent-notify.svg`
- 新建：`assets/agent-notify.png`
- 修改：`build_windows.py`
- 修改：`agent_notify/tray_app.py`
- 修改：`tests/test_build_windows.py`
- 修改：`tests/test_packaging.py`

- [x] **步骤 1：生成自有图标**

使用确定性 SVG 与 Pillow 脚本生成浅色底、深色通知铃、白色终端符号和珊瑚色
提醒点，不使用亮绿色强调。

```text
https://raw.githubusercontent.com/ancespio/Agent-Notify/v1.0.0/assets/agent-notify.png
```

- [x] **步骤 2：编写资源测试**

断言图标存在、可由 Pillow 打开、尺寸非零，构建脚本从该 PNG 生成 ICO，
托盘从相同 PNG 创建图像。

- [x] **步骤 3：运行测试**

```powershell
python -m unittest tests.test_build_windows tests.test_packaging tests.test_tray_app -v
```

- [x] **步骤 4：实现统一图标**

`build_windows.py` 将 `assets/agent-notify.png` 转为多尺寸 ICO，并以
`--add-data` 打包 PNG。托盘通过运行时资源路径加载自有 PNG，并在通知关闭时
转为灰度显示。

- [x] **步骤 5：运行相关测试并确认通过**

运行步骤 3 的命令，预期全部通过。

### 任务 4：安装器、无控制台构建与中文文档

**文件：**
- 修改：`installer/Agent-Notify.iss`
- 修改：`build_windows.py`
- 修改：`README.md`
- 修改：`config.example.json`
- 修改：`tests/test_packaging.py`

- [ ] **步骤 1：编写安装器失败测试**

断言版本为 `2.2.0`，默认 URL 为 `chatgpt://`，包含图标 URL 字段、开始菜单
设置快捷方式和 `SetupIconFile`，构建参数使用 `--windowed` 而非 `--console`。

- [ ] **步骤 2：运行测试并确认失败**

```powershell
python -m unittest tests.test_packaging -v
```

- [ ] **步骤 3：更新安装器和构建**

安装器增加“Bark 通知图标”字段，创建开始菜单设置快捷方式，使用 Bark ICO，
版本提升到 `2.2.0`。PyInstaller 改用无控制台模式。

- [ ] **步骤 4：更新中文 README 和示例配置**

明确：

- 默认安装目录 `C:\Program Files\Agent-Notify`，用户可在安装器修改。
- 配置路径 `%APPDATA%\Agent-Notify\config.json`。
- 双击 EXE 或托盘“打开设置”可修改 Bark Key 等配置。
- 默认 `chatgpt://` 只保证优先唤起 App，不提供网页回退。
- Bark 图标来源和 MIT 许可。

- [ ] **步骤 5：运行完整单元测试和静态检查**

```powershell
python -m unittest discover -s tests -v
git diff --check
```

### 任务 5：冻结构建和端到端验证

**文件：**
- 构建：`dist/Agent-Notify.exe`
- 构建：`dist-installer/Agent-Notify-Setup.exe`
- 发布：`../../outputs/Agent-Notify-Setup.exe`

- [ ] **步骤 1：构建单文件 EXE**

```powershell
python build_windows.py
```

- [ ] **步骤 2：执行冻结入口冒烟**

```powershell
dist\Agent-Notify.exe --smoke-test
dist\Agent-Notify.exe --settings-smoke-test
```

预期两个命令退出码均为 0，且不出现控制台窗口。

- [ ] **步骤 3：执行隔离配置与 Hook 验证**

使用临时 `--home`、`--config` 和安装请求，验证 Codex/Claude Hook 可分别
启用和移除，配置写入 `chatgpt://` 与 Bark 图标 URL。

- [ ] **步骤 4：编译 2.2.0 安装器**

```powershell
build\inno-setup\ISCC.exe installer\Agent-Notify.iss
```

- [ ] **步骤 5：复制发布包并核验**

```powershell
Copy-Item dist-installer\Agent-Notify-Setup.exe ..\..\outputs\Agent-Notify-Setup.exe -Force
Get-FileHash ..\..\outputs\Agent-Notify-Setup.exe -Algorithm SHA256
```

确认安装包版本为 `2.2.0`，最终测试全部通过。
