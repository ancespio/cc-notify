import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_runtime_secrets_and_logs_are_ignored(self):
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

        self.assertIn("config.json", ignore)
        self.assertIn("config.json.agents-notify-backup-*", ignore)
        self.assertIn("agents-notify.log", ignore)
        self.assertIn("*.log", ignore)
        self.assertIn("AGENTS.md", ignore)
        self.assertIn("task_plan.md", ignore)

    def test_installer_starts_tray_and_manages_autostart(self):
        script = (ROOT / "installer" / "Agents-Notify.iss").read_text(
            encoding="utf-8"
        )

        self.assertIn('#define AppVersion "1.0.3"', script)
        self.assertIn("Agents-Notify-Setup-v1.0.3", script)
        self.assertIn("SetupIconFile=..\\build\\agents-notify.ico", script)
        self.assertIn("UsePreviousGroup=no", script)
        self.assertIn("[Icons]", script)
        self.assertIn("Agents-Notify 设置", script)
        self.assertIn("[Run]", script)
        self.assertIn("postinstall", script)
        self.assertIn("--onboarding", script)
        self.assertIn("--stop-tray --disable-autostart", script)
        self.assertIn("Sleep(2000)", script)
        self.assertIn("是否同时删除 Agents-Notify 的用户配置", script)
        self.assertIn(
            "ExpandConstant('{userappdata}\\Agent-Notify')",
            script,
        )
        self.assertIn(
            "ExpandConstant('{userappdata}\\Agents-Notify')",
            script,
        )
        self.assertIn('Name: "{app}\\Agent-Notify.exe"', script)
        self.assertIn(
            'Name: "{commonprograms}\\Agent-Notify"',
            script,
        )
        self.assertNotIn("BarkPage", script)
        self.assertNotIn("--install-request", script)
        self.assertNotIn("--test-notification", script)
        self.assertIn('Source: "..\\LICENSE"', script)

    def test_desktop_app_exposes_notification_destination(self):
        script = (ROOT / "desktop_app.py").read_text(encoding="utf-8")

        self.assertIn("点击通知跳转", script)
        self.assertIn("DEFAULT_BARK_URL", script)
        self.assertIn("wx.ScrolledWindow", script)
        self.assertIn("wx.RadioButton", script)
        self.assertNotIn('label="启用 Bark 通知"', script)
        self.assertNotIn('label="启用飞书通知"', script)

    def test_readme_documents_native_question_hook_and_clean_agents(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("`PreToolUse(request_user_input)`", readme)
        self.assertIn("不会写入 `AGENTS.md`", readme)
        self.assertIn("`chatgpt://codex`", readme)
        self.assertIn(r"C:\Program Files\Agents-Notify", readme)
        self.assertIn(r"%APPDATA%\Agents-Notify\config.json", readme)
        self.assertIn("双击 `Agents-Notify.exe`", readme)
        self.assertIn("不生成具体线程", readme)
        self.assertIn("/notify bark on|ssh|off|status", readme)
        self.assertIn("/notify feishu on|ssh|off|status", readme)
        self.assertIn("lark-cli", readme)
        self.assertIn("v1.0.3", readme)
        self.assertIn("auth login --recommend", readme)
        self.assertIn("自动获取", readme)
        self.assertIn("飞书 App ID", readme)
        self.assertIn("飞书 App Secret", readme)
        self.assertIn("im:message.p2p_msg:readonly", readme)
        self.assertIn("im:message:send_as_bot", readme)
        self.assertIn("im.message.receive_v1", readme)
        self.assertNotIn("Global `AGENTS.md` fallback", readme)

    def test_pyinstaller_build_is_windowed_and_bundles_custom_icon(self):
        script = (ROOT / "build_windows.py").read_text(encoding="utf-8")

        self.assertIn('"--windowed"', script)
        self.assertNotIn('"--console"', script)
        self.assertIn("--add-data=", script)
        self.assertIn("--hidden-import=lark_oapi.ws.client", script)
        self.assertIn("--hidden-import=lark_oapi.api.im.v1", script)
        self.assertIn("SOURCE_ICON_PATH", script)

    def test_example_config_uses_app_link_and_custom_icon(self):
        config = (ROOT / "config.example.json").read_text(encoding="utf-8")

        self.assertIn('"config_version": "1.0.3"', config)
        self.assertIn('"url": "chatgpt://codex"', config)
        self.assertIn(
            "Agents-Notify/master/assets/agents-notify.png", config
        )
        self.assertNotIn('"enabled"', config)
        self.assertNotIn("Finb/Bark", config)
        self.assertIn('"agents"', config)


if __name__ == "__main__":
    unittest.main()
