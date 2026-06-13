#!/usr/bin/env python
"""Frozen Hook entry point for Agent-Notify."""

import argparse
import json
import os
from pathlib import Path
import sys

from agent_notify.config import load_config
from agent_notify.desktop import (
    apply_install_request,
    app_data_dir,
    remove_hooks,
    send_test_notification,
    user_home,
)
from agent_notify.runtime import handle_payload
from agent_notify.tray_app import (
    run_tray,
    set_autostart,
    signal_tray_stop,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--hook", action="store_true")
    parser.add_argument("--tray", action="store_true")
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--settings-smoke-test", action="store_true")
    parser.add_argument("--onboarding", action="store_true")
    parser.add_argument("--onboarding-smoke-test", action="store_true")
    parser.add_argument("--enable-autostart", action="store_true")
    parser.add_argument("--disable-autostart", action="store_true")
    parser.add_argument("--stop-tray", action="store_true")
    parser.add_argument("--install-request")
    parser.add_argument("--remove-hooks", action="store_true")
    parser.add_argument("--test-notification", action="store_true")
    parser.add_argument("--silent", action="store_true")
    parser.add_argument("--home")
    parser.add_argument("--config")
    parser.add_argument("--question")
    parser.add_argument("--source", default="codex")
    parser.add_argument("--cwd", default=os.getcwd())
    args, _ = parser.parse_known_args(argv)
    return args


def should_open_settings(args: argparse.Namespace) -> bool:
    return not any(
        (
            args.hook,
            args.tray,
            args.smoke_test,
            args.settings_smoke_test,
            args.onboarding,
            args.onboarding_smoke_test,
            args.enable_autostart,
            args.disable_autostart,
            args.stop_tray,
            args.install_request,
            args.remove_hooks,
            args.test_notification,
            args.question is not None,
        )
    )


def run_settings_app(
    smoke_test: bool = False,
    onboarding: bool = False,
) -> int:
    from desktop_app import run_app

    return run_app(smoke_test=smoke_test, onboarding=onboarding)


def read_payload(args: argparse.Namespace) -> dict:
    if args.question is not None:
        return {
            "hook_event_name": "Question",
            "source": args.source,
            "cwd": args.cwd,
            "prompt": args.question,
        }
    try:
        sys.stdin.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    if sys.stdin is None:
        return {}
    return json.loads(sys.stdin.read())


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    home = Path(args.home) if args.home else user_home()
    data_dir = app_data_dir()
    config_path = Path(args.config) if args.config else data_dir / "config.json"
    executable = Path(sys.executable).resolve()

    if args.smoke_test:
        return 0
    if args.settings_smoke_test:
        return run_settings_app(smoke_test=True)
    if args.onboarding_smoke_test:
        return run_settings_app(smoke_test=True, onboarding=True)
    if args.onboarding:
        return run_settings_app(smoke_test=False, onboarding=True)
    if should_open_settings(args):
        return run_settings_app(smoke_test=False, onboarding=False)

    if (
        args.install_request
        or args.remove_hooks
        or args.test_notification
        or args.enable_autostart
        or args.disable_autostart
        or args.stop_tray
    ):
        try:
            if args.install_request:
                apply_install_request(
                    Path(args.install_request),
                    config_path,
                    home,
                    executable,
                )
            if args.remove_hooks:
                remove_hooks(home)
            if args.test_notification and not send_test_notification(
                config_path
            ):
                return 2
            if args.enable_autostart:
                set_autostart(True, executable)
            if args.disable_autostart:
                set_autostart(False, executable)
            if args.stop_tray:
                signal_tray_stop()
        except Exception as exc:
            if not args.silent:
                print(str(exc), file=sys.stderr)
            return 1
        return 0

    if args.tray:
        return run_tray(
            executable, config_path, data_dir / "mode.json"
        )

    try:
        payload = read_payload(args)
        config_path = Path(
            os.environ.get(
                "AGENT_NOTIFY_CONFIG", str(config_path)
            )
        )
        mode_path = Path(
            os.environ.get(
                "AGENT_NOTIFY_MODE", str(data_dir / "mode.json")
            )
        )
        handle_payload(
            payload,
            load_config(config_path, mode_path),
        )
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
