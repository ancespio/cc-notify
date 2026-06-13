#!/usr/bin/env python
"""Agent-Notify native Windows settings application."""

from dataclasses import dataclass
from pathlib import Path
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
from agent_notify.resources import resource_path
from agent_notify.tray_app import (
    is_autostart_enabled,
    restart_tray,
    set_autostart,
)


APP_NAME = "Agent-Notify"
DEFAULT_SERVER = "https://api.day.app"


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
        self.key_ctrl = wx.TextCtrl(
            bark_panel,
            value=values.device_key,
            style=wx.TE_PASSWORD,
        )
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
        style = 0 if self.show_key.IsChecked() else wx.TE_PASSWORD
        self.key_ctrl.SetWindowStyleFlag(style)
        self.key_ctrl.Refresh()

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


def run_app(smoke_test: bool = False) -> int:
    app = wx.App(False)
    frame = SettingsFrame(
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
