from pathlib import Path
import tempfile
import unittest

from aiwk.cli import initialize
from aiwk.render import render


class ClaudeWorkflowRenderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        initialized = initialize("demo", str(root / "repo"), str(root / "workflows"))
        self.config_path = Path(initialized["config_path"])
        self.project_root = self.config_path.parent

    def tearDown(self):
        self.temporary.cleanup()

    def test_default_render(self):
        result = render(self.config_path)
        output = self.project_root / "generated" / "demo.claude_workflow.js"
        self.assertEqual(Path(result["output_path"]), output)
        text = output.read_text(encoding="utf-8")
        for expected in (
            "export const meta", "onlyStep", "fromStep", "preflightSummary",
            "handoffPath", "beadsSnapshot", "DEMO_SS0", "TODO implement the scoped change.",
            "checkpoint_commit.sh", "await agent(",
        ):
            self.assertIn(expected, text)

    def test_explicit_spec_and_output(self):
        custom_spec = self.project_root / "custom.yaml"
        custom_spec.write_text(
            (self.project_root / "workflow.yaml").read_text(encoding="utf-8").replace("DEMO_SS0", "CUSTOM_SS1"),
            encoding="utf-8",
        )
        output = self.project_root / "elsewhere" / "custom.js"
        result = render(self.config_path, custom_spec, output)
        self.assertEqual(Path(result["workflow_spec"]), custom_spec.resolve())
        self.assertEqual(Path(result["output_path"]), output.resolve())
        self.assertIn("CUSTOM_SS1", output.read_text(encoding="utf-8"))

