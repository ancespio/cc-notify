"""Debug hook: 记录所有 stdin 到日志文件，用于诊断 Hook 是否被调用."""
import json
import os
import sys
from datetime import datetime

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hook_debug.log")

try:
    raw = sys.stdin.read()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"=== {ts} ===\n")
        f.write(f"cwd: {os.getcwd()}\n")
        f.write(f"SSH_TTY: {os.environ.get('SSH_TTY', 'N/A')}\n")
        f.write(f"SSH_CONNECTION: {os.environ.get('SSH_CONNECTION', 'N/A')}\n")
        f.write(f"stdin ({len(raw)} chars): {raw}\n")
        try:
            event = json.loads(raw)
            f.write(f"parsed keys: {list(event.keys())}\n")
            f.write(f"event field: {event.get('event') or event.get('hook_event') or 'MISSING'}\n")
        except json.JSONDecodeError:
            f.write("JSON parse FAILED\n")
        f.write("\n")
except Exception as e:
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"ERROR: {e}\n\n")

print(json.dumps({}))
