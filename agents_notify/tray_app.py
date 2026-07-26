"""Bark-only Windows tray application and login startup management."""

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from typing import Any, Mapping

from PIL import Image, ImageEnhance
import pystray

from .config import load_config, update_config
from .desktop import (
    send_feishu_test_notification,
    send_test_notification,
)
from .diagnostics import write_diagnostic
from .feishu_control import FeishuController
from .feishu_control import MODE_LABELS
from .feishu_service import FeishuWebSocketService
from .resources import resource_path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE_NAME = "Agents-Notify"
LEGACY_RUN_VALUE_NAME = "Agent-Notify"
MUTEX_NAME = r"Local\Agents-Notify-Tray"
STOP_EVENT_NAME = r"Local\Agents-Notify-Tray-Stop"
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


def self_launch_environment(
    environ: Mapping[str, str] | None = None,
    *,
    frozen: bool | None = None,
) -> dict[str, str]:
    environment = dict(environ or os.environ)
    is_frozen = (
        bool(getattr(sys, "frozen", False))
        if frozen is None
        else frozen
    )
    if is_frozen:
        environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return environment


def launch_self(
    executable: Path,
    *arguments: str,
    launcher=subprocess.Popen,
    frozen: bool | None = None,
):
    return launcher(
        [str(executable), *arguments],
        close_fds=True,
        env=self_launch_environment(frozen=frozen),
    )


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
            try:
                registry.DeleteValue(key, LEGACY_RUN_VALUE_NAME)
            except FileNotFoundError:
                pass
        else:
            for value_name in (RUN_VALUE_NAME, LEGACY_RUN_VALUE_NAME):
                try:
                    registry.DeleteValue(key, value_name)
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


def migrate_legacy_autostart(
    executable: Path,
    registry: Any = None,
) -> bool:
    if registry is None:
        import winreg as registry

    try:
        with registry.OpenKey(
            registry.HKEY_CURRENT_USER, RUN_KEY
        ) as key:
            registry.QueryValueEx(key, LEGACY_RUN_VALUE_NAME)
    except FileNotFoundError:
        return False
    set_autostart(True, executable, registry)
    return True


def set_provider_mode(
    config_path: Path, provider: str, mode: str
) -> None:
    update_config(
        config_path,
        lambda config: config["providers"][provider].update(
            {"mode": mode}
        ),
    )


def notification_status_text(config: Mapping[str, Any]) -> str:
    providers = config.get("providers", {})
    bark = providers.get("bark", {})
    feishu = providers.get("feishu", {})
    bark_mode = MODE_LABELS.get(bark.get("mode", "all"), "全部通知")
    feishu_mode = MODE_LABELS.get(
        feishu.get("mode", "off"), "关闭"
    )
    control = "开启" if feishu.get("control_enabled") else "关闭"
    return (
        f"Agents-Notify | Bark：{bark_mode} | "
        f"飞书：{feishu_mode} | 遥控：{control}"
    )


def feishu_control_missing_fields(
    settings: Mapping[str, Any],
) -> tuple[str, ...]:
    fields = (
        ("app_id", settings.get("app_id")),
        ("app_secret", settings.get("app_secret")),
        ("open_id", settings.get("open_id")),
        ("chat_id", settings.get("chat_id")),
    )
    return tuple(label for label, value in fields if not str(value or "").strip())


def set_feishu_control(config_path: Path, enabled: bool) -> None:
    if enabled:
        settings = load_config(config_path)["providers"]["feishu"]
        missing = feishu_control_missing_fields(settings)
        if missing:
            raise ValueError(
                "启用飞书遥控前请先配置：" + "、".join(missing)
            )
    update_config(
        config_path,
        lambda config: config["providers"]["feishu"].update(
            {"control_enabled": enabled}
        ),
    )


def _notifications_enabled(config_path: Path) -> bool:
    config = load_config(config_path)
    return any(
        settings.get("mode") != "off"
        for settings in config["providers"].values()
    )


def build_feishu_controller(
    config_path: Path,
    on_config_changed=None,
) -> FeishuController | None:
    settings = load_config(config_path)["providers"]["feishu"]
    if not settings.get("control_enabled"):
        return None
    client = FeishuWebSocketService(
        str(settings.get("app_id") or ""),
        str(settings.get("app_secret") or ""),
    )
    return FeishuController(
        config_path,
        client,
        on_config_changed=on_config_changed,
    )


def restart_tray(
    executable: Path,
    stop_signal=None,
    launcher=subprocess.Popen,
    sleeper=time.sleep,
    tray_running=None,
    frozen: bool | None = None,
) -> None:
    if stop_signal is None:
        stop_signal = signal_tray_stop
    if tray_running is None:
        tray_running = _tray_instance_running
    stop_signal()
    stopped = False
    for _ in range(50):
        if not tray_running():
            stopped = True
            break
        sleeper(0.1)
    if not stopped:
        raise TimeoutError("旧托盘未能在限定时间内退出。")
    launch_self(
        executable,
        "--tray",
        launcher=launcher,
        frozen=frozen,
    )


