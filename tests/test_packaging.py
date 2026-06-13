import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackagingTests(unittest.TestCase):
    def test_installer_starts_tray_and_manages_autostart(self):
        script = (ROOT / "installer" / "Agent-Notify.iss").read_text(
            encoding="utf-8"
        )

        self.assertIn('#define AppVersion "1.0.0"', script)
        self.assertIn("SetupIconFile=..\\build\\agent-notify.ico", script)
        self.assertIn("[Icons]", script)
        self.assertIn("Agent-Notify 设置", script)
        self.assertIn("[Run]", script)
        self.assertIn("postinstall", script)
        self.assertIn("--stop-tray --disable-autostart", script)
        self.assertNotIn("BarkPage", script)
        self.assertNotIn("--install-request", script)
        self.assertNotIn("--test-notification", script)
        self.assertIn('Source: "..\\LICENSE"', script)

    def test_desktop_app_exposes_notification_destination(self):
        script = (ROOT / "desktop_app.py").read_text(encoding="utf-8")

        self.assertIn("点击通知跳转", script)
        self.assertIn("DEFAULT_BARK_URL", script)

    def test_readme_documents_native_question_hook_and_clean_agents(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("`PreToolUse(request_user_input)`", readme)
        self.assertIn("不会写入 `AGENTS.md`", readme)
        self.assertIn("`chatgpt://`", readme)
        self.assertIn(r"C:\Program Files\Agent-Notify", readme)
        self.assertIn(r"%APPDATA%\Agent-Notify\config.json", readme)
        self.assertIn("双击 `Agent-Notify.exe`", readme)
        self.assertIn("不生成具体线程", readme)
        self.assertIn("/notify bark on|ssh|off|status", readme)
        self.assertIn("/notify feishu on|ssh|off|status", readme)
        self.assertIn("lark-cli", readme)
        self.assertIn("v1.0.0", readme)
        self.assertNotIn("Global `AGENTS.md` fallback", readme)

    def test_pyinstaller_build_is_windowed_and_bundles_custom_icon(self):
        script = (ROOT / "build_windows.py").read_text(encoding="utf-8")

        self.assertIn('"--windowed"', script)
        self.assertNotIn('"--console"', script)
        self.assertIn("--add-data=", script)
        self.assertIn("SOURCE_ICON_PATH", script)

    def test_example_config_uses_app_link_and_custom_icon(self):
        config = (ROOT / "config.example.json").read_text(encoding="utf-8")

        self.assertIn('"url": "chatgpt://"', config)
        self.assertIn(
            "Agent-Notify/v1.0.0/assets/agent-notify.png", config
        )
        self.assertNotIn("Finb/Bark", config)
        self.assertIn('"agents"', config)


if __name__ == "__main__":
    unittest.main()
