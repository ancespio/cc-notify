#!/usr/bin/env python
"""Install Agents-Notify hooks for Codex and Claude Code."""

import argparse
from pathlib import Path
import sys

from agents_notify.config import VALID_MODES, load_config, update_config
from agents_notify.installer import (
    install_claude_hooks,
    install_codex_hooks,
    remove_agent_instructions,
)


SCRIPT_DIR = Path(__file__).resolve().parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install Agents-Notify for Codex and Claude Code."
    )
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument(
        "--config", type=Path, default=SCRIPT_DIR / "config.json"
    )
    parser.add_argument("--bark-key", default="")
    parser.add_argument("--bark-server", default="")
    parser.add_argument("--bark-mode", choices=VALID_MODES, default="")
    parser.add_argument("--enable-feishu", action="store_true")
    parser.add_argument("--enable-feishu-control", action="store_true")
    parser.add_argument("--feishu-mode", choices=VALID_MODES, default="")
    parser.add_argument("--open-id", default="")
    parser.add_argument("--chat-id", default="")
    parser.add_argument("--lark-cli", default="")
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--skip-codex", action="store_true")
    parser.add_argument("--skip-claude", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def write_config(path: Path, args: argparse.Namespace) -> None:
    def mutate(config: dict) -> dict:
        bark = config["providers"]["bark"]
        if args.bark_key:
            bark["device_key"] = args.bark_key
            if bark.get("mode") == "off":
                bark["mode"] = "all"
        if args.bark_server:
            bark["server"] = args.bark_server
        if args.bark_mode:
            bark["mode"] = args.bark_mode

        feishu = config["providers"]["feishu"]
        if args.enable_feishu or args.open_id:
            if feishu.get("mode") == "off":
                feishu["mode"] = "all"
        if args.enable_feishu_control:
            feishu["control_enabled"] = True
        if args.feishu_mode:
            feishu["mode"] = args.feishu_mode
        if args.open_id:
            feishu["open_id"] = args.open_id
        if args.chat_id:
            feishu["chat_id"] = args.chat_id
        if args.lark_cli:
            feishu["lark_cli"] = args.lark_cli
        return config

    update_config(path, mutate)


def main() -> int:
    args = parse_args()
    script_path = SCRIPT_DIR / "notify_hook.py"
    codex_dir = args.home / ".codex"
    actions = []

    if not args.skip_codex:
        actions.append(("Codex hooks", codex_dir / "hooks.json"))
        if (codex_dir / "AGENTS.md").exists():
            actions.append(
                (
                    "Clean legacy Agents-Notify instructions",
                    codex_dir / "AGENTS.md",
                )
            )
    if not args.skip_claude:
        actions.append(
            ("Claude Code hooks", args.home / ".claude" / "settings.json")
        )
    actions.append(("Agents-Notify config", args.config))

    if args.dry_run:
        print("Agents-Notify dry run:")
        for label, path in actions:
            print(f"- {label}: {path}")
        return 0

    if not args.skip_codex:
        install_codex_hooks(
            codex_dir / "hooks.json",
            script_path,
            args.python_executable,
        )
        agents_path = codex_dir / "AGENTS.md"
        if agents_path.exists():
            remove_agent_instructions(agents_path)
    if not args.skip_claude:
        install_claude_hooks(
            args.home / ".claude" / "settings.json",
            script_path,
            args.python_executable,
        )
    write_config(args.config, args)

    print("Agents-Notify installation complete.")
    print("Restart Codex and Claude Code to load the new hooks.")
    if not load_config(args.config)["providers"]["bark"]["device_key"]:
        print("Bark device key is empty; add it to config.json or rerun with --bark-key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
