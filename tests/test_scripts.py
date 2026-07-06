from pathlib import Path
import tempfile
import unittest
import sys

from aiwk.scripts import script_text


class ScriptTests(unittest.TestCase):
    def test_scripts_reference_resolved_config(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "workflows" / "demo" / "aiwk.yaml"
            text = script_text("preflight", config)
            self.assertIn(f"--config {config.resolve()}", text)
            self.assertIn(f"{sys.executable} -m aiwk preflight", text)

    def test_scripts_can_pin_an_explicit_venv_python(self):
        text = script_text("preflight", "aiwk.yaml", "/opt/aiwk/.venv/bin/python")
        self.assertIn("/opt/aiwk/.venv/bin/python -m aiwk preflight", text)

    def test_argument_wrappers(self):
        self.assertIn("--phase", script_text("context-pack", "aiwk.yaml"))
        self.assertIn("--step", script_text("checkpoint", "aiwk.yaml"))
