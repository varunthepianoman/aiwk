from pathlib import Path
import tempfile
import unittest

from aiwk.cli import initialize
from aiwk.config import load_config, project_folder


class PathTests(unittest.TestCase):
    def test_project_folder_is_derived(self):
        self.assertEqual(project_folder("anything", "demo"), Path("anything/demo"))

    def test_init_creates_structure(self):
        with tempfile.TemporaryDirectory() as directory:
            workflow = Path(directory) / "my_workflows"
            result = initialize("demo", "/some/repo", str(workflow))
            root = workflow / "demo"
            expected = [
                "aiwk.yaml", "spec/project.spec.md", "spec/invariants.yaml", "spec/gates.yaml",
                "scripts/preflight.sh", "scripts/context_pack.sh", "scripts/checkpoint_commit.sh",
                "workflow.yaml", "master_coordinator_prompt.md", "state", "state/handoffs", "logs", "generated",
            ]
            self.assertTrue(all((root / item).exists() for item in expected))
            config = load_config(result["config_path"])
            self.assertEqual(config.project_folder, str(root))
            self.assertEqual(config.workflow_folder, str(workflow))
