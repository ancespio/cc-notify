# Bark Codex Link Design

## Goal

Make every Agent-Notify Bark notification open Codex when tapped, while
preserving a reliable browser fallback and allowing the destination to be
changed by the user.

## Behavior

- The default Bark notification URL is `https://chatgpt.com/codex`.
- The Windows installer shows a notification destination field prefilled with
  that URL.
- The desktop configuration application exposes the same field.
- A custom non-empty destination is saved to
  `providers.bark.url` in `config.json`.
- Leaving the field empty restores the default Codex URL.
- Bark receives the destination through its documented `url` payload field.

## Deep-Link Boundary

Agent-Notify will not generate `codex://threads/<session UUID>` links in this
version. OpenAI documents that scheme for the Codex app, but does not guarantee
that ChatGPT on iOS handles it. The HTTPS Codex URL can be handled as a
Universal Link when supported and otherwise opens safely in the browser.

The link is not thread-specific. Mapping a local hook session UUID to a mobile
Codex thread is deferred until OpenAI documents a supported mobile link format.

## Compatibility

Existing configurations with an explicitly configured Bark URL keep their
value. Existing configurations whose URL is missing or empty receive the
default Codex destination when settings are saved or installation is rerun.

Notification delivery remains fail-open. An invalid custom destination does
not block Codex or Claude Code hook execution.

## Testing

- Default configuration contains `https://chatgpt.com/codex`.
- Bark payloads include the configured `url`.
- Desktop settings save both default and custom destinations.
- Installer requests persist the destination.
- Installer source exposes the field and increments the application version.
- README documents the tap behavior, browser fallback, and lack of
  thread-specific mobile deep links.
