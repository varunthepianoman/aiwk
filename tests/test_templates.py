from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from aiwk.cli import initialize
from aiwk.render import render
from aiwk.workflow_spec import load_workflow_spec


class TemplateTests(unittest.TestCase):
    def test_templates_list_cli(self):
        completed = subprocess.run(
            [sys.executable, "-m", "aiwk", "templates", "list"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        )
        self.assertEqual(
            json.loads(completed.stdout)["templates"],
            ["generic", "ros2_refactor", "bugfix_redteam"],
        )

    def initialize_template(self, root: Path, name: str) -> Path:
        repo = root / f"repo_{name}"
        repo.mkdir()
        result = initialize(f"demo_{name}", str(repo), str(root / ".aiwk"), name)
        return Path(result["config_path"]).parent

    def test_generic_template_initializes_and_renders(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.initialize_template(Path(directory), "generic")
            spec = load_workflow_spec(project / "workflow.yaml")
            self.assertEqual(spec.commit.mode, "mechanical_all")
            self.assertIn("default", spec.objective_gates)
            self.assertEqual(spec.stages["build"].steps[0].id, "GENERIC_SS0")
            self.assertTrue(Path(render(project / "aiwk.yaml")["output_path"]).is_file())

    def test_ros2_refactor_template_has_placeholders_and_three_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.initialize_template(Path(directory), "ros2_refactor")
            text = (project / "workflow.yaml").read_text(encoding="utf-8")
            self.assertIn("TODO_PACKAGE", text)
            self.assertIn("colcon build", text)
            self.assertNotIn("ur_arci_adapter", text)
            spec = load_workflow_spec(project / "workflow.yaml")
            self.assertEqual(len(spec.stages["build"].steps), 3)
            render(project / "aiwk.yaml")

    def test_bugfix_template_emphasizes_reproduction(self):
        with tempfile.TemporaryDirectory() as directory:
            project = self.initialize_template(Path(directory), "bugfix_redteam")
            text = (project / "workflow.yaml").read_text(encoding="utf-8")
            self.assertIn("Reproduce before fixing", text)
            self.assertIn("regression test", text)
            self.assertEqual(len(load_workflow_spec(project / "workflow.yaml").stages["build"].steps), 2)
            render(project / "aiwk.yaml")

