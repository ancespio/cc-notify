#!/usr/bin/env python
"""兼容旧启动方式，转发到 Agents-Notify 的统一托盘入口。"""

from desktop_hook import main


if __name__ == "__main__":
    raise SystemExit(main(["--tray"]))
