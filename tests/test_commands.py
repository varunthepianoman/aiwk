from pathlib import Path
import json
import subprocess
import tempfile
import unittest

from aiwk.checkpoint import checkpoint
from aiwk.cli import initialize, preflight
from aiwk.config import load_config
from aiwk.context_pack import create_context_pack


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.strip()


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test User")
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        git(self.repo, "add", "tracked.txt")
        git(self.repo, "commit", "-qm", "initial")
        result = initialize("demo", str(self.repo), str(root / "workflows"))
        self.config_path = Path(result["config_path"])
        self.config = load_config(self.config_path)

    def tearDown(self):
        self.temporary.cleanup()

    def test_preflight_and_context_pack(self):
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        result = preflight(self.config, self.config_path)
        self.assertEqual(result["status"], "dirty")
        self.assertEqual(result["dirty_relevant_files"], ["tracked.txt"])
        context = create_context_pack(self.config, self.config_path, "PHASE_1")
        self.assertTrue(Path(context["handoff_path"]).is_file())
        self.assertTrue(Path(context["context_path"]).is_file())

    def test_rich_context_pack_with_bounded_diff_and_evidence(self):
        (self.repo / "tracked.txt").write_text("\n".join(f"line {i}" for i in range(20)) + "\n", encoding="utf-8")
        evidence = self.config_path.parent / "fake_gate.json"
        evidence.write_text(json.dumps({
            "gate": "default", "gate_clean": False, "build_rc": 7,
            "test_rc": 0, "result_rc": 0, "log_path": "/tmp/gate.log",
        }), encoding="utf-8")
        beads = self.config_path.parent / "beads.txt"
        beads.write_text("issue DEMO-1 in_progress\n", encoding="utf-8")
        result = create_context_pack(
            self.config, self.config_path, "DEV", "STEP_1", True, 5,
            evidence, beads,
        )
        context = json.loads(Path(result["context_path"]).read_text(encoding="utf-8"))
        for key in ("changed_files", "diff_stat", "head", "branch", "status_short", "next_agent_instructions"):
            self.assertIn(key, context)
        self.assertLessEqual(len(context["diff_excerpt"].splitlines()), 5)
        self.assertEqual(context["objective_gate"]["evidence_path"], str(evidence))
        self.assertIn("DEMO-1", context["beads"]["snapshot"])
        handoff = Path(result["handoff_path"]).read_text(encoding="utf-8")
        self.assertIn(str(evidence), handoff)

    def test_checkpoint_and_nothing_to_commit(self):
        (self.repo / "tracked.txt").write_text("changed\n", encoding="utf-8")
        created = checkpoint(self.config, self.config_path, "STEP_1")
        self.assertEqual(created["status"], "committed")
        self.assertEqual(git(self.repo, "log", "-1", "--pretty=%s"), "STEP_1")
        empty = checkpoint(self.config, self.config_path, "STEP_2")
        self.assertEqual(empty["status"], "nothing_to_commit")
