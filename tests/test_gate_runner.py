from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

from aiwk.cli import initialize


class GateRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.repo = root / "target"
        self.repo.mkdir()
        initialized = initialize("gate_demo", str(self.repo), str(root / "workflows"))
        self.config_path = Path(initialized["config_path"])
        self.workflow_path = self.config_path.parent / "workflow.yaml"
        self.write_workflow()

    def tearDown(self):
        self.temporary.cleanup()

    def write_workflow(self, build_commands: list[str] | None = None):
        build_commands = build_commands or ["printf 'build ok\\n'"]
        build_yaml = "\n".join(f"        - {command}" for command in build_commands)
        self.workflow_path.write_text(
            f'''project: gate_demo
description: Gate runner tests.
default_stage: build

objective_gates:
  default:
    enabled: true
    description: Deterministic test gate.
    setup:
      commands:
        - printf 'setup ok\\n'
    build:
      commands:
{build_yaml}
    test:
      commands:
        - printf 'test ok\\n'
    result:
      commands:
        - "true"
    checks:
      - name: no_forbidden_marker
        command: 'grep -R "FORBIDDEN_MARKER" .'
        max_count: 0
        counting_instructions: Count matching output lines.

stages:
  build:
    description: Test.
    steps:
      - id: GATE_SS0
        title: Gate test
        model: sonnet
        effort: medium
        objective_gate: default
        phases:
          - scope
          - dev
          - redteam
          - review
          - commit
        prompt:
          scope: Scope.
          dev: Develop.
          redteam: Red team.
          review: Review.
''',
            encoding="utf-8",
        )

    def run_cli(self, gate: str = "default", explicit_paths: bool = False):
        command = [
            sys.executable, "-m", "aiwk", "gate-run",
            "--config", str(self.config_path),
            "--gate", gate,
            "--step", "GATE_SS0",
            "--attempt", "1",
        ]
        if explicit_paths:
            command.extend(["--workflow-spec", str(self.workflow_path), "--repo", str(self.repo)])
        return subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def test_passing_gate_writes_evidence_and_log(self):
        completed = self.run_cli(explicit_paths=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(
            [result[key] for key in ("setup_rc", "build_rc", "test_rc", "result_rc")],
            [0, 0, 0, 0],
        )
        self.assertTrue(result["gate_clean"])
        evidence_path = Path(result["evidence_path"])
        log_path = Path(result["log_path"])
        self.assertTrue(evidence_path.is_file())
        self.assertTrue(log_path.is_file())
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertEqual(evidence["gate_clean"], result["gate_clean"])
        self.assertIn("sections", evidence)
        self.assertIn("duration_seconds", evidence["sections"]["build"][0])
        self.assertIn("integrity", evidence)
        self.assertRegex(evidence["integrity"]["log_sha256"], r"^[0-9a-f]{64}$")
        saved_hash = evidence["integrity"]["evidence_sha256"]
        evidence["integrity"]["evidence_sha256"] = None
        recomputed = hashlib.sha256(
            json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.assertEqual(saved_hash, recomputed)
        self.assertIn("repo_head_before", evidence["integrity"])
        self.assertIn("$ printf 'build ok", log_path.read_text(encoding="utf-8"))

    def test_command_failure_is_successfully_captured(self):
        self.write_workflow(["exit 3", "exit 7", '"true"'])
        completed = self.run_cli()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["build_rc"], 7)
        self.assertFalse(result["gate_clean"])
        evidence = json.loads(Path(result["evidence_path"]).read_text(encoding="utf-8"))
        self.assertEqual(evidence["sections"]["build"][1]["rc"], 7)

    def test_unknown_gate_is_runner_error(self):
        completed = self.run_cli(gate="missing")
        self.assertNotEqual(completed.returncode, 0)
        result = json.loads(completed.stderr)
        self.assertEqual(result["status"], "error")
        self.assertIn("Unknown objective gate", result["error"])

    def test_check_count_over_threshold_fails_gate(self):
        (self.repo / "marker.txt").write_text("FORBIDDEN_MARKER\n", encoding="utf-8")
        completed = self.run_cli()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertGreater(result["check_results"][0]["count"], 0)
        self.assertEqual(result["check_results"][0]["rc"], 0)
        self.assertFalse(result["gate_clean"])

    def test_build_timeout_is_captured_and_fails_gate(self):
        command = f'{sys.executable} -c "import time; time.sleep(2)"'
        self.write_workflow([command])
        text = self.workflow_path.read_text(encoding="utf-8").replace(
            "    build:\n      commands:",
            "    build:\n      timeout_seconds: 0.2\n      commands:",
        )
        self.workflow_path.write_text(text, encoding="utf-8")
        completed = self.run_cli()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["build_rc"], 124)
        self.assertFalse(result["gate_clean"])
        evidence = json.loads(Path(result["evidence_path"]).read_text(encoding="utf-8"))
        command_result = evidence["sections"]["build"][0]
        self.assertTrue(command_result["timed_out"])
        self.assertEqual(command_result["timeout_seconds"], 0.2)
