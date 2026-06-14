"""Fail-open runtime orchestration."""

import os
from typing import Any, Iterable, Mapping, Optional

from .events import normalize_event
from .providers import BarkProvider, FeishuProvider, dispatch


def should_notify_for_mode(
    mode: str, environ: Mapping[str, str]
) -> bool:
    if mode == "off":
        return False
    if mode == "ssh-only":
        return bool(environ.get("SSH_TTY") or environ.get("SSH_CONNECTION"))
    return True


def build_providers(config: Mapping[str, Any]) -> dict[str, Any]:
    provider_config = config.get("providers", {})
    return {
        "bark": BarkProvider(provider_config.get("bark", {})),
        "feishu": FeishuProvider(provider_config.get("feishu", {})),
    }


def handle_payload(
    payload: Mapping[str, Any],
    config: Mapping[str, Any],
    mode: str | None = None,
    providers: Optional[Iterable[Any] | Mapping[str, Any]] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> list[bool]:
    event = normalize_event(payload)
    if event is None:
        return []
    if not config.get("events", {}).get(event.kind, True):
        return []
    environment = environ or os.environ
    if providers is not None and not isinstance(providers, Mapping):
        if not should_notify_for_mode(mode or "all", environment):
            return []
        return dispatch(event, list(providers))

    named_providers = (
        dict(providers) if providers is not None else build_providers(config)
    )
    provider_config = config.get("providers", {})
    active = []
    for name, provider in named_providers.items():
        settings = provider_config.get(name, {})
        if should_notify_for_mode(settings.get("mode", "all"), environment):
            active.append(provider)
    return dispatch(event, active)
