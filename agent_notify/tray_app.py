"""Bark-only Windows tray application and login startup management."""

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any

from PIL import Image, ImageEnhance
import pystray

from .config import load_config, update_config
from .desktop import send_test_notification
from .feishu_control import FeishuController, LarkCliClient
from .resources import resource_path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "Agent-Notify"
MUTEX_NAME = r"Local\Agent-Notify-Tray"
STOP_EVENT_NAME = r"Local\Agent-Notify-Tray-Stop"
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
WAIT_INFINITE = 0xFFFFFFFF


def _windows_kernel32():
    if sys.platform != "win32":
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateEventW.argtypes = [
        wintypes.LPVOID,
        wintypes.BOOL,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    kernel32.CreateEventW.restype = wintypes.HANDLE
    kernel32.OpenEventW.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.LPCWSTR,
    ]
    kernel32.OpenEventW.restype = wintypes.HANDLE
    kernel32.SetEvent.argtypes = [wintypes.HANDLE]
    kernel32.SetEvent.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
    ]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


KERNEL32 = _windows_kernel32()


def autostart_command(executable: Path) -> str:
    return f'"{executable}" --tray'


def settings_command(executable: Path) -> list[str]:
    return [str(executable)]


def set_autostart(
    enabled: bool, executable: Path, registry: Any = None
) -> None:
    if registry is None:
        import winreg as registry

    with registry.CreateKey(
        registry.HKEY_CURRENT_USER, RUN_KEY
    ) as key:
        if enabled:
            registry.SetValueEx(
                key,
                RUN_VALUE_NAME,
                0,
                registry.REG_SZ,
                autostart_command(executable),
            )
        else:
            try:
                registry.DeleteValue(key, RUN_VALUE_NAME)
            except FileNotFoundError:
                pass


def is_autostart_enabled(
    executable: Path, registry: Any = None
) -> bool:
    if registry is None:
        import winreg as registry

    try:
        with registry.OpenKey(
            registry.HKEY_CURRENT_USER, RUN_KEY
        ) as key:
            value, _ = registry.QueryValueEx(key, RUN_VALUE_NAME)
    except FileNotFoundError:
        return False
    return str(value).casefold() == autostart_command(executable).casefold()


def set_provider_mode(
    config_path: Path, provider: str, mode: str
) -> None:
    update_config(
        config_path,
        lambda config: config["providers"][provider].update(
            {"mode": mode}
        ),
    )


def _notifications_enabled(config_path: Path) -> bool:
    config = load_config(config_path)
    return any(
        settings.get("enabled") and settings.get("mode") != "off"
        for settings in config["providers"].values()
    )


def _default_lark_cli() -> str:
    if sys.platform == "win32":
        return str(
            Path(os.environ.get("APPDATA", ""))
            / "npm"
            / "lark-cli.cmd"
        )
    return "lark-cli"


def build_feishu_controller(
    config_path: Path,
) -> FeishuController | None:
    settings = load_config(config_path)["providers"]["feishu"]
    if not settings.get("control_enabled"):
        return None
    client = LarkCliClient(
        str(settings.get("lark_cli") or _default_lark_cli()),
        float(settings.get("timeout", 10)),
    )
    return FeishuController(config_path, client)


def restart_tray(
    executable: Path,
    stop_signal=None,
    launcher=subprocess.Popen,
    sleeper=time.sleep,
    tray_running=None,
) -> None:
    if stop_signal is None:
        stop_signal = signal_tray_stop
    if tray_running is None:
        tray_running = _tray_instance_running
    stop_signal()
    for _ in range(50):
        if not tray_running():
            break
        sleeper(0.1)
    launcher([str(executable), "--tray"], close_fds=True)


def _make_icon(enabled: bool) -> Image.Image:
    with Image.open(resource_path("assets/agent-notify.png")) as source:
        image = source.convert("RGBA").resize(
            (64, 64),
            Image.Resampling.LANCZOS,
        )
    if not enabled:
        image = ImageEnhance.Color(image).enhance(0.0)
        image = ImageEnhance.Brightness(image).enhance(0.65)
    return image


def _notify(icon: pystray.Icon, message: str) -> None:
    try:
        icon.notify(message, "Agent-Notify")
    except Exception:
        pass


def _acquire_single_instance() -> tuple[bool, int | None]:
    if KERNEL32 is None:
        return True, None
    ctypes.set_last_error(0)
    handle = KERNEL32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return False, None
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        KERNEL32.CloseHandle(handle)
        return False, None
    return True, handle


