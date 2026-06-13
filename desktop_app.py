#!/usr/bin/env python
"""Agent-Notify native Windows settings application."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import hashlib
import subprocess
import sys
import threading

import wx

from agent_notify.config import (
    DEFAULT_BARK_ICON_URL,
    DEFAULT_BARK_URL,
    load_config,
)
from agent_notify.desktop import (
    app_data_dir,
    connect_feishu,
    save_provider_settings,
    send_test_notification,
    sync_hooks,
    user_home,
)
from agent_notify.feishu_control import LarkCliClient
from agent_notify.icon_validation import (
    IconValidationError,
    validate_icon_url,
)
from agent_notify.resources import resource_path
from agent_notify.tray_app import (
    is_autostart_enabled,
    restart_tray,
    set_autostart,
)


APP_NAME = "Agent-Notify"
DEFAULT_SERVER = "https://api.day.app"
LEGACY_BARK_ICON_PARTS = (
    "githubusercontent.com/Finb/Bark/",
    "githubusercontent.com/Finb/Bark",
)


def legacy_bark_warnings(url: str, icon: str) -> str:
    warnings = []
    if url.strip().casefold() == "chatgpt://codex":
        warnings.append("点击跳转仍使用旧版 chatgpt://codex。")
    if any(part.casefold() in icon.casefold() for part in LEGACY_BARK_ICON_PARTS):
        warnings.append("通知图标仍使用旧版 Bark 官方图标。")
    return " ".join(warnings)


def local_icon_sha256() -> str | None:
    icon_path = resource_path("assets/agent-notify.png")
    if not icon_path.is_file():
        return None
    return hashlib.sha256(icon_path.read_bytes()).hexdigest()


def expected_icon_sha256(url: str) -> str | None:
    if url.strip() != DEFAULT_BARK_ICON_URL:
        return None
    return local_icon_sha256()


class SecretField(wx.Panel):
    def __init__(self, parent: wx.Window, value: str = ""):
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.password_ctrl = wx.TextCtrl(
            self,
            value=value,
            style=wx.TE_PASSWORD,
        )
        self.plain_ctrl = wx.TextCtrl(self, value=value)
        self.plain_ctrl.Hide()
        sizer.Add(self.password_ctrl, 1, wx.EXPAND)
        sizer.Add(self.plain_ctrl, 1, wx.EXPAND)
        self.SetSizer(sizer)
        self._plain_visible = False

    def GetValue(self) -> str:
        control = (
            self.plain_ctrl if self._plain_visible else self.password_ctrl
        )
        return control.GetValue()

    def SetValue(self, value: str) -> None:
        self.password_ctrl.SetValue(value)
        self.plain_ctrl.SetValue(value)

    def show_plain_text(self, visible: bool) -> None:
        source = (
            self.plain_ctrl if self._plain_visible else self.password_ctrl
        )
        target = self.plain_ctrl if visible else self.password_ctrl
        value = source.GetValue()
        insertion_point = source.GetInsertionPoint()
        target.SetValue(value)
        target.SetInsertionPoint(min(insertion_point, len(value)))
        source.Hide()
        target.Show()
        self._plain_visible = visible
        self.Layout()
        target.SetFocus()


@dataclass
class SettingsValues:
    bark_enabled: bool
    device_key: str
    server: str
    url: str
    icon: str
    bark_mode: str
    feishu_enabled: bool
    feishu_control_enabled: bool
    feishu_mode: str
    open_id: str
    chat_id: str
    lark_cli: str
    codex: bool
    claude: bool


def load_settings_values(config_path: Path) -> SettingsValues:
    config = load_config(config_path)
    bark = config["providers"]["bark"]
    feishu = config["providers"]["feishu"]
    agents = config["agents"]
    return SettingsValues(
        bark_enabled=bool(bark.get("enabled", True)),
        device_key=str(bark.get("device_key") or ""),
        server=str(bark.get("server") or DEFAULT_SERVER),
        url=str(bark.get("url") or DEFAULT_BARK_URL),
        icon=str(bark.get("icon") or DEFAULT_BARK_ICON_URL),
        bark_mode=str(bark.get("mode") or "all"),
        feishu_enabled=bool(feishu.get("enabled", False)),
        feishu_control_enabled=bool(
            feishu.get("control_enabled", False)
        ),
        feishu_mode=str(feishu.get("mode") or "all"),
        open_id=str(feishu.get("open_id") or ""),
        chat_id=str(feishu.get("chat_id") or ""),
        lark_cli=str(feishu.get("lark_cli") or default_lark_cli()),
        codex=bool(agents.get("codex", True)),
        claude=bool(agents.get("claude", True)),
    )


def default_lark_cli() -> str:
    if sys.platform == "win32":
        import os

        return str(
            Path(os.environ.get("APPDATA", ""))
            / "npm"
            / "lark-cli.cmd"
        )
    return "lark-cli"


def validate_settings(values: SettingsValues) -> None:
    if values.bark_enabled and not values.device_key.strip():
        raise ValueError("启用 Bark 通知时请填写 Bark Key。")
    if values.feishu_enabled or values.feishu_control_enabled:
        if not values.open_id.strip():
            raise ValueError("启用飞书功能时请填写 open_id。")
        if not values.lark_cli.strip():
            raise ValueError("启用飞书功能时请填写 lark-cli 路径。")


def apply_settings(
    values: SettingsValues,
    config_path: Path,
    home: Path,
    executable: Path,
) -> list[Path]:
    validate_settings(values)
    save_provider_settings(
        config_path,
        bark={
            "enabled": values.bark_enabled,
            "device_key": values.device_key,
            "server": values.server,
            "url": values.url,
            "icon": values.icon,
            "mode": values.bark_mode,
        },
        feishu={
            "enabled": values.feishu_enabled,
            "control_enabled": values.feishu_control_enabled,
            "mode": values.feishu_mode,
            "open_id": values.open_id,
            "chat_id": values.chat_id,
            "lark_cli": values.lark_cli,
        },
        agents={
            "codex": values.codex,
            "claude": values.claude,
        },
    )
    return sync_hooks(
        home,
        executable,
        values.codex,
        values.claude,
    )


def installed_executable() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return Path(__file__).resolve().parent / "dist" / "Agent-Notify.exe"


class SettingsFrame(wx.Frame):
    def __init__(
        self,
        config_path: Path,
        home: Path,
        executable: Path,
    ):
        super().__init__(
            None,
            title=f"{APP_NAME} 设置",
            size=(760, 660),
            style=wx.DEFAULT_FRAME_STYLE & ~wx.RESIZE_BORDER,
        )
        self.config_path = config_path
        self.home = home
        self.executable = executable
        icon_path = resource_path("assets/agent-notify.png")
        if icon_path.is_file():
            self.SetIcon(wx.Icon(str(icon_path), wx.BITMAP_TYPE_PNG))
        values = load_settings_values(config_path)

        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)

        title = wx.StaticText(panel, label=APP_NAME)
        title.SetFont(
            wx.Font(
                20,
                wx.FONTFAMILY_DEFAULT,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_BOLD,
            )
        )
        outer.Add(title, 0, wx.LEFT | wx.RIGHT | wx.TOP, 24)
        subtitle = wx.StaticText(
            panel,
            label="Bark、飞书通知与 Agent Hook 设置",
        )
        subtitle.SetForegroundColour(wx.Colour(95, 99, 104))
        outer.Add(subtitle, 0, wx.LEFT | wx.RIGHT | wx.TOP, 24)

        notebook = wx.Notebook(panel)
        bark_panel = wx.Panel(notebook)
        feishu_panel = wx.Panel(notebook)
        agent_panel = wx.Panel(notebook)
        notebook.AddPage(bark_panel, "Bark")
        notebook.AddPage(feishu_panel, "飞书")
        notebook.AddPage(agent_panel, "Agent 与程序")
        outer.Add(notebook, 1, wx.EXPAND | wx.ALL, 24)

        bark_sizer = wx.BoxSizer(wx.VERTICAL)
        self.bark_enabled = wx.CheckBox(
            bark_panel, label="启用 Bark 通知"
        )
        self.bark_enabled.SetValue(values.bark_enabled)
        bark_sizer.Add(self.bark_enabled, 0, wx.ALL, 12)
        bark_form = self._form()
        self.key_ctrl = SecretField(bark_panel, values.device_key)
        self.show_key = wx.CheckBox(bark_panel, label="显示")
        self.show_key.Bind(wx.EVT_CHECKBOX, self._toggle_key)
        self._add_row(
            bark_form,
            bark_panel,
            "Bark Key",
            self.key_ctrl,
            self.show_key,
        )

        self.server_ctrl = wx.TextCtrl(bark_panel, value=values.server)
        self._add_row(
            bark_form, bark_panel, "Bark 服务器", self.server_ctrl
        )

        self.url_ctrl = wx.TextCtrl(bark_panel, value=values.url)
        self._add_row(
            bark_form, bark_panel, "点击通知跳转", self.url_ctrl
        )

        self.icon_ctrl = wx.TextCtrl(bark_panel, value=values.icon)
        self.url_ctrl.Bind(wx.EVT_TEXT, self._refresh_legacy_warning)
        self.icon_ctrl.Bind(wx.EVT_TEXT, self._refresh_legacy_warning)
        self._add_row(
            bark_form, bark_panel, "通知图标 URL", self.icon_ctrl
        )
        self.bark_mode = self._mode_choice(
            bark_panel, values.bark_mode
        )
        self._add_row(
            bark_form, bark_panel, "通知模式", self.bark_mode
        )
        bark_sizer.Add(bark_form, 0, wx.EXPAND | wx.ALL, 12)
        bark_tools = wx.BoxSizer(wx.HORIZONTAL)
        restore_defaults = wx.Button(
            bark_panel, label="恢复新版默认"
        )
        restore_defaults.Bind(
            wx.EVT_BUTTON, self._on_restore_bark_defaults
        )
        validate_icon = wx.Button(bark_panel, label="校验图标")
        validate_icon.Bind(wx.EVT_BUTTON, self._on_validate_icon)
        self.icon_preview = wx.StaticBitmap(
            bark_panel, size=(64, 64)
        )
        bark_tools.Add(restore_defaults, 0, wx.RIGHT, 8)
        bark_tools.Add(validate_icon, 0, wx.RIGHT, 12)
        bark_tools.Add(self.icon_preview, 0, wx.ALIGN_CENTER_VERTICAL)
        bark_sizer.Add(
            bark_tools, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12
        )
        self.legacy_warning = wx.StaticText(bark_panel, label="")
        self.legacy_warning.SetForegroundColour(wx.Colour(181, 82, 48))
        bark_sizer.Add(
            self.legacy_warning,
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            12,
        )
        bark_test = wx.Button(bark_panel, label="发送 Bark 测试通知")
        bark_test.Bind(wx.EVT_BUTTON, self._on_bark_test)
        bark_sizer.Add(bark_test, 0, wx.LEFT | wx.BOTTOM, 12)
        bark_panel.SetSizer(bark_sizer)

        feishu_sizer = wx.BoxSizer(wx.VERTICAL)
        options = wx.BoxSizer(wx.HORIZONTAL)
        self.feishu_enabled = wx.CheckBox(
            feishu_panel, label="启用飞书通知"
        )
        self.feishu_enabled.SetValue(values.feishu_enabled)
        self.feishu_control = wx.CheckBox(
            feishu_panel, label="启用飞书远程控制"
        )
        self.feishu_control.SetValue(values.feishu_control_enabled)
        options.Add(self.feishu_enabled, 0, wx.ALL, 12)
        options.Add(self.feishu_control, 0, wx.ALL, 12)
        feishu_sizer.Add(options, 0)
        feishu_form = self._form()
        self.lark_cli_ctrl = wx.TextCtrl(
            feishu_panel, value=values.lark_cli
        )
        self._add_row(
            feishu_form,
            feishu_panel,
            "lark-cli 路径",
            self.lark_cli_ctrl,
        )
        self.open_id_ctrl = wx.TextCtrl(
            feishu_panel, value=values.open_id
        )
        self._add_row(
            feishu_form, feishu_panel, "open_id", self.open_id_ctrl
        )
        self.chat_id_ctrl = wx.TextCtrl(
            feishu_panel,
            value=values.chat_id,
            style=wx.TE_READONLY,
        )
        self._add_row(
            feishu_form, feishu_panel, "chat_id", self.chat_id_ctrl
        )
        self.feishu_mode = self._mode_choice(
            feishu_panel, values.feishu_mode
        )
        self._add_row(
            feishu_form, feishu_panel, "通知模式", self.feishu_mode
        )
        feishu_sizer.Add(feishu_form, 0, wx.EXPAND | wx.ALL, 12)
        self.lark_status = wx.StaticText(
            feishu_panel, label="尚未检测 lark-cli 登录状态"
        )
        feishu_sizer.Add(
            self.lark_status, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12
        )
        setup_actions = wx.BoxSizer(wx.HORIZONTAL)
        for label, step in (
            ("1. 安装", "install"),
            ("2. 初始化", "config"),
            ("3. 登录", "login"),
        ):
            button = wx.Button(feishu_panel, label=label)
            button.Bind(
                wx.EVT_BUTTON,
                lambda _event, value=step: self._run_lark_setup(value),
            )
            setup_actions.Add(button, 0, wx.RIGHT, 8)
        detect_button = wx.Button(feishu_panel, label="4. 重新检测")
        detect_button.Bind(wx.EVT_BUTTON, self._on_lark_detect)
        setup_actions.Add(detect_button, 0, wx.RIGHT, 8)
        fetch_open_id = wx.Button(
            feishu_panel, label="自动获取 open_id"
        )
        fetch_open_id.Bind(wx.EVT_BUTTON, self._on_fetch_open_id)
        setup_actions.Add(fetch_open_id, 0)
        feishu_sizer.Add(
            setup_actions, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 12
        )
        connect_button = wx.Button(
            feishu_panel, label="连接并发送测试消息"
        )
        connect_button.Bind(wx.EVT_BUTTON, self._on_feishu_connect)
        feishu_sizer.Add(connect_button, 0, wx.LEFT | wx.BOTTOM, 12)
        feishu_panel.SetSizer(feishu_sizer)

        agent_sizer = wx.BoxSizer(wx.VERTICAL)
        agent_box = wx.StaticBoxSizer(
            wx.HORIZONTAL, agent_panel, "启用 Hook"
        )
        self.codex_check = wx.CheckBox(agent_panel, label="Codex")
        self.codex_check.SetValue(values.codex)
        self.claude_check = wx.CheckBox(
            agent_panel, label="Claude Code"
        )
        self.claude_check.SetValue(values.claude)
        agent_box.Add(self.codex_check, 0, wx.ALL, 10)
        agent_box.Add(self.claude_check, 0, wx.ALL, 10)
        agent_sizer.Add(
            agent_box, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 12
        )
        self.autostart_check = wx.CheckBox(
            agent_panel, label="登录时自动启动托盘"
        )
        self.autostart_check.SetValue(
            is_autostart_enabled(executable)
        )
        agent_sizer.Add(self.autostart_check, 0, wx.ALL, 12)

        paths = wx.StaticBoxSizer(wx.VERTICAL, agent_panel, "位置")
        paths.Add(
            wx.StaticText(
                agent_panel,
                label=f"程序目录：{executable.parent}",
            ),
            0,
            wx.ALL,
            8,
        )
        paths.Add(
            wx.StaticText(
                agent_panel,
                label=f"配置文件：{config_path}",
            ),
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            8,
        )
        agent_sizer.Add(paths, 0, wx.EXPAND | wx.ALL, 12)
        rerun_onboarding = wx.Button(
            agent_panel, label="重新运行配置向导"
        )
        rerun_onboarding.Bind(
            wx.EVT_BUTTON, self._on_rerun_onboarding
        )
        agent_sizer.Add(rerun_onboarding, 0, wx.LEFT | wx.BOTTOM, 12)
        agent_panel.SetSizer(agent_sizer)

        actions = wx.BoxSizer(wx.HORIZONTAL)
        save_button = wx.Button(panel, label="保存并应用")
        save_button.Bind(wx.EVT_BUTTON, self._on_save)
        close_button = wx.Button(panel, label="关闭")
        close_button.Bind(wx.EVT_BUTTON, lambda _event: self.Close())
        actions.Add(save_button, 0)
        actions.AddStretchSpacer()
        actions.Add(close_button, 0)
        outer.Add(
            actions,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            24,
        )

        self.status = wx.StaticText(panel, label="尚未执行操作")
        self.status.Wrap(700)
        outer.Add(
            self.status,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM,
            24,
        )

        panel.SetSizer(outer)
        self._refresh_legacy_warning()
        self.Centre()

    @staticmethod
    def _form() -> wx.FlexGridSizer:
        form = wx.FlexGridSizer(rows=0, cols=3, vgap=12, hgap=12)
        form.AddGrowableCol(1, 1)
        return form

    @staticmethod
    def _mode_choice(parent: wx.Window, value: str) -> wx.Choice:
        choices = wx.Choice(
            parent,
            choices=["全部通知", "仅 SSH", "关闭"],
        )
        choices.SetSelection(
            {"all": 0, "ssh-only": 1, "off": 2}.get(value, 0)
        )
        return choices

    @staticmethod
    def _mode_value(control: wx.Choice) -> str:
        return ("all", "ssh-only", "off")[control.GetSelection()]

    @staticmethod
    def _add_row(
        form: wx.FlexGridSizer,
        panel: wx.Panel,
        label: str,
        control: wx.Window,
        trailing: wx.Window | None = None,
    ) -> None:
        form.Add(
            wx.StaticText(panel, label=label),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )
        form.Add(control, 1, wx.EXPAND)
        form.Add(
            trailing or wx.StaticText(panel, label=""),
            0,
            wx.ALIGN_CENTER_VERTICAL,
        )

    def _toggle_key(self, _event: wx.CommandEvent) -> None:
        self.key_ctrl.show_plain_text(self.show_key.IsChecked())

    def _refresh_legacy_warning(
        self, _event: wx.CommandEvent | None = None
    ) -> None:
        if not hasattr(self, "legacy_warning"):
            return
        warning = legacy_bark_warnings(
            self.url_ctrl.GetValue(),
            self.icon_ctrl.GetValue(),
        )
        self.legacy_warning.SetLabel(
            f"旧版配置提示：{warning}" if warning else ""
        )
        self.legacy_warning.Wrap(650)

    def _on_restore_bark_defaults(
        self, _event: wx.CommandEvent
    ) -> None:
        self.url_ctrl.SetValue(DEFAULT_BARK_URL)
        self.icon_ctrl.SetValue(DEFAULT_BARK_ICON_URL)
        self.status.SetLabel("已恢复新版默认值，保存后生效。")

    def _on_validate_icon(self, _event: wx.CommandEvent) -> None:
        url = self.icon_ctrl.GetValue().strip()
        if not url:
            wx.MessageBox(
                "请填写通知图标 URL。",
                APP_NAME,
                wx.OK | wx.ICON_ERROR,
            )
            return
        self.status.SetLabel("正在下载并校验通知图标...")

        def worker() -> None:
            try:
                result = validate_icon_url(
                    url,
                    expected_sha256=expected_icon_sha256(url),
                )
                wx.CallAfter(self._icon_validated, result, "")
            except Exception as exc:
                wx.CallAfter(self._icon_validated, None, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _icon_validated(self, result, error: str) -> None:
        if error or result is None:
            detail = error or "无法校验图标。"
            self.status.SetLabel(f"图标校验失败：{detail}")
            wx.MessageBox(detail, APP_NAME, wx.OK | wx.ICON_ERROR)
            return
        try:
            image = wx.Image(BytesIO(result.data))
            image.Rescale(64, 64, wx.IMAGE_QUALITY_HIGH)
            self.icon_preview.SetBitmap(wx.Bitmap(image))
        except Exception:
            pass
        self.status.SetLabel(
            f"图标有效：{result.format}，"
            f"{result.size[0]}x{result.size[1]}，"
            f"SHA-256 {result.sha256[:12]}..."
        )

    def _values(self) -> SettingsValues:
        return SettingsValues(
            bark_enabled=self.bark_enabled.IsChecked(),
            device_key=self.key_ctrl.GetValue(),
            server=self.server_ctrl.GetValue(),
            url=self.url_ctrl.GetValue(),
            icon=self.icon_ctrl.GetValue(),
            bark_mode=self._mode_value(self.bark_mode),
            feishu_enabled=self.feishu_enabled.IsChecked(),
            feishu_control_enabled=self.feishu_control.IsChecked(),
            feishu_mode=self._mode_value(self.feishu_mode),
            open_id=self.open_id_ctrl.GetValue(),
            chat_id=self.chat_id_ctrl.GetValue(),
            lark_cli=self.lark_cli_ctrl.GetValue(),
            codex=self.codex_check.IsChecked(),
            claude=self.claude_check.IsChecked(),
        )

    def _save(self) -> list[Path]:
        return apply_settings(
            self._values(),
            self.config_path,
            self.home,
            self.executable,
        )

    def _on_save(self, _event: wx.CommandEvent) -> None:
        try:
            changed = self._save()
            set_autostart(
                self.autostart_check.IsChecked(),
                self.executable,
            )
            restart_tray(self.executable)
        except Exception as exc:
            self.status.SetLabel(f"保存失败：{exc}")
            wx.MessageBox(str(exc), APP_NAME, wx.OK | wx.ICON_ERROR)
            return
        self.status.SetLabel(
            f"配置已保存，共更新 {len(changed)} 个 Hook 配置文件。"
            "托盘已重新加载；请重启已修改的 Agent。"
        )
        wx.MessageBox(
            "配置与 Hook 已更新。",
            APP_NAME,
            wx.OK | wx.ICON_INFORMATION,
        )

    def _on_bark_test(self, _event: wx.CommandEvent) -> None:
        try:
            self._save()
        except Exception as exc:
            self.status.SetLabel(f"保存失败：{exc}")
            wx.MessageBox(str(exc), APP_NAME, wx.OK | wx.ICON_ERROR)
            return
        self.status.SetLabel("正在发送 Bark 测试通知...")

        def worker() -> None:
            try:
                ok = send_test_notification(self.config_path)
                error = ""
            except Exception as exc:
                ok = False
                error = str(exc)
            wx.CallAfter(self._test_finished, ok, error)

        threading.Thread(target=worker, daemon=True).start()

    def _on_feishu_connect(self, _event: wx.CommandEvent) -> None:
        open_id = self.open_id_ctrl.GetValue().strip()
        lark_cli = self.lark_cli_ctrl.GetValue().strip()
        if not open_id or not lark_cli:
            wx.MessageBox(
                "请填写 open_id 和 lark-cli 路径。",
                APP_NAME,
                wx.OK | wx.ICON_ERROR,
            )
            return
        self.status.SetLabel("正在连接飞书并发送测试消息...")

        def worker() -> None:
            try:
                client = LarkCliClient(lark_cli)
                chat_id = connect_feishu(
                    self.config_path,
                    open_id,
                    client,
                )
                wx.CallAfter(self._feishu_connected, chat_id, "")
            except Exception as exc:
                wx.CallAfter(self._feishu_connected, "", str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _run_lark_setup(self, step: str) -> None:
        client = LarkCliClient(self.lark_cli_ctrl.GetValue().strip())
        try:
            command = client.setup_command(step)
            process = subprocess.Popen(command)
        except Exception as exc:
            wx.MessageBox(str(exc), APP_NAME, wx.OK | wx.ICON_ERROR)
            return
        self.lark_status.SetLabel(
            "已打开 PowerShell，请在窗口中完成官方交互流程。"
        )

        def wait_for_setup() -> None:
            process.wait()
            wx.CallAfter(self._refresh_lark_status)

        threading.Thread(target=wait_for_setup, daemon=True).start()

    def _on_lark_detect(self, _event: wx.CommandEvent) -> None:
        self._refresh_lark_status()

    def _refresh_lark_status(self) -> None:
        executable = self.lark_cli_ctrl.GetValue().strip()
        self.lark_status.SetLabel("正在检测 lark-cli...")

        def worker() -> None:
            status = LarkCliClient(executable).auth_status()
            wx.CallAfter(self._lark_status_finished, status)

        threading.Thread(target=worker, daemon=True).start()

    def _lark_status_finished(self, status) -> None:
        if status.authenticated:
            self.lark_status.SetLabel(
                f"已登录：{status.executable}"
            )
        else:
            detail = status.detail or "未安装、未初始化或尚未登录。"
            self.lark_status.SetLabel(f"未就绪：{detail}")

    def _on_fetch_open_id(self, _event: wx.CommandEvent) -> None:
        executable = self.lark_cli_ctrl.GetValue().strip()
        self.lark_status.SetLabel("正在读取当前飞书用户 open_id...")

        def worker() -> None:
            try:
                open_id = LarkCliClient(executable).current_open_id()
                wx.CallAfter(self._open_id_finished, open_id, "")
            except Exception as exc:
                wx.CallAfter(self._open_id_finished, "", str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _open_id_finished(self, open_id: str, error: str) -> None:
        if error:
            self.lark_status.SetLabel(f"自动获取失败：{error}")
            wx.MessageBox(
                "自动获取 open_id 失败。\n\n"
                f"{error}\n\n可手动运行：\n"
                "lark-cli api GET "
                "/open-apis/authen/v1/user_info "
                "--as user --format json",
                APP_NAME,
                wx.OK | wx.ICON_ERROR,
            )
            return
        self.open_id_ctrl.SetValue(open_id)
        self.lark_status.SetLabel(
            "已自动填写 open_id，可在连接前手动修正。"
        )

    def _on_rerun_onboarding(
        self, _event: wx.CommandEvent
    ) -> None:
        try:
            subprocess.Popen([str(self.executable), "--onboarding"])
        except Exception as exc:
            wx.MessageBox(str(exc), APP_NAME, wx.OK | wx.ICON_ERROR)

    def _feishu_connected(self, chat_id: str, error: str) -> None:
        if error:
            self.status.SetLabel(f"飞书连接失败：{error}")
            wx.MessageBox(error, APP_NAME, wx.OK | wx.ICON_ERROR)
            return
        self.chat_id_ctrl.SetValue(chat_id)
        self.status.SetLabel("飞书连接成功，测试消息已发送。")
        wx.MessageBox(
            "飞书连接成功。",
            APP_NAME,
            wx.OK | wx.ICON_INFORMATION,
        )

    def _test_finished(self, ok: bool, error: str) -> None:
        if ok:
            self.status.SetLabel("Bark 测试通知已发送。")
            wx.MessageBox(
                "测试通知已发送，请检查 iPhone。",
                APP_NAME,
                wx.OK | wx.ICON_INFORMATION,
            )
            return
        detail = error or "Bark 服务未返回成功状态。"
        self.status.SetLabel(f"测试失败：{detail}")
        wx.MessageBox(detail, APP_NAME, wx.OK | wx.ICON_ERROR)


class OnboardingFrame(wx.Frame):
    def __init__(
        self,
        config_path: Path,
        home: Path,
        executable: Path,
    ):
        super().__init__(
            None,
            title=f"{APP_NAME} 首次配置向导",
            size=(760, 650),
            style=wx.DEFAULT_FRAME_STYLE & ~wx.RESIZE_BORDER,
        )
        self.config_path = config_path
        self.home = home
        self.executable = executable
        self.page_index = 0
        values = load_settings_values(config_path)
        icon_path = resource_path("assets/agent-notify.png")
        if icon_path.is_file():
            self.SetIcon(wx.Icon(str(icon_path), wx.BITMAP_TYPE_PNG))

        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)
        heading = wx.StaticText(panel, label="Agent-Notify 配置向导")
        heading.SetFont(
            wx.Font(
                18,
                wx.FONTFAMILY_DEFAULT,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_BOLD,
            )
        )
        outer.Add(heading, 0, wx.LEFT | wx.RIGHT | wx.TOP, 24)
        self.progress = wx.StaticText(panel, label="")
        self.progress.SetForegroundColour(wx.Colour(95, 99, 104))
        outer.Add(self.progress, 0, wx.LEFT | wx.RIGHT | wx.TOP, 24)

        self.book = wx.Simplebook(panel)
        outer.Add(self.book, 1, wx.EXPAND | wx.ALL, 24)
        self._build_selection_page(values)
        self._build_bark_page(values)
        self._build_feishu_page(values)
        self._build_agent_page(values)
        self._build_summary_page()

        nav = wx.BoxSizer(wx.HORIZONTAL)
        self.back_button = wx.Button(panel, label="上一步")
        self.next_button = wx.Button(panel, label="下一步")
        self.back_button.Bind(wx.EVT_BUTTON, self._on_back)
        self.next_button.Bind(wx.EVT_BUTTON, self._on_next)
        nav.Add(self.back_button, 0)
        nav.AddStretchSpacer()
        nav.Add(self.next_button, 0)
        outer.Add(nav, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 24)
        self.status = wx.StaticText(panel, label="所有渠道均可跳过。")
        self.status.Wrap(700)
        outer.Add(
            self.status,
            0,
            wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM,
            24,
        )
        panel.SetSizer(outer)
        self._show_page(0)
        self.Centre()

    @staticmethod
    def _page(parent: wx.Window, title: str, description: str):
        page = wx.Panel(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        label = wx.StaticText(page, label=title)
        label.SetFont(
            wx.Font(
                14,
                wx.FONTFAMILY_DEFAULT,
                wx.FONTSTYLE_NORMAL,
                wx.FONTWEIGHT_BOLD,
            )
        )
        sizer.Add(label, 0, wx.BOTTOM, 8)
        detail = wx.StaticText(page, label=description)
        detail.SetForegroundColour(wx.Colour(95, 99, 104))
        detail.Wrap(650)
        sizer.Add(detail, 0, wx.BOTTOM, 18)
        page.SetSizer(sizer)
        return page, sizer

    @staticmethod
    def _row(
        parent: wx.Window,
        sizer: wx.BoxSizer,
        label: str,
        control: wx.Window,
    ) -> None:
        row = wx.BoxSizer(wx.HORIZONTAL)
        text = wx.StaticText(parent, label=label, size=(125, -1))
        row.Add(text, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        row.Add(control, 1, wx.EXPAND)
        sizer.Add(row, 0, wx.EXPAND | wx.BOTTOM, 10)

    def _build_selection_page(self, values: SettingsValues) -> None:
        page, sizer = self._page(
            self.book,
            "1. 选择要配置的功能",
            "Bark、飞书和 Agent Hook 都可以独立选择，也可以全部跳过。",
        )
        self.wizard_bark_enabled = wx.CheckBox(
            page, label="配置并启用 Bark 通知"
        )
        self.wizard_bark_enabled.SetValue(values.bark_enabled)
        self.wizard_feishu_enabled = wx.CheckBox(
            page, label="配置并启用飞书通知"
        )
        self.wizard_feishu_enabled.SetValue(values.feishu_enabled)
        self.wizard_feishu_control = wx.CheckBox(
            page, label="启用飞书远程控制"
        )
        self.wizard_feishu_control.SetValue(
            values.feishu_control_enabled
        )
        self.wizard_codex = wx.CheckBox(
            page, label="安装 Codex Hook"
        )
        self.wizard_codex.SetValue(values.codex)
        self.wizard_claude = wx.CheckBox(
            page, label="安装 Claude Code Hook"
        )
        self.wizard_claude.SetValue(values.claude)
        for control in (
            self.wizard_bark_enabled,
            self.wizard_feishu_enabled,
            self.wizard_feishu_control,
            self.wizard_codex,
            self.wizard_claude,
        ):
            sizer.Add(control, 0, wx.BOTTOM, 12)
        self.book.AddPage(page, "选择")

    def _build_bark_page(self, values: SettingsValues) -> None:
        page, sizer = self._page(
            self.book,
            "2. 配置 Bark",
            "从 iPhone 的 Bark App 复制设备 Key。测试通知发送前会校验远程图标。",
        )
        key_row = wx.BoxSizer(wx.HORIZONTAL)
        key_panel = wx.Panel(page)
        self.wizard_key = SecretField(key_panel, values.device_key)
        self.wizard_show_key = wx.CheckBox(key_panel, label="显示")
        self.wizard_show_key.Bind(
            wx.EVT_CHECKBOX,
            lambda _event: self.wizard_key.show_plain_text(
                self.wizard_show_key.IsChecked()
            ),
        )
        key_row.Add(self.wizard_key, 1, wx.RIGHT, 10)
        key_row.Add(
            self.wizard_show_key, 0, wx.ALIGN_CENTER_VERTICAL
        )
        key_panel.SetSizer(key_row)
        self._row(page, sizer, "Bark Key", key_panel)
        self.wizard_server = wx.TextCtrl(page, value=values.server)
        self.wizard_url = wx.TextCtrl(page, value=values.url)
        self.wizard_icon = wx.TextCtrl(page, value=values.icon)
        self._row(page, sizer, "Bark 服务器", self.wizard_server)
        self._row(page, sizer, "点击通知跳转", self.wizard_url)
        self._row(page, sizer, "通知图标 URL", self.wizard_icon)
        actions = wx.BoxSizer(wx.HORIZONTAL)
        defaults = wx.Button(page, label="恢复新版默认")
        defaults.Bind(wx.EVT_BUTTON, self._wizard_restore_defaults)
        validate = wx.Button(page, label="校验图标")
        validate.Bind(wx.EVT_BUTTON, self._wizard_validate_icon)
        test = wx.Button(page, label="发送测试通知")
        test.Bind(wx.EVT_BUTTON, self._wizard_bark_test)
        actions.Add(defaults, 0, wx.RIGHT, 8)
        actions.Add(validate, 0, wx.RIGHT, 8)
        actions.Add(test, 0)
        sizer.Add(actions, 0, wx.TOP, 4)
        self.book.AddPage(page, "Bark")

    def _build_feishu_page(self, values: SettingsValues) -> None:
        page, sizer = self._page(
            self.book,
            "3. 配置飞书",
            "安装和登录会在可见 PowerShell 中完成。登录后可自动获取 open_id，连接消息会自动建立 chat_id。",
        )
        self.wizard_lark_cli = wx.TextCtrl(
            page, value=values.lark_cli
        )
        self.wizard_open_id = wx.TextCtrl(page, value=values.open_id)
        self.wizard_chat_id = wx.TextCtrl(
            page, value=values.chat_id, style=wx.TE_READONLY
        )
        self._row(page, sizer, "lark-cli 路径", self.wizard_lark_cli)
        self._row(page, sizer, "open_id", self.wizard_open_id)
        self._row(page, sizer, "chat_id", self.wizard_chat_id)
        commands = wx.BoxSizer(wx.HORIZONTAL)
        for label, step in (
            ("1. 安装", "install"),
            ("2. 初始化", "config"),
            ("3. 登录", "login"),
        ):
            button = wx.Button(page, label=label)
            button.Bind(
                wx.EVT_BUTTON,
                lambda _event, value=step: self._wizard_lark_setup(value),
            )
            commands.Add(button, 0, wx.RIGHT, 8)
        detect = wx.Button(page, label="4. 检测并获取 open_id")
        detect.Bind(wx.EVT_BUTTON, self._wizard_fetch_open_id)
        commands.Add(detect, 0)
        sizer.Add(commands, 0, wx.BOTTOM, 10)
        connect = wx.Button(page, label="连接飞书并生成 chat_id")
        connect.Bind(wx.EVT_BUTTON, self._wizard_connect_feishu)
        sizer.Add(connect, 0)
        self.wizard_lark_status = wx.StaticText(
            page, label="尚未检测飞书登录状态。"
        )
        self.wizard_lark_status.Wrap(650)
        sizer.Add(self.wizard_lark_status, 0, wx.TOP, 12)
        self.book.AddPage(page, "飞书")

    def _build_agent_page(self, values: SettingsValues) -> None:
        page, sizer = self._page(
            self.book,
            "4. Agent 与程序",
            "Hook 在保存时安全合并。Agent-Notify 不写入 AGENTS.md，只清理历史标记区块。",
        )
        self.wizard_autostart = wx.CheckBox(
            page, label="登录 Windows 时自动启动托盘"
        )
        self.wizard_autostart.SetValue(
            is_autostart_enabled(self.executable)
        )
        sizer.Add(self.wizard_autostart, 0, wx.BOTTOM, 18)
        location = wx.StaticText(
            page,
            label=(
                f"程序：{self.executable}\n"
                f"配置：{self.config_path}\n"
                f"用户目录：{self.home}"
            ),
        )
        location.Wrap(650)
        sizer.Add(location, 0)
        self.book.AddPage(page, "Agent")

    def _build_summary_page(self) -> None:
        page, sizer = self._page(
            self.book,
            "5. 检查并保存",
            "确认选择后点击“完成配置”。保存后会重载托盘；已打开的 Agent 需要重启。",
        )
        self.wizard_summary = wx.StaticText(page, label="")
        self.wizard_summary.Wrap(650)
        sizer.Add(self.wizard_summary, 0)
        self.book.AddPage(page, "完成")

    def _show_page(self, index: int) -> None:
        self.page_index = index
        self.book.SetSelection(index)
        self.progress.SetLabel(f"步骤 {index + 1} / 5")
        self.back_button.Enable(index > 0)
        self.next_button.SetLabel(
            "完成配置" if index == 4 else "下一步"
        )
        if index == 4:
            self._update_summary()

    def _on_back(self, _event: wx.CommandEvent) -> None:
        self._show_page(max(0, self.page_index - 1))

    def _on_next(self, _event: wx.CommandEvent) -> None:
        if self.page_index < 4:
            self._show_page(self.page_index + 1)
            return
        try:
            values = self._values()
            changed = apply_settings(
                values,
                self.config_path,
                self.home,
                self.executable,
            )
            set_autostart(
                self.wizard_autostart.IsChecked(),
                self.executable,
            )
            restart_tray(self.executable)
        except Exception as exc:
            self.status.SetLabel(f"保存失败：{exc}")
            wx.MessageBox(str(exc), APP_NAME, wx.OK | wx.ICON_ERROR)
            return
        wx.MessageBox(
            f"配置完成，共更新 {len(changed)} 个 Hook 配置文件。",
            APP_NAME,
            wx.OK | wx.ICON_INFORMATION,
        )
        self.Close()

    def _values(self) -> SettingsValues:
        return SettingsValues(
            bark_enabled=self.wizard_bark_enabled.IsChecked(),
            device_key=self.wizard_key.GetValue(),
            server=self.wizard_server.GetValue(),
            url=self.wizard_url.GetValue(),
            icon=self.wizard_icon.GetValue(),
            bark_mode="all",
            feishu_enabled=self.wizard_feishu_enabled.IsChecked(),
            feishu_control_enabled=self.wizard_feishu_control.IsChecked(),
            feishu_mode="all",
            open_id=self.wizard_open_id.GetValue(),
            chat_id=self.wizard_chat_id.GetValue(),
            lark_cli=self.wizard_lark_cli.GetValue(),
            codex=self.wizard_codex.IsChecked(),
            claude=self.wizard_claude.IsChecked(),
        )

    def _update_summary(self) -> None:
        selected = []
        if self.wizard_bark_enabled.IsChecked():
            selected.append("Bark 通知")
        if self.wizard_feishu_enabled.IsChecked():
            selected.append("飞书通知")
        if self.wizard_feishu_control.IsChecked():
            selected.append("飞书远程控制")
        if self.wizard_codex.IsChecked():
            selected.append("Codex Hook")
        if self.wizard_claude.IsChecked():
            selected.append("Claude Code Hook")
        self.wizard_summary.SetLabel(
            "将启用："
            + ("、".join(selected) if selected else "无，可稍后在设置中启用")
            + f"\n\nBark 跳转：{self.wizard_url.GetValue() or DEFAULT_BARK_URL}"
            + f"\n飞书 open_id：{self.wizard_open_id.GetValue() or '未配置'}"
            + f"\n飞书 chat_id：{self.wizard_chat_id.GetValue() or '尚未建立'}"
        )

    def _wizard_restore_defaults(
        self, _event: wx.CommandEvent
    ) -> None:
        self.wizard_url.SetValue(DEFAULT_BARK_URL)
        self.wizard_icon.SetValue(DEFAULT_BARK_ICON_URL)
        self.status.SetLabel("已恢复新版 Bark 跳转和自有图标默认值。")

    def _wizard_validate_icon(
        self, _event: wx.CommandEvent
    ) -> None:
        url = self.wizard_icon.GetValue().strip()
        self.status.SetLabel("正在校验 Bark 消息图标...")

        def worker() -> None:
            try:
                result = validate_icon_url(
                    url,
                    expected_sha256=expected_icon_sha256(url),
                )
                message = (
                    f"图标有效：{result.format} "
                    f"{result.size[0]}x{result.size[1]}，"
                    f"SHA-256 {result.sha256[:12]}..."
                )
            except Exception as exc:
                message = f"图标校验失败：{exc}"
            wx.CallAfter(self.status.SetLabel, message)

        threading.Thread(target=worker, daemon=True).start()

    def _save_wizard_config(self) -> None:
        values = self._values()
        save_provider_settings(
            self.config_path,
            bark={
                "enabled": values.bark_enabled,
                "device_key": values.device_key,
                "server": values.server,
                "url": values.url,
                "icon": values.icon,
                "mode": values.bark_mode,
            },
            feishu={
                "enabled": values.feishu_enabled,
                "control_enabled": values.feishu_control_enabled,
                "mode": values.feishu_mode,
                "open_id": values.open_id,
                "chat_id": values.chat_id,
                "lark_cli": values.lark_cli,
            },
            agents={"codex": values.codex, "claude": values.claude},
        )

    def _wizard_bark_test(self, _event: wx.CommandEvent) -> None:
        try:
            if not self.wizard_key.GetValue().strip():
                raise ValueError("请先填写 Bark Key。")
            self._save_wizard_config()
        except Exception as exc:
            wx.MessageBox(str(exc), APP_NAME, wx.OK | wx.ICON_ERROR)
            return
        self.status.SetLabel("正在校验图标并发送 Bark 测试通知...")

        def worker() -> None:
            try:
                ok = send_test_notification(self.config_path)
                message = (
                    "测试通知已发送，请检查 iPhone 上的自有图标。"
                    if ok
                    else "Bark 服务未返回成功状态。"
                )
            except Exception as exc:
                message = f"测试失败：{exc}"
            wx.CallAfter(self.status.SetLabel, message)

        threading.Thread(target=worker, daemon=True).start()

    def _wizard_lark_setup(self, step: str) -> None:
        client = LarkCliClient(self.wizard_lark_cli.GetValue().strip())
        try:
            process = subprocess.Popen(client.setup_command(step))
        except Exception as exc:
            wx.MessageBox(str(exc), APP_NAME, wx.OK | wx.ICON_ERROR)
            return
        self.wizard_lark_status.SetLabel(
            "请在 PowerShell 中完成官方交互流程。"
        )

        def wait_for_setup() -> None:
            process.wait()
            wx.CallAfter(
                self.wizard_lark_status.SetLabel,
                "命令已结束，可点击“检测并获取 open_id”。",
            )

        threading.Thread(target=wait_for_setup, daemon=True).start()

    def _wizard_fetch_open_id(
        self, _event: wx.CommandEvent
    ) -> None:
        executable = self.wizard_lark_cli.GetValue().strip()
        self.wizard_lark_status.SetLabel("正在检测登录并获取 open_id...")

        def worker() -> None:
            try:
                client = LarkCliClient(executable)
                status = client.auth_status()
                if not status.authenticated:
                    raise OSError(
                        status.detail or "lark-cli 尚未登录。"
                    )
                open_id = client.current_open_id()
                wx.CallAfter(self.wizard_open_id.SetValue, open_id)
                message = "已登录并自动填写 open_id。"
            except Exception as exc:
                message = (
                    f"自动检测失败：{exc}\n"
                    "可手动运行 user_info 命令并填写 open_id。"
                )
            wx.CallAfter(self.wizard_lark_status.SetLabel, message)

        threading.Thread(target=worker, daemon=True).start()

    def _wizard_connect_feishu(
        self, _event: wx.CommandEvent
    ) -> None:
        open_id = self.wizard_open_id.GetValue().strip()
        executable = self.wizard_lark_cli.GetValue().strip()
        if not open_id:
            wx.MessageBox(
                "请先自动获取或手动填写 open_id。",
                APP_NAME,
                wx.OK | wx.ICON_ERROR,
            )
            return
        self.wizard_lark_status.SetLabel(
            "正在发送连接消息并建立 chat_id..."
        )

        def worker() -> None:
            try:
                chat_id = connect_feishu(
                    self.config_path,
                    open_id,
                    LarkCliClient(executable),
                )
                wx.CallAfter(self.wizard_chat_id.SetValue, chat_id)
                message = "连接成功，chat_id 已自动保存。"
            except Exception as exc:
                message = f"连接失败：{exc}"
            wx.CallAfter(self.wizard_lark_status.SetLabel, message)

        threading.Thread(target=worker, daemon=True).start()


def run_app(
    smoke_test: bool = False,
    onboarding: bool = False,
) -> int:
    app = wx.App(False)
    frame_class = OnboardingFrame if onboarding else SettingsFrame
    frame = frame_class(
        app_data_dir() / "config.json",
        user_home(),
        installed_executable(),
    )
    if smoke_test:
        frame.Show()
        app.Yield()
        frame.Destroy()
        return 0
    frame.Show()
    app.MainLoop()
    return 0


if __name__ == "__main__":
    raise SystemExit(run_app())
