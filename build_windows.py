#!/usr/bin/env python
"""Build Agent-Notify Windows executables with PyInstaller."""

from pathlib import Path
import shutil
import sys

from PIL import Image
import PyInstaller.__main__


ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
ICON_PATH = BUILD_DIR / "agent-notify.ico"
SOURCE_ICON_PATH = ROOT / "assets" / "agent-notify.png"
SOURCE_SVG_PATH = ROOT / "assets" / "agent-notify.svg"
RUNTIME_DLLS = (
    "libssl-3-x64.dll",
    "libcrypto-3-x64.dll",
    "liblzma.dll",
    "libbz2.dll",
    "libmpdec-4.dll",
    "ffi.dll",
    "libexpat.dll",
    "sqlite3.dll",
)


def collect_runtime_binaries(prefix: Path) -> list[str]:
    bin_dir = prefix / "Library" / "bin"
    binaries = []
    for name in RUNTIME_DLLS:
        path = bin_dir / name
        if path.exists():
            binaries.append(f"{path};.")
    return binaries


def make_icon() -> None:
    from generate_icon_assets import generate

    generate()
    BUILD_DIR.mkdir(exist_ok=True)
    with Image.open(SOURCE_ICON_PATH) as source:
        source.convert("RGBA").save(
            ICON_PATH,
            format="ICO",
            sizes=[(16, 16), (32, 32), (48, 48), (256, 256)],
        )


def build() -> None:
    make_icon()
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)

    common = [
        "--noconfirm",
        "--clean",
        "--onefile",
        "--noupx",
        "--windowed",
        f"--icon={ICON_PATH}",
        f"--add-data={SOURCE_ICON_PATH};assets",
        f"--distpath={DIST_DIR}",
        f"--workpath={BUILD_DIR / 'pyinstaller'}",
        f"--specpath={BUILD_DIR}",
    ]
    for binary in collect_runtime_binaries(Path(sys.prefix)):
        common.append(f"--add-binary={binary}")
    PyInstaller.__main__.run(
        [
            str(ROOT / "desktop_hook.py"),
            "--name=Agent-Notify",
            *common,
        ]
    )


if __name__ == "__main__":
    build()
