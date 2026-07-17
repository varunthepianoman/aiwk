from pathlib import Path
import tempfile
import unittest
import sys
import os
import shutil
import subprocess
import re
import json

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

    def test_durable_context_embedded_in_full(self):
        # Durable spec/invariants/gates are authoritative in-prompt context and
        # must embed whole -- no length bound. A file past the former 6000-char
        # cap must appear in full, tail included, with no truncation marker.
        spec_dir = self.project_root / "spec"
        spec_dir.mkdir(parents=True, exist_ok=True)
        marker = "UNIQUE_TAIL_MARKER_ZZ"
        big = "invariants:\n" + "".join(
            f"  - id: pad_{i}\n    rule: {'x' * 80}\n" for i in range(120)
        ) + f"  - id: tail\n    rule: {marker}\n"
        self.assertGreater(len(big), 6000)
        (spec_dir / "invariants.yaml").write_text(big, encoding="utf-8")
        result = render(self.config_path)
        text = Path(result["output_path"]).read_text(encoding="utf-8")
        self.assertIn(marker, text)
        self.assertNotIn("[truncated", text)

    def test_default_render(self):
        result = render(self.config_path)
        output = self.project_root / "generated" / "demo.claude_workflow.js"
        self.assertEqual(Path(result["output_path"]), output)
        text = output.read_text(encoding="utf-8")
        for expected in (
            "export const meta", "onlyStep", "fromStep", "preflightSummary",
            "handoffPath", "startAtRole", "beadsSnapshot", "DEMO_SS0", "TODO implement the scoped change.",
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
            "preflightSummary", "handoffPath", "startAtRole", "commitAgentPrompt",
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
            "preflightSummary", "handoffPath", "startAtRole",
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

    def test_start_at_role_fresh_entry_control_flow_renders(self):
        text = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")
        for marker in (
            "START_AT_ROLE = normalizeStartAtRole",
            "startAtRole_requires_onlyStep",
            "startAtRole_requires_handoffPath_or_gateEvidencePath",
            "validateStartAtRoleForStep(step, START_AT_ROLE)",
            "roleIsAtOrAfter(START_AT_ROLE, \"scope\")",
            "roleIsAtOrAfter(START_AT_ROLE, \"discovery\")",
            "skipInitialDevForRedteamEntry",
            "START_AT_ROLE === \"redteam\"",
            "skipFixForDirectGateOrReviewEntry",
            "[\"gate\", \"review\"].includes(START_AT_ROLE)",
            "START_AT_ROLE === \"commit\" ? true",
            "roleIsAtOrAfter(START_AT_ROLE, \"commit\")",
            "WORKFLOW_ARGS.gateEvidencePath",
            "RESUME_CHANGED_PATHS",
            "RESUME_FINDINGS",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_rendered_workflow_passes_available_javascript_syntax_check(self):
        output = Path(render(self.config_path)["output_path"])
        node = shutil.which("node")
        code = Path("/usr/share/code/code")
        if node:
            command = [node, "--check", str(output)]
            env = None
        elif code.exists():
            command = [str(code), "--check", str(output)]
            env = {**os.environ, "ELECTRON_RUN_AS_NODE": "1"}
        else:
            self.skipTest("No node-compatible syntax checker available")
        subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

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
            "invokeSubstantiveRoleWithContinuations",
            "rememberHandoff(state, output)",
            "rememberGateEvidence(handoffState, gate)",
            "buildReviewerPrompt(step, gate, gateClean, handoffState, attempt, continuation",
            "checkpoint_requested",
            "checkpoint_continuation_limit_exceeded",
            'status: "checkpoint"',
            "validHandoffFor(output, expectedHandoffPath)",
            "invalid_handoff_path",
            "MAX_CHECKPOINT_CONTINUATIONS",
            "Context economy rule:",
            "Broad grep/find/read sweeps are allowed only if the handoff is missing",
            "Do not checkpoint or exit merely because the transcript or tool-call count is growing",
            "tail -80",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)
        self.assertNotIn("If you approach about", text)
        self.assertNotIn("max_tool_calls_before_checkpoint} tool calls", text)

    def test_unique_handoff_paths_include_role_cycle_attempt_and_continuation(self):
        text = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")
        for marker in (
            "_${sanitizePathComponent(role).toUpperCase()}_C${Number(cycle || 0)}_A${Number(attempt || 0)}_K${Number(continuation || 0)}_",
            'role: "scope", cycle: 0, attempt: 0',
            'role: "dev", cycle, attempt: 0',
            'role: "redteam", cycle, attempt: 0',
            'role: "dev_fix", cycle: 0, attempt',
            'role: "review", cycle: 0, attempt',
            "`dev_fix_${attempt}_k${continuation}`",
            "`review_${attempt}_k${continuation}`",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_checkpoint_continuation_reinvokes_same_role(self):
        text = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")
        for marker in (
            "while (continuation <= MAX_CHECKPOINT_CONTINUATIONS)",
            "checkpointHandoffPath = output.handoff_path",
            "remainingWork = output.remaining_work || []",
            "continuation += 1",
            "continue;",
            "This is the same logical role and same step continuing after a checkpoint",
            "Do not consume a new Red-Team cycle or reset reviewer-attempt state",
            "Write a new unique continuation handoff path",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_targeted_context_propagates_to_later_roles(self):
        text = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")
        for marker in (
            "Current changed paths reported by prior agents:",
            "Compact test summary from prior agents:",
            "Known dirty paths reported by prior agents:",
            "Allowed edit paths:",
            "Forbidden scope:",
            "Specific findings being addressed:",
            "priorContextBlock(handoffState, redFindings)",
            "priorContextBlock(handoffState, priorReviewFindings)",
            "priorContextBlock(state, findings)",
            "gateEvidencePaths",
            "changedPaths",
            "testsRun",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_reviewer_prompt_uses_current_state_wording(self):
        text = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")
        for marker in (
            "Review the current repository diff, durable handoffs, changed paths, and fresh objective-gate evidence",
            "Use targeted verification around concrete file, symbol, command, and evidence references",
            "Do not assume every reviewed change came solely from the latest Developer invocation",
            "Your acceptance is necessary but not sufficient",
            "You cannot make a red build/test/check pass",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)
        self.assertNotIn("uncommitted Developer diff", text)

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
            "Do not checkpoint or exit merely because the transcript or tool-call count is growing",
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
        workflow_path = self.project_root / "workflow.yaml"
        workflow_path.write_text(
            workflow_path.read_text(encoding="utf-8").replace(
                "stages:\n", "beads:\n  enabled: false\n\nstages:\n", 1
            ),
            encoding="utf-8",
        )
        disabled = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")
        self.assertIn("beadsSnapshot", disabled)
        for forbidden in (
            "BEADS_CONFIG", "LIVE BEADS DISCIPLINE", "ACTIVE BEADS PROJECT LEDGER SNAPSHOT",
            "bd prime", "bd list", "bd create", "bd update", "bd remember",
            "Use bd remember", "create one only if", "Beads issue",
            "Do not run bd commands", "OPTIONAL EXTERNAL MEMORY SNAPSHOT",
        ):
            with self.subTest(default_forbidden=forbidden):
                self.assertNotIn(forbidden, disabled)
        self.enable_beads()
        enabled = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")
        for marker in (
            "EXTERNAL_MEMORY_CONFIG", "OPTIONAL EXTERNAL MEMORY SNAPSHOT",
            "advisory operator-supplied long-term memory",
            "Current source, specs, gate evidence, and git state override this snapshot",
            "Do not mutate the external memory system",
            "Do not run bd commands", "beadsSnapshot",
        ):
            self.assertIn(marker, enabled)
        for forbidden in (
            "LIVE BEADS DISCIPLINE", "ACTIVE BEADS PROJECT LEDGER SNAPSHOT",
            "bd prime", "bd list --status", "bd create", "bd update",
            "bd remember", "Use bd remember", "create one only if", "Beads issue",
        ):
            self.assertNotIn(forbidden, enabled)

    def test_generated_prompts_scrub_legacy_live_beads_commands(self):
        project_spec = self.project_root / "spec" / "project.spec.md"
        project_spec.write_text("Run bd prime and use bd remember before edits.\n", encoding="utf-8")
        workflow = self.project_root / "workflow.yaml"
        workflow.write_text(
            workflow.read_text(encoding="utf-8").replace(
                "TODO implement the scoped change.",
                "Run bd list before implementing.",
            ),
            encoding="utf-8",
        )
        text = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")
        self.assertIn("external-memory command suppressed", text)
        self.assertNotIn("bd prime", text)
        self.assertNotIn("bd list", text)
        self.assertNotIn("bd remember", text)

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

    # ------------------------------------------------------------------
    # Optional modules: code-review filter and fanned red team.
    # ------------------------------------------------------------------

    def enable_code_review(self, placement="pre_redteam"):
        workflow_path = self.project_root / "workflow.yaml"
        block = (
            "        code_review:\n"
            "          enabled: true\n"
            f"          placement: {placement}\n"
            "          effort: high\n"
            "          apply_fixes: true\n"
        )
        text = workflow_path.read_text(encoding="utf-8").replace("        phases:\n", block + "        phases:\n", 1)
        workflow_path.write_text(text, encoding="utf-8")

    def enable_redteam_fan(self):
        workflow_path = self.project_root / "workflow.yaml"
        block = (
            "        redteam_fan:\n"
            "          enabled: true\n"
            "          verify_votes: 3\n"
            "          completeness_critic: true\n"
            "          lenses:\n"
            "            - key: payload-bound\n"
            "              prompt: attack the receive-boundary payload limit\n"
            "            - key: fault-drop\n"
            "              prompt: attack connection disposition after a fault\n"
        )
        text = workflow_path.read_text(encoding="utf-8").replace("        phases:\n", block + "        phases:\n", 1)
        workflow_path.write_text(text, encoding="utf-8")

    def test_modules_disabled_are_inert_and_config_defaults_false(self):
        """When neither optional module is configured, the generated workflow's
        ALL_STEPS carries both config blobs with enabled:false, so the always-
        present helper functions never fire. The module code is dormant
        infrastructure (like formatRedFindings), gated entirely by the runtime
        enabled checks -- a plain spec runs the exact single-agent route."""
        text = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")
        steps_match = re.search(r"const ALL_STEPS = (\{.*?\});\nconst MAX_DEV_RED_CYCLES", text, re.DOTALL)
        self.assertIsNotNone(steps_match)
        steps = json.loads(steps_match.group(1))
        step = steps["build"]["steps"][0]
        self.assertFalse(step["codeReview"]["enabled"])
        self.assertFalse(step["redteamFan"]["enabled"])
        self.assertEqual(step["redteamFan"]["lenses"], [])
        # The runtime gates guarantee inertness: the single-agent red team is only
        # skipped when the fan flag is true, and the /code-review filter only runs
        # when its flag is true.
        self.assertIn("if (step.redteamFan && step.redteamFan.enabled)", text)
        self.assertIn("step.codeReview && step.codeReview.enabled", text)

    def test_code_review_module_renders_when_enabled(self):
        self.enable_code_review("pre_redteam")
        text = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")
        for marker in (
            "CODE_REVIEW_SCHEMA", "runCodeReview", "codeReviewBlocking",
            "formatCodeReviewFindings", "CODE-REVIEW FILTER", "/code-review skill",
            "code_review_blocking_finding",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_redteam_fan_module_renders_when_enabled(self):
        self.enable_redteam_fan()
        text = Path(render(self.config_path)["output_path"]).read_text(encoding="utf-8")
        for marker in (
            "runFannedRedTeam", "FAN_VERDICT_SCHEMA", "FAN_CRITIC_SCHEMA",
            "FANNED RED TEAM LENS", "attack:", "verify:", "payload-bound",
            "step.redteamFan && step.redteamFan.enabled",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_modules_render_passes_javascript_syntax_check(self):
        self.enable_code_review("pre_redteam")
        self.enable_redteam_fan()
        output = Path(render(self.config_path)["output_path"])
        node = shutil.which("node")
        code = Path("/usr/share/code/code")
        if node:
            command = [node, "--check", str(output)]
            env = None
        elif code.exists():
            command = [str(code), "--check", str(output)]
            env = {**os.environ, "ELECTRON_RUN_AS_NODE": "1"}
        else:
            self.skipTest("No node-compatible syntax checker available")
        subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
