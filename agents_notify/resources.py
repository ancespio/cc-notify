"""Locate bundled and source-tree resources."""

from pathlib import Path
import sys


def resource_path(relative: str) -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS"))
    else:
        base = Path(__file__).resolve().parents[1]
    return base / relative
