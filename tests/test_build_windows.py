import tempfile
import unittest
from pathlib import Path

from PIL import Image

from build_windows import (
    ICON_PATH,
    SOURCE_ICON_PATH,
    SOURCE_SVG_PATH,
    collect_runtime_binaries,
    make_icon,
)


class BuildWindowsTests(unittest.TestCase):
    def test_build_uses_agent_notify_source_icon(self):
        self.assertTrue(SOURCE_ICON_PATH.is_file())
        self.assertTrue(SOURCE_SVG_PATH.is_file())
        svg = SOURCE_SVG_PATH.read_text(encoding="utf-8")
        self.assertIn("<svg", svg)
        self.assertIn("#FAFCF8", svg)
        self.assertIn("#FFFFFF", svg)
        with Image.open(SOURCE_ICON_PATH) as image:
            self.assertEqual(image.size, (1024, 1024))
            self.assertEqual(image.format, "PNG")

    def test_make_icon_converts_custom_png_to_windows_icon(self):
        make_icon()

        self.assertTrue(ICON_PATH.is_file())
        with Image.open(ICON_PATH) as image:
            self.assertEqual(image.format, "ICO")

    def test_collects_conda_runtime_dlls(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prefix = Path(temp_dir)
            bin_dir = prefix / "Library" / "bin"
            bin_dir.mkdir(parents=True)
            for name in (
                "libssl-3-x64.dll",
                "libcrypto-3-x64.dll",
                "ffi.dll",
                "libexpat.dll",
                "sqlite3.dll",
            ):
                (bin_dir / name).write_bytes(b"test")

            binaries = collect_runtime_binaries(prefix)

        names = {Path(item.split(";", 1)[0]).name for item in binaries}
        self.assertIn("libssl-3-x64.dll", names)
        self.assertIn("libcrypto-3-x64.dll", names)
        self.assertIn("ffi.dll", names)
        self.assertIn("libexpat.dll", names)
        self.assertIn("sqlite3.dll", names)


if __name__ == "__main__":
    unittest.main()
