"""Small, redacted diagnostics log for desktop actions."""

from datetime import datetime
from pathlib import Path
from typing import Iterable


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    result = str(text)
    for secret in secrets:
        value = str(secret or "").strip()
        if value:
            result = result.replace(value, "[REDACTED]")
    return result


def write_diagnostic(
    path: Path,
    message: str,
    *,
    secrets: Iterable[str] = (),
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"{timestamp} {redact(message, secrets)}\n"
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(line)
