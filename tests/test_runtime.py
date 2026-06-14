import json
import os
import tempfile
import threading
import unittest
from pathlib import Path

from agent_notify.config import (
    CONFIG_VERSION,
    DEFAULT_AGENT_ICON_URL,
    DEFAULT_BARK_URL,
    load_config,
    update_config,
)
from agent_notify.runtime import (
    build_providers,
    handle_payload,
    should_notify_for_mode,
)


class ConfigTests(unittest.TestCase):
    def test_missing_config_uses_safe_defaults(self):
        config = load_config(Path("does-not-exist.json"))

        self.assertNotIn("enabled", config["providers"]["bark"])
        self.assertEqual(config["providers"]["bark"]["device_key"], "")
        self.assertEqual(
            config["providers"]["bark"]["url"],
            "chatgpt://codex",
        )
        self.assertEqual(
            config["providers"]["bark"]["icon"],
            DEFAULT_AGENT_ICON_URL,
        )
        self.assertEqual(config["providers"]["bark"]["mode"], "all")
        self.assertTrue(config["agents"]["codex"])
        self.assertTrue(config["agents"]["claude"])
        self.assertNotIn("enabled", config["providers"]["feishu"])
        self.assertFalse(
            config["providers"]["feishu"]["control_enabled"]
        )
        self.assertEqual(config["providers"]["feishu"]["mode"], "off")
        self.assertEqual(config["config_version"], CONFIG_VERSION)

    def test_empty_legacy_url_and_icon_use_new_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "providers": {
                            "bark": {
                                "url": "",
                                "icon": "",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(path)

        bark = config["providers"]["bark"]
        self.assertEqual(bark["url"], DEFAULT_BARK_URL)
        self.assertEqual(bark["icon"], DEFAULT_AGENT_ICON_URL)

    def test_old_defaults_are_backed_up_and_migrated_once(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            old = {
                "providers": {
                    "bark": {
                        "device_key": "keep-secret",
                        "url": "chatgpt://",
                        "icon": (
                            "https://raw.githubusercontent.com/ancespio/"
                            "Agent-Notify/v1.0.1/assets/agent-notify.png"
                        ),
                    }
                }
            }
            path.write_text(json.dumps(old), encoding="utf-8")

            first = load_config(path)
            backups = list(
                path.parent.glob("config.json.agent-notify-backup-*")
            )
            second = load_config(path)

        self.assertEqual(first["config_version"], CONFIG_VERSION)
        self.assertEqual(
            first["providers"]["bark"]["url"], "chatgpt://codex"
        )
        self.assertIn(
            "master/assets/agent-notify.png",
            first["providers"]["bark"]["icon"],
        )
        self.assertEqual(
            first["providers"]["bark"]["device_key"], "keep-secret"
        )
        self.assertEqual(len(backups), 1)
        self.assertEqual(first, second)

    def test_migration_preserves_custom_bark_destinations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "providers": {
                            "bark": {
                                "url": "myapp://thread/123",
                                "icon": "https://example.com/custom.png",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(path)

        bark = config["providers"]["bark"]
        self.assertEqual(bark["url"], "myapp://thread/123")
        self.assertEqual(
            bark["icon"], "https://example.com/custom.png"
        )

    def test_legacy_feishu_config_is_migrated_in_memory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(
                json.dumps({"open_id": "ou_legacy", "chat_id": "oc_legacy"}),
                encoding="utf-8",
            )

            config = load_config(path)

        self.assertEqual(config["providers"]["feishu"]["mode"], "all")
        self.assertNotIn("enabled", config["providers"]["feishu"])
        self.assertEqual(config["providers"]["feishu"]["open_id"], "ou_legacy")
        self.assertEqual(config["providers"]["feishu"]["chat_id"], "oc_legacy")
        self.assertNotIn("open_id", config)
        self.assertNotIn("chat_id", config)

    def test_current_version_enabled_fields_are_normalized_to_modes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "config_version": CONFIG_VERSION,
                        "providers": {
                            "bark": {
                                "enabled": False,
                                "mode": "all",
                            },
                            "feishu": {
                                "enabled": True,
                                "mode": "ssh-only",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(path)
            persisted = json.loads(path.read_text(encoding="utf-8"))
            backups = list(
                path.parent.glob("config.json.agent-notify-backup-*")
            )

        self.assertEqual(config["providers"]["bark"]["mode"], "off")
        self.assertEqual(
            config["providers"]["feishu"]["mode"], "ssh-only"
        )
        self.assertNotIn("enabled", persisted["providers"]["bark"])
        self.assertNotIn("enabled", persisted["providers"]["feishu"])
        self.assertEqual(len(backups), 1)

    def test_legacy_mode_file_is_migrated_into_provider_modes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "config.json"
            mode_path = root / "mode.json"
            path.write_text("{}", encoding="utf-8")
            mode_path.write_text('{"mode":"ssh-only"}', encoding="utf-8")

            config = load_config(path, mode_path)
            persisted = load_config(path)

        self.assertEqual(config["providers"]["bark"]["mode"], "ssh-only")
        self.assertEqual(config["providers"]["feishu"]["mode"], "ssh-only")
        self.assertEqual(
            persisted["providers"]["bark"]["mode"], "ssh-only"
        )

    def test_atomic_update_preserves_unrelated_provider_fields(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            update_config(
                path,
                lambda config: config["providers"]["bark"].update(
                    {"device_key": "secret"}
                ),
            )
            update_config(
                path,
                lambda config: config["providers"]["feishu"].update(
                    {"mode": "off"}
                ),
            )
            config = load_config(path)

        self.assertEqual(
            config["providers"]["bark"]["device_key"], "secret"
        )
        self.assertEqual(config["providers"]["feishu"]["mode"], "off")

    def test_concurrent_updates_do_not_lose_provider_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            barrier = threading.Barrier(3)

            def update_bark():
                barrier.wait()
                update_config(
                    path,
                    lambda config: config["providers"]["bark"].update(
                        {"device_key": "concurrent-secret"}
                    ),
                )

            def update_feishu():
                barrier.wait()
                update_config(
                    path,
                    lambda config: config["providers"]["feishu"].update(
                        {"mode": "ssh-only"}
                    ),
                )

            threads = [
                threading.Thread(target=update_bark),
                threading.Thread(target=update_feishu),
            ]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join()
            config = load_config(path)

        self.assertEqual(
            config["providers"]["bark"]["device_key"],
            "concurrent-secret",
        )
        self.assertEqual(
            config["providers"]["feishu"]["mode"],
            "ssh-only",
        )


class RuntimeTests(unittest.TestCase):
    def test_disabled_event_is_not_dispatched(self):
        config = load_config(Path("does-not-exist.json"))
        config["events"]["permission"] = False

        results = handle_payload(
            {
                "hook_event_name": "PermissionRequest",
                "source": "codex",
                "cwd": "/tmp/demo",
                "tool_name": "shell_command",
                "tool_input": {"command": "git status"},
            },
            config,
            providers=[],
        )

        self.assertEqual(results, [])

    def test_unknown_payload_is_ignored(self):
        config = load_config(Path("does-not-exist.json"))

        self.assertEqual(
            handle_payload(
                {"hook_event_name": "SessionStart"},
                config,
                providers=[],
            ),
            [],
        )

    def test_mode_rules(self):
        self.assertTrue(should_notify_for_mode("all", {}))
        self.assertFalse(should_notify_for_mode("off", {}))
        self.assertFalse(should_notify_for_mode("ssh-only", {}))
        self.assertTrue(
            should_notify_for_mode(
                "ssh-only", {"SSH_CONNECTION": "client server"}
            )
        )

    def test_runtime_is_fail_open_when_provider_raises(self):
        class BrokenProvider:
            def send(self, event):
                raise OSError("offline")

        config = load_config(Path("does-not-exist.json"))
        results = handle_payload(
            {
                "hook_event_name": "Question",
                "source": "codex",
                "cwd": os.getcwd(),
                "prompt": "Choose a target",
            },
            config,
            providers=[BrokenProvider()],
        )

        self.assertEqual(results, [False])

    def test_each_provider_uses_its_own_mode(self):
        class Recorder:
            def __init__(self):
                self.calls = 0

            def send(self, _event):
                self.calls += 1
                return True

        bark = Recorder()
        feishu = Recorder()
        config = {
            "events": {"stop": True},
            "providers": {
                "bark": {"mode": "off"},
                "feishu": {"mode": "all"},
            },
        }

        results = handle_payload(
            {"hook_event_name": "Stop"},
            config,
            providers={"bark": bark, "feishu": feishu},
            environ={},
        )

        self.assertEqual(results, [True])
        self.assertEqual(bark.calls, 0)
        self.assertEqual(feishu.calls, 1)

    def test_build_providers_returns_named_channels(self):
        providers = build_providers(load_config(Path("missing.json")))

        self.assertEqual(set(providers), {"bark", "feishu"})


if __name__ == "__main__":
    unittest.main()