def _make_icon(enabled: bool) -> Image.Image:
    with Image.open(resource_path("assets/agents-notify.png")) as source:
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
        icon.notify(message, "Agents-Notify")
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
    controller_ref: list[FeishuController | None] = [None]
    controller_thread_ref: list[threading.Thread | None] = [None]

    def refresh_icon() -> None:
        icon = icon_ref[0]
        if icon is None:
            return
        config = load_config(config_path)
        enabled = _notifications_enabled(config_path)
        icon.icon = _make_icon(enabled)
        icon.title = notification_status_text(config)
        icon.update_menu()

    def start_controller() -> None:
        thread = controller_thread_ref[0]
        if thread is not None and thread.is_alive():
            return
        controller = build_feishu_controller(
            config_path,
            on_config_changed=refresh_icon,
        )
        if controller is None:
            return
        thread = threading.Thread(
            target=controller.run,
            daemon=True,
        )
        controller_ref[0] = controller
        controller_thread_ref[0] = thread
        thread.start()

    def stop_controller() -> None:
        controller = controller_ref[0]
        if controller is not None:
            controller.stop_event.set()
        controller_ref[0] = None
        controller_thread_ref[0] = None

    def sync_controller() -> None:
        settings = load_config(config_path)["providers"]["feishu"]
        if settings.get("control_enabled"):
            start_controller()
        else:
            stop_controller()

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

    def send_bark_test(
        icon: pystray.Icon, _item: pystray.MenuItem
    ) -> None:
        def worker() -> None:
            ok = False
            error = ""
            try:
                ok = send_test_notification(config_path)
            except Exception as exc:
                error = str(exc)
                config = load_config(config_path)
                bark = config["providers"]["bark"]
                feishu = config["providers"]["feishu"]
                write_diagnostic(
                    config_path.parent / "agents-notify.log",
                    f"Bark test failed: {error}",
                    secrets=(
                        bark.get("device_key", ""),
                        feishu.get("open_id", ""),
                        feishu.get("chat_id", ""),
                    ),
                )
            _notify(
                icon,
                "Bark 测试通知已发送。"
                if ok
                else f"Bark 测试失败：{error[:80]}",
            )

        threading.Thread(target=worker, daemon=True).start()

    def send_feishu_test(
        icon: pystray.Icon, _item: pystray.MenuItem
    ) -> None:
        def worker() -> None:
            error = ""
            try:
                ok = send_feishu_test_notification(config_path)
            except Exception as exc:
                ok = False
                error = str(exc)
                config = load_config(config_path)
                bark = config["providers"]["bark"]
                feishu = config["providers"]["feishu"]
                write_diagnostic(
                    config_path.parent / "agents-notify.log",
                    f"Feishu test failed: {error}",
                    secrets=(
                        bark.get("device_key", ""),
                        feishu.get("open_id", ""),
                        feishu.get("chat_id", ""),
                    ),
                )
            _notify(
                icon,
                "飞书测试消息已发送。"
                if ok
                else f"飞书测试失败：{error[:80]}",
            )

        threading.Thread(target=worker, daemon=True).start()

    def toggle_feishu_control(
        icon: pystray.Icon, _item: pystray.MenuItem
    ) -> None:
        settings = load_config(config_path)["providers"]["feishu"]
        target = not bool(settings.get("control_enabled"))
        try:
            set_feishu_control(config_path, target)
        except ValueError as exc:
            _notify(icon, str(exc))
            try:
                launch_self(
                    executable,
                    "--settings-tab",
                    "feishu",
                )
            except OSError:
                pass
            return
        sync_controller()
        refresh_icon()

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
            launch_self(executable)
        except OSError as exc:
            write_diagnostic(
                config_path.parent / "agents-notify.log",
                f"Open settings failed: {exc}",
            )
            _notify(icon, f"无法打开设置：{exc}")

    def exit_tray(
        icon: pystray.Icon, _item: pystray.MenuItem
    ) -> None:
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem(
            lambda _item: (
                "Bark："
                + MODE_LABELS.get(
                    load_config(config_path)["providers"]["bark"][
                        "mode"
                    ],
                    "全部通知",
                )
            ),
            mode_menu("bark"),
        ),
        pystray.MenuItem(
            lambda _item: (
                "飞书："
                + MODE_LABELS.get(
                    load_config(config_path)["providers"]["feishu"][
                        "mode"
                    ],
                    "关闭",
                )
            ),
            mode_menu("feishu"),
        ),
        pystray.MenuItem(
            "启用飞书遥控",
            toggle_feishu_control,
            checked=lambda _item: bool(
                load_config(config_path)["providers"]["feishu"].get(
                    "control_enabled"
                )
            ),
        ),
        pystray.MenuItem("发送 Bark 测试通知", send_bark_test),
        pystray.MenuItem("发送飞书测试消息", send_feishu_test),
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
        "agents-notify",
        _make_icon(_notifications_enabled(config_path)),
        notification_status_text(load_config(config_path)),
        menu,
    )
    icon_ref[0] = icon
    sync_controller()
    threading.Thread(
        target=_watch_stop_event, args=(icon,), daemon=True
    ).start()
    try:
        icon.run()
    finally:
        stop_controller()
        if mutex_handle and KERNEL32 is not None:
            KERNEL32.CloseHandle(mutex_handle)
    return 0
