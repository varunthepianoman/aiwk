from pathlib import Path
import tempfile
import unittest

from aiwk.workflow_spec import load_workflow_spec, starter_workflow


class WorkflowSpecTests(unittest.TestCase):
    def write(self, text: str) -> Path:
        self.temporary = tempfile.TemporaryDirectory()
        path = Path(self.temporary.name) / "workflow.yaml"
        path.write_text(text, encoding="utf-8")
        self.addCleanup(self.temporary.cleanup)
        return path

    def test_starter_workflow_loads(self):
        spec = load_workflow_spec(self.write(starter_workflow("demo")))
        self.assertEqual(spec.project, "demo")
        self.assertEqual(spec.default_stage, "build")
        self.assertEqual(spec.stages["build"].steps[0].phases[-1], "commit")

    def test_missing_stages_fails(self):
        with self.assertRaisesRegex(ValueError, "stages"):
            load_workflow_spec(self.write("project: demo\ndefault_stage: build\n"))

    def test_duplicate_step_ids_fail(self):
        text = starter_workflow("demo")
        step = text[text.index("      - id:"):]
        with self.assertRaisesRegex(ValueError, "Duplicate step id"):
            load_workflow_spec(self.write(text + step))

    def test_unknown_phase_fails(self):
        with self.assertRaisesRegex(ValueError, "Unknown phase"):
            load_workflow_spec(self.write(starter_workflow("demo").replace("          - dev", "          - deploy")))

    def test_missing_phase_prompt_fails(self):
        with self.assertRaisesRegex(ValueError, "Missing prompt"):
            load_workflow_spec(self.write(starter_workflow("demo").replace("          dev: TODO implement the scoped change.\n", "")))

