#!/usr/bin/env python
"""Agents-Notify hook entry point for Codex and Claude Code."""

import argparse
import json
import os
from pathlib import Path
import sys

from agents_notify.config import load_config
from agents_notify.runtime import handle_payload


PROJECT_DIR = Path(__file__).resolve().parent


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--question")
    parser.add_argument("--source", default="codex")
    parser.add_argument("--cwd", default=os.getcwd())
    args, _ = parser.parse_known_args()
    return args


def _payload(args: argparse.Namespace) -> dict:
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
    raw = sys.stdin.read()
    return json.loads(raw)


def main() -> int:
    try:
        args = _arguments()
        payload = _payload(args)
        config_path = Path(
            os.environ.get(
                "AGENTS_NOTIFY_CONFIG",
                os.environ.get(
                    "AGENT_NOTIFY_CONFIG",
                    str(PROJECT_DIR / "config.json"),
                ),
            )
        )
        mode_path = Path(
            os.environ.get(
                "AGENTS_NOTIFY_MODE",
                os.environ.get(
                    "AGENT_NOTIFY_MODE",
                    str(PROJECT_DIR / "mode.json"),
                ),
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
