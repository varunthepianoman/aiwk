from pathlib import Path
import tempfile
import unittest
import sys

from aiwk.cli import initialize
from aiwk.render import render
from aiwk.workflow_spec import starter_workflow


class ClaudeWorkflowRenderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        initialized = initialize("demo", str(root / "repo"), str(root / "workflows"))
        self.config_path = Path(initialized["config_path"])
        self.project_root = self.config_path.parent
        (self.project_root / "workflow.yaml").write_text(starter_workflow("demo"), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def add_objective_gate(self):
        workflow_path = self.project_root / "workflow.yaml"
        text = workflow_path.read_text(encoding="utf-8")
        gate = '''objective_gates:
  default:
    enabled: true
    description: Run deterministic project checks.
    setup:
      commands:
        - python --version
    build:
      commands:
        - python -m py_compile demo.py
    test:
      commands:
        - python -m unittest
    result:
      commands:
        - "true"
    checks:
      - name: no_forbidden_marker
        command: 'grep -R "FORBIDDEN_MARKER" .'
        max_count: 0
        counting_instructions: Count matching output lines.

'''
        text = text.replace("stages:\n", gate + "stages:\n", 1)
        text = text.replace("        phases:\n", "        objective_gate: default\n        phases:\n", 1)
        workflow_path.write_text(text, encoding="utf-8")

    def enable_beads(self):
        workflow_path = self.project_root / "workflow.yaml"
        block = '''beads:
  enabled: true
  project_hint: demo
  require_before_edit: true
  allow_create_issue: true
  allow_remember: true
  before_edit_commands:
    - bd prime || true
    - bd list --status open,in_progress,blocked,deferred,closed || true
  remember_guidance:
    - Use bd remember for durable decisions.

'''
        workflow_path.write_text(
            workflow_path.read_text(encoding="utf-8").replace("stages:\n", block + "stages:\n", 1),
            encoding="utf-8",
        )

    def enable_discovery_and_context_economy(self):
        workflow_path = self.project_root / "workflow.yaml"
        block = '''discovery:
  enabled: true
  model: opus
  effort: high

context_economy:
  max_tool_calls_before_checkpoint: 25
  checkpoint_after_major_test_milestone: true
  require_handoff_before_checkpoint: true

'''
        text = workflow_path.read_text(encoding="utf-8").replace("stages:\n", block + "stages:\n", 1)
        text = text.replace(
            "          scope: TODO write black-box tests/spec checks.\n",
            "          scope: TODO write black-box tests/spec checks.\n          discovery: TODO map relevant files and symbols.\n",
            1,
        )
        workflow_path.write_text(text, encoding="utf-8")

    def test_default_render(self):
        result = render(self.config_path)
        output = self.project_root / "generated" / "demo.claude_workflow.js"
        self.assertEqual(Path(result["output_path"]), output)
        text = output.read_text(encoding="utf-8")
        for expected in (
            "export const meta", "onlyStep", "fromStep", "preflightSummary",
            "handoffPath", "beadsSnapshot", "DEMO_SS0", "TODO implement the scoped change.",
            "mechanical commit runner", "await agent(",
        ):
            self.assertIn(expected, text)

    def test_rendered_workflow_has_mature_control_flow(self):
        output = Path(render(self.config_path)["output_path"])
        text = output.read_text(encoding="utf-8")
        for expected in (
            "MAX_DEV_RED_CYCLES", "MAX_REVIEW_ATTEMPTS", "SCOPING TEST WRITER",
            "ADVERSARIAL RED TEAM", "DEVELOPER FIX PASS", "Code Reviewer",
            "commitAgentPrompt", "fromStep", "onlyStep", "beadsSnapshot",
            "preflightSummary", "handoffPath", "commitAgentPrompt",
        ):
            with self.subTest(marker=expected):
                self.assertIn(expected, text)

    def test_rendered_workflow_has_role_schemas_and_agent_options(self):
        output = Path(render(self.config_path)["output_path"])
        text = output.read_text(encoding="utf-8")
        for expected in (
            "SCOPE_SCHEMA", "DISCOVERY_SCHEMA", "IMPL_SCHEMA", "RED_SCHEMA", "REVIEW_SCHEMA",
            "agentOptions",
            "The Red Team found these failures",
            "Address exactly these Code Reviewer findings", "schema:",
            "handoff_path", "files_inspected", "tests_run", "known_dirty_paths",
            "state/handoffs", "handoffPathFor", "Handoff: ${step.id}",
            "Prior handoff paths:", "Latest gate evidence/log paths:",
        ):
            with self.subTest(marker=expected):
                self.assertIn(expected, text)
        self.assertNotIn("await agent({", text)

    def test_rendered_schemas_have_no_duplicate_required_items(self):
        """The runtime rejects a JSON Schema whose ``required`` array has
        duplicate items. Every rendered schema (after resolving the shared
        ``...HANDOFF_REQUIRED`` spread) must list each field at most once."""
        import re

        text = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")

        handoff_block = re.search(
            r"const HANDOFF_REQUIRED = \[(.*?)\];", text, re.DOTALL
        )
        self.assertIsNotNone(handoff_block, "HANDOFF_REQUIRED constant not found")
        handoff_fields = re.findall(r'"([^"]+)"', handoff_block.group(1))
        self.assertIn("files_changed", handoff_fields)

        # Every literal `required: [ ... ]` array in the rendered script.
        for match in re.finditer(r"required:\s*\[(.*?)\]", text, re.DOTALL):
            body = match.group(1)
            fields = re.findall(r'"([^"]+)"', body)
            if "...HANDOFF_REQUIRED" in body:
                fields = fields + handoff_fields
            with self.subTest(required=body.strip()[:60]):
                self.assertEqual(
                    len(fields), len(set(fields)),
                    f"duplicate required item(s): "
                    f"{[f for f in fields if fields.count(f) > 1]}",
                )

    def test_rendered_workflow_is_runtime_compatible(self):
        """Generated JS must match the Claude Workflow runtime contract.

        Fails on the old, runtime-incompatible output shape: an ES module with
        ``export default async function`` plus Node globals / unsupported agent
        options.
        """
        output = Path(render(self.config_path)["output_path"])
        text = output.read_text(encoding="utf-8")

        # meta must carry a non-empty name for the runtime to accept the script.
        self.assertIn("meta =", text)
        self.assertRegex(text, r'meta =\s*\{[^}]*"name"\s*:\s*"[^"]+"')

        # Runtime-incompatible constructs that must be gone.
        for forbidden in ("export default", "process.env", "permissionMode", "env:"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

        # Top-level runtime-supported invocation style.
        self.assertIn("runWorkflow", text)

        # Reviewer prompt must distinguish pre-commit review from post-commit
        # cleanliness (otherwise review can never accept before the commit phase).
        for phrase in (
            "This review runs before the Commit phase",
            "Do not reject solely because expected in-scope files are modified or untracked",
            "The Commit phase is responsible",
            "If handoffPath is supplied, read it before editing",
            "source/specs win",
            "AIWK context-pack",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

        # Mature workflow semantics must survive the restructure.
        for marker in (
            "MAX_DEV_RED_CYCLES", "MAX_REVIEW_ATTEMPTS", "SCOPING TEST WRITER",
            "ADVERSARIAL RED TEAM", "DEVELOPER FIX PASS", "Code Reviewer",
            "commitAgentPrompt", "onlyStep", "fromStep", "beadsSnapshot",
            "preflightSummary", "handoffPath",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)
        self.assertLess(
            text.index("objective gate ${attempt}"),
            text.index("review ${attempt}"),
        )
        self.assertIn("if (!gateClean) findings.push(formatGateResult(gate))", text)
        self.assertIn("configuredChecksClean", text)
        self.assertIn('gate.status !== "ok"', text)

    def test_rendered_objective_gate_is_enforced_before_review(self):
        self.add_objective_gate()
        output = Path(render(self.config_path)["output_path"])
        text = output.read_text(encoding="utf-8")
        for marker in (
            "GATE_SCHEMA", "buildGatePrompt", "formatGateResult", "computeGateClean",
            "OBJECTIVE BUILD GATE", "setup_rc", "build_rc", "test_rc", "result_rc",
            "check_results", "raw_tail", "gateClean",
            "accepted = gateClean && reviewAccepted(review)",
            "Your acceptance is necessary but not sufficient",
            "You cannot make a red build/test/check pass",
            "The Commit phase is responsible",
            "Do not reject solely because expected in-scope files are modified or untracked",
            "aiwk gate-run", "evidence_path", "log_path", "gate_clean",
            "Do not edit files", "Run exactly this one AIWK command",
            "no_forbidden_marker", "integrity", "evidence_sha256", "log_sha256",
            "timed_out",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)
        self.assertNotIn("Run exactly the command block below", text)
        self.assertNotIn("Run this block verbatim", text)
        self.assertNotIn("python -m py_compile demo.py", text)
        self.assertIn(sys.executable, text)
        self.assertIn(str(self.config_path.resolve()), text)
        self.assertIn(str((self.project_root / "workflow.yaml").resolve()), text)

    def test_review_acceptance_requires_all_review_quality_flags(self):
        output = Path(render(self.config_path)["output_path"])
        text = output.read_text(encoding="utf-8")
        for marker in (
            "function reviewAccepted(review)",
            "review.accepted === true",
            "review.scope_clean === true",
            "review.build_passed === true",
            "review.gtests_passed === true",
            "accepted = gateClean && reviewAccepted(review)",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_workflow_without_objective_gate_still_renders_mature_flow(self):
        output = Path(render(self.config_path)["output_path"])
        text = output.read_text(encoding="utf-8")
        self.assertIn('"objectiveGate": null', text)
        self.assertIn("MAX_DEV_RED_CYCLES", text)
        self.assertIn("Code Reviewer", text)

    def test_mechanical_all_commit_policy_and_clean_status(self):
        output = Path(render(self.config_path)["output_path"])
        text = output.read_text(encoding="utf-8")
        for marker in (
            "COMMIT_SCHEMA", "commitAgentPrompt", "commitPolicyForStep",
            "renderCommitMessage", "mechanical commit runner", "git add -A",
            "git commit -m", "git rev-parse HEAD", 'model: commitPolicy.model',
            'effort: commitPolicy.effort', "commit_rc", "clean_after",
            "commit_left_dirty_tree", "commit_failed", "status_after", "commitResult",
            "Do not selectively stage", "If status_after is not empty",
            "Gate/review must confirm that git add -A is safe",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("NEVER use git add -A", text)

    def test_handoff_propagation_and_checkpoint_policy_render(self):
        output = Path(render(self.config_path)["output_path"])
        text = output.read_text(encoding="utf-8")
        for marker in (
            "const HANDOFF_REQUIRED",
            "Durable handoff requirement:",
            "Write this exact handoff markdown file",
            "state/handoffs",
            "rememberHandoff(handoffState, scope)",
            "rememberHandoff(handoffState, impl)",
            "rememberHandoff(handoffState, red)",
            "rememberGateEvidence(handoffState, gate)",
            "buildReviewerPrompt(step, gate, gateClean, handoffState)",
            "checkpoint_requested",
            'status: "checkpoint"',
            "Context economy rule:",
            "Broad grep/find/read sweeps are allowed only if the handoff is missing",
            "tail -80",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_discovery_enabled_renders_discovery_between_scope_and_dev(self):
        self.enable_discovery_and_context_economy()
        output = Path(render(self.config_path)["output_path"])
        text = output.read_text(encoding="utf-8")
        for marker in (
            '"discovery": {',
            '"enabled": true',
            "=== DISCOVERY AGENT:",
            "DISCOVERY_SCHEMA",
            "Discovery did the broad map for this step",
            "Target the files/symbols named in the Discovery handoff",
            "Tell Developer what NOT to rediscover",
            "max_tool_calls_before_checkpoint",
            "about ${CONTEXT_ECONOMY.max_tool_calls_before_checkpoint} tool calls",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)
        self.assertLess(text.index("SCOPING TEST WRITER"), text.index("DISCOVERY AGENT"))
        self.assertLess(text.index("DISCOVERY AGENT"), text.index("DEVELOPER:"))

    def test_commit_mode_none_is_structured_skip(self):
        workflow = self.project_root / "workflow.yaml"
        workflow.write_text(
            workflow.read_text(encoding="utf-8").replace("mode: mechanical_all", "mode: none", 1),
            encoding="utf-8",
        )
        text = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")
        self.assertIn('"mode": "none"', text)
        self.assertIn('status: "skipped", summary: "commit_mode none"', text)

    def test_beads_enabled_and_disabled_rendering(self):
        disabled = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")
        self.assertIn("BEADS_CONFIG", disabled)
        self.assertIn("beadsSnapshot", disabled)
        self.assertNotIn("LIVE BEADS DISCIPLINE", disabled)
        self.assertNotIn("bd prime", disabled)
        self.enable_beads()
        enabled = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")
        for marker in (
            "BEADS_CONFIG", "getActiveBeadsContext", "withBeadsContext",
            "ACTIVE BEADS PROJECT LEDGER SNAPSHOT", "LIVE BEADS DISCIPLINE",
            "bd prime", "bd list --status", "bd remember", "beadsSnapshot",
        ):
            self.assertIn(marker, enabled)

    def test_render_inlines_durable_context_contents(self):
        project_spec = self.project_root / "spec" / "project.spec.md"
        project_spec.write_text("# Durable marker\n\nBackticks: `safe` and ${runtimeText}.\n", encoding="utf-8")
        output = Path(render(self.config_path)["output_path"])
        text = output.read_text(encoding="utf-8")
        self.assertIn("Durable marker", text)
        self.assertIn("Backticks: `safe` and ${runtimeText}.", text)

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
