"""Normalize Codex and Claude Code hook payloads."""

from dataclasses import dataclass
import json
import os
import re
from typing import Any, Mapping, Optional


@dataclass(frozen=True)
class NormalizedEvent:
    source: str
    kind: str
    workspace: str
    tool_name: str = ""
    summary: str = ""


_EVENT_KINDS = {
    "permissionrequest": "permission",
    "permission_request": "permission",
    "elicitation": "question",
    "elicitation_request": "question",
    "question": "question",
    "requestuserinput": "question",
    "request_user_input": "question",
    "stop": "stop",
}


def _clean_text(value: Any, limit: int = 300) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) > limit:
        return value[: limit - 3] + "..."
    return value


def _workspace_name(value: Any) -> str:
    path = str(value or os.getcwd()).replace("\\", "/").rstrip("/")
    return path.rsplit("/", 1)[-1] or path


def _detect_source(payload: Mapping[str, Any]) -> str:
    explicit = str(payload.get("source") or payload.get("agent") or "").lower()
    if explicit in {"codex", "claude", "claude-code", "claudecode"}:
        return "claude" if explicit != "codex" else "codex"
    if "permission_mode" in payload or (
        "turn_id" in payload and "model" in payload
    ):
        return "codex"
    return "claude"


def _summary(payload: Mapping[str, Any], kind: str) -> str:
    if kind == "stop":
        return _clean_text(
            payload.get("last_assistant_message")
            or payload.get("message")
            or payload.get("summary")
        )
    if kind == "question":
        direct = (
            payload.get("prompt")
            or payload.get("question")
            or payload.get("message")
        )
        if direct:
            return _clean_text(direct)

    tool_input = payload.get("tool_input")
    if tool_input is None:
        tool_input = payload.get("arguments")
    if isinstance(tool_input, Mapping):
        questions = tool_input.get("questions")
        if (
            kind == "question"
            and isinstance(questions, list)
            and questions
            and isinstance(questions[0], Mapping)
        ):
            return _clean_text(questions[0].get("question"))
        for key in ("command", "description", "path", "query", "prompt", "question"):
            if tool_input.get(key):
                return _clean_text(tool_input[key])
    return _clean_text(tool_input)


def normalize_event(
    payload: Mapping[str, Any],
) -> Optional[NormalizedEvent]:
    raw_name = (
        payload.get("hook_event_name")
        or payload.get("event")
        or payload.get("hook_event")
        or ""
    )
    normalized_name = str(raw_name).replace("-", "_").lower()
    if normalized_name == "pretooluse" and payload.get("tool_name") in {
        "AskUserQuestion",
        "request_user_input",
    }:
        kind = "question"
    else:
        kind = _EVENT_KINDS.get(normalized_name)
    if not kind:
        return None

    return NormalizedEvent(
        source=_detect_source(payload),
        kind=kind,
        workspace=_workspace_name(payload.get("cwd")),
        tool_name=str(payload.get("tool_name") or payload.get("toolName") or ""),
        summary=_summary(payload, kind),
    )
