# Codex Question Hook And Tray Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add reliable native Codex question notifications and a Bark-only Windows tray process without modifying `AGENTS.md`.

**Architecture:** Codex structured questions are captured through a `PreToolUse` matcher for `request_user_input`, alongside the existing permission and stop hooks. The existing frozen executable gains a `--tray` mode using `pystray`; it manages notification mode and Windows login startup through HKCU Run. The installer starts the tray after installation and removes its startup registration during uninstall.

**Tech Stack:** Python 3.13, unittest, pystray, Pillow, PyInstaller, Inno Setup 6.

---

### Task 1: Native Codex Question Hook

**Files:**
- Modify: `agent_notify/installer.py`
- Modify: `agent_notify/events.py`
- Modify: `agent_notify/desktop.py`
- Test: `tests/test_installer.py`
- Test: `tests/test_events.py`
- Test: `tests/test_desktop.py`

- [ ] Add failing tests requiring a Codex `PreToolUse` group matched to `^request_user_input$`, normalization as a question event, and removal of the marked legacy `AGENTS.md` block during installation.
- [ ] Run the focused tests and confirm they fail for the missing native question behavior.
- [ ] Add the Codex matcher group, recognize `request_user_input`, and replace instruction installation with legacy block cleanup.
- [ ] Run focused tests and confirm they pass.

### Task 2: Bark-Only Tray And Autostart

**Files:**
- Create: `agent_notify/tray_app.py`
- Modify: `desktop_hook.py`
- Modify: `build_windows.py`
- Test: `tests/test_tray_app.py`
- Test: `tests/test_cli.py`

- [ ] Add failing tests for tray mode state, HKCU Run command generation, enable/disable autostart, and CLI dispatch to tray mode.
- [ ] Run the focused tests and confirm they fail.
- [ ] Implement a single-instance pystray application with notification mode controls, Bark test action, autostart toggle, and exit.
- [ ] Add `--tray`, `--enable-autostart`, and `--disable-autostart` CLI actions and include pystray dependencies in the frozen build.
- [ ] Run focused tests and confirm they pass.

### Task 3: Installer And Documentation

**Files:**
- Modify: `installer/Agent-Notify.iss`
- Modify: `README.md`
- Modify: `CODEX_TEST_PROMPT.md`

- [ ] Bump the installer to `2.1.0`.
- [ ] Start the tray after successful installation and enable login startup.
- [ ] Stop the tray, disable startup, and remove only Agent-Notify hooks during uninstall.
- [ ] Document that Codex questions use native `PreToolUse(request_user_input)` and that Agent-Notify never writes to `AGENTS.md`.
- [ ] Update the Codex test prompt and expected three-notification sequence.

### Task 4: Verification And Packaging

**Files:**
- Output: `dist-installer/Agent-Notify-Setup.exe`
- Output: `outputs/Agent-Notify-Setup.exe`

- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Run Python bytecode compilation, BOM scan, legacy brand scan, and `git diff --check`.
- [ ] Build the frozen executable and compile the Inno Setup package.
- [ ] Verify generated Codex hooks contain PermissionRequest, request_user_input PreToolUse, and Stop, with no Agent-Notify block in `AGENTS.md`.
- [ ] Verify tray startup command and single-instance process behavior.
- [ ] Copy the final installer to `outputs` and record its version, size, SHA256, and signature status.