def _tray_instance_running() -> bool:
    acquired, handle = _acquire_single_instance()
    if acquired and handle and KERNEL32 is not None:
        KERNEL32.CloseHandle(handle)
    return not acquired


def signal_tray_stop() -> bool:
    if KERNEL32 is None:
        return False
    handle = KERNEL32.OpenEventW(
        EVENT_MODIFY_STATE, False, STOP_EVENT_NAME
    )
    if not handle:
        return False
    try:
        return bool(KERNEL32.SetEvent(handle))
    finally:
        KERNEL32.CloseHandle(handle)


def _watch_stop_event(icon: pystray.Icon) -> None:
    if KERNEL32 is None:
        return
    handle = KERNEL32.CreateEventW(
        None, False, False, STOP_EVENT_NAME
    )
    if not handle:
        return
    try:
        KERNEL32.WaitForSingleObject(handle, WAIT_INFINITE)
        icon.stop()
    finally:
        KERNEL32.CloseHandle(handle)


def run_tray(
    executable: Path,
    config_path: Path,
    legacy_mode_path: Path | None = None,
) -> int:
    acquired, mutex_handle = _acquire_single_instance()
    if not acquired:
        return 0
    load_config(config_path, legacy_mode_path)

    icon_ref: list[pystray.Icon | None] = [None]
    controller = build_feishu_controller(config_path)
    controller_thread = None
    if controller is not None:
        controller_thread = threading.Thread(
            target=controller.run,
            daemon=True,
        )
        controller_thread.start()

    def refresh_icon() -> None:
        icon = icon_ref[0]
        if icon is None:
            return
        enabled = _notifications_enabled(config_path)
        icon.icon = _make_icon(enabled)
        icon.title = (
            "Agent-Notify: 通知已开启"
            if enabled
            else "Agent-Notify: 通知已关闭"
        )
        icon.update_menu()

    def set_mode(provider: str, mode: str):
        def callback(
            icon: pystray.Icon, _item: pystray.MenuItem
        ) -> None:
            set_provider_mode(config_path, provider, mode)
            refresh_icon()

        return callback

    def mode_checked(provider: str, mode: str):
        return lambda _item: (
            load_config(config_path)["providers"][provider]["mode"]
            == mode
        )

    def mode_menu(provider: str) -> pystray.Menu:
        return pystray.Menu(
            *[
                pystray.MenuItem(
                    label,
                    set_mode(provider, mode),
                    checked=mode_checked(provider, mode),
                    radio=True,
                )
                for mode, label in (
                    ("all", "全部通知"),
                    ("ssh-only", "仅 SSH"),
                    ("off", "关闭"),
                )
            ]
        )

    def send_test(
        icon: pystray.Icon, _item: pystray.MenuItem
    ) -> None:
        def worker() -> None:
            ok = False
            try:
                ok = send_test_notification(config_path)
            except Exception:
                pass
            _notify(
                icon,
                "Bark 测试通知已发送。"
                if ok
                else "Bark 测试通知发送失败。",
            )

        threading.Thread(target=worker, daemon=True).start()

    def toggle_autostart(
        icon: pystray.Icon, _item: pystray.MenuItem
    ) -> None:
        try:
            set_autostart(
                not is_autostart_enabled(executable), executable
            )
            icon.update_menu()
        except OSError:
            _notify(icon, "无法更新登录自启动设置。")

    def open_settings(
        icon: pystray.Icon, _item: pystray.MenuItem
    ) -> None:
        try:
            subprocess.Popen(
                settings_command(executable),
                close_fds=True,
            )
        except OSError:
            _notify(icon, "无法打开 Agent-Notify 设置。")

    def exit_tray(
        icon: pystray.Icon, _item: pystray.MenuItem
    ) -> None:
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem(
            "Bark 模式",
            mode_menu("bark"),
        ),
        pystray.MenuItem(
            "飞书模式",
            mode_menu("feishu"),
        ),
        pystray.MenuItem("发送 Bark 测试通知", send_test),
        pystray.MenuItem("打开设置", open_settings),
        pystray.MenuItem(
            "登录时自动启动",
            toggle_autostart,
            checked=lambda _item: is_autostart_enabled(executable),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", exit_tray),
    )
    icon = pystray.Icon(
        "agent-notify",
        _make_icon(_notifications_enabled(config_path)),
        "Agent-Notify",
        menu,
    )
    icon_ref[0] = icon
    threading.Thread(
        target=_watch_stop_event, args=(icon,), daemon=True
    ).start()
    try:
        icon.run()
    finally:
        if controller is not None:
            controller.stop_event.set()
        if mutex_handle and KERNEL32 is not None:
            KERNEL32.CloseHandle(mutex_handle)
    return 0
