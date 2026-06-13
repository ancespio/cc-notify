import tempfile
import unittest
from pathlib import Path

from agent_notify.diagnostics import write_diagnostic


class DiagnosticTests(unittest.TestCase):
    def test_log_redacts_configured_secrets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "agent-notify.log"

            write_diagnostic(
                path,
                "Bark push failed for secret-key ou_owner oc_private",
                secrets=("secret-key", "ou_owner", "oc_private"),
            )
            content = path.read_text(encoding="utf-8")

        self.assertIn("[REDACTED]", content)
        self.assertNotIn("secret-key", content)
        self.assertNotIn("ou_owner", content)
        self.assertNotIn("oc_private", content)
