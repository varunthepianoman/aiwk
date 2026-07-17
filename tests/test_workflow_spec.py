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
        self.assertFalse(spec.discovery.enabled)
        self.assertEqual(spec.context_economy.max_tool_calls_before_checkpoint, 30)
        self.assertEqual(spec.context_economy.max_checkpoint_continuations, 1)

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

    def gate_workflow(self) -> str:
        gates = '''objective_gates:
  default:
    enabled: true
    description: Deterministic checks.
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
        counting_instructions: Count matching output lines.

'''
        workflow = starter_workflow("demo").replace(
            "        phases:\n", "        objective_gate: default\n        phases:\n"
        )
        return workflow.replace("stages:\n", gates + "stages:\n", 1)

    def test_objective_gates_parse_and_step_reference_resolves(self):
        spec = load_workflow_spec(self.write(self.gate_workflow()))
        gate = spec.objective_gates["default"]
        self.assertEqual(gate.build_commands, ["python -m py_compile demo.py"])
        self.assertEqual(gate.checks[0].name, "no_forbidden_marker")
        self.assertEqual(spec.stages["build"].steps[0].objective_gate, "default")

    def test_check_max_count_defaults_to_zero(self):
        spec = load_workflow_spec(self.write(self.gate_workflow()))
        self.assertEqual(spec.objective_gates["default"].checks[0].max_count, 0)

    def test_unknown_objective_gate_reference_fails(self):
        text = starter_workflow("demo").replace(
            "        phases:\n", "        objective_gate: missing\n        phases:\n"
        )
        with self.assertRaisesRegex(ValueError, "unknown objective_gate 'missing'"):
            load_workflow_spec(self.write(text))

    def test_objective_gate_commands_must_be_strings(self):
        text = self.gate_workflow().replace("        - python --version", "        - 7")
        with self.assertRaisesRegex(ValueError, "setup commands must be strings"):
            load_workflow_spec(self.write(text))

    def test_objective_gate_check_requires_command(self):
        text = self.gate_workflow().replace(
            "        command: 'grep -R \"FORBIDDEN_MARKER\" .'\n", ""
        )
        with self.assertRaisesRegex(ValueError, "requires a string command"):
            load_workflow_spec(self.write(text))

    def test_command_with_colon_remains_a_scalar(self):
        text = self.gate_workflow().replace(
            "        - python --version", "        - echo protocol:value"
        )
        spec = load_workflow_spec(self.write(text))
        self.assertEqual(spec.objective_gates["default"].setup_commands, ["echo protocol:value"])

    def test_top_level_commit_policy_parses(self):
        spec = load_workflow_spec(self.write(starter_workflow("demo")))
        self.assertEqual(spec.commit.mode, "mechanical_all")
        self.assertEqual(spec.commit.effort, "low")

    def test_commit_mode_none_and_step_override(self):
        text = starter_workflow("demo").replace("  mode: mechanical_all", "  mode: none")
        text = text.replace(
            "        phases:\n",
            "        commit:\n          mode: mechanical_all\n        phases:\n",
            1,
        )
        spec = load_workflow_spec(self.write(text))
        self.assertEqual(spec.commit.mode, "none")
        self.assertEqual(spec.stages["build"].steps[0].commit.mode, "mechanical_all")

    def test_unknown_commit_mode_fails(self):
        with self.assertRaisesRegex(ValueError, "mode must be one of"):
            load_workflow_spec(self.write(starter_workflow("demo").replace("mechanical_all", "magic", 1)))

    def test_invalid_commit_message_and_unknown_variable_fail(self):
        with self.assertRaisesRegex(ValueError, "message_template must be a string"):
            load_workflow_spec(self.write(starter_workflow("demo").replace(
                'message_template: "{step_id}: {step_title}"', "message_template: 7"
            )))
        with self.assertRaisesRegex(ValueError, "unknown variable"):
            load_workflow_spec(self.write(starter_workflow("demo").replace(
                "{step_title}", "{mystery}"
            )))

    def test_objective_gate_timeout_validation(self):
        text = self.gate_workflow().replace(
            "    enabled: true", "    enabled: true\n    timeout_seconds: -1", 1
        )
        with self.assertRaisesRegex(ValueError, "positive number"):
            load_workflow_spec(self.write(text))

    def test_beads_defaults_disabled_and_enabled_config_parses(self):
        disabled = load_workflow_spec(self.write(starter_workflow("demo")))
        self.assertFalse(disabled.beads.enabled)
        self.assertEqual(disabled.external_memory.mode, "disabled")
        block = '''beads:
  enabled: true
  project_hint: demo-board
  require_before_edit: true
  allow_create_issue: true
  allow_remember: true
  status_filter: open,in_progress
  before_edit_commands:
    - bd prime || true
    - bd list --status open,in_progress || true
  remember_guidance:
    - Use bd remember for durable decisions.

'''
        text = starter_workflow("demo").replace("stages:\n", block + "stages:\n", 1)
        enabled = load_workflow_spec(self.write(text))
        self.assertTrue(enabled.beads.enabled)
        self.assertEqual(enabled.beads.project_hint, "demo-board")
        self.assertEqual(len(enabled.beads.before_edit_commands), 2)
        self.assertEqual(enabled.external_memory.mode, "snapshot")
        self.assertEqual(enabled.external_memory.label, "beads")
        self.assertTrue(enabled.external_memory.include_in_agent_prompts)

    def test_external_memory_snapshot_config_parses(self):
        block = '''external_memory:
  mode: snapshot
  label: operator-notes
  include_in_context_pack: true
  include_in_agent_prompts: true

'''
        spec = load_workflow_spec(self.write(starter_workflow("demo").replace("stages:\n", block + "stages:\n", 1)))
        self.assertEqual(spec.external_memory.mode, "snapshot")
        self.assertEqual(spec.external_memory.label, "operator-notes")
        self.assertTrue(spec.external_memory.include_in_context_pack)
        self.assertTrue(spec.external_memory.include_in_agent_prompts)

    def test_invalid_external_memory_config_fails(self):
        with self.assertRaisesRegex(ValueError, "external_memory.mode"):
            load_workflow_spec(self.write(starter_workflow("demo").replace(
                "stages:\n", "external_memory:\n  mode: live\n\nstages:\n", 1
            )))

    def test_invalid_beads_types_fail(self):
        text = starter_workflow("demo").replace(
            "stages:\n", "beads:\n  enabled: yes\n\nstages:\n", 1
        )
        with self.assertRaisesRegex(ValueError, "beads.enabled must be a boolean"):
            load_workflow_spec(self.write(text))
        text = starter_workflow("demo").replace(
            "stages:\n", "beads:\n  before_edit_commands: nope\n\nstages:\n", 1
        )
        with self.assertRaisesRegex(ValueError, "list of strings"):
            load_workflow_spec(self.write(text))

    def test_discovery_config_top_level_and_step_override_parse(self):
        block = '''discovery:
  enabled: true
  model: opus
  effort: high

context_economy:
  max_tool_calls_before_checkpoint: 25
  checkpoint_after_major_test_milestone: true
  require_handoff_before_checkpoint: true
  max_checkpoint_continuations: 2

'''
        text = starter_workflow("demo").replace("stages:\n", block + "stages:\n", 1)
        text = text.replace(
            "        phases:\n",
            "        discovery:\n          enabled: false\n          model: sonnet\n          effort: medium\n        phases:\n",
            1,
        )
        spec = load_workflow_spec(self.write(text))
        self.assertTrue(spec.discovery.enabled)
        self.assertEqual(spec.discovery.model, "opus")
        self.assertEqual(spec.context_economy.max_tool_calls_before_checkpoint, 25)
        self.assertEqual(spec.context_economy.max_checkpoint_continuations, 2)
        step = spec.stages["build"].steps[0]
        self.assertFalse(step.discovery.enabled)
        self.assertEqual(step.discovery.model, "sonnet")

    def test_explicit_discovery_phase_enables_discovery_with_default_prompt(self):
        text = starter_workflow("demo").replace("          - dev\n", "          - discovery\n          - dev\n", 1)
        spec = load_workflow_spec(self.write(text))
        step = spec.stages["build"].steps[0]
        self.assertIn("discovery", step.phases)
        self.assertTrue(step.discovery.enabled)

    def test_invalid_discovery_and_context_economy_types_fail(self):
        with self.assertRaisesRegex(ValueError, "top-level discovery.enabled must be a boolean"):
            load_workflow_spec(self.write(starter_workflow("demo").replace(
                "stages:\n", "discovery:\n  enabled: yes\n\nstages:\n", 1
            )))
        with self.assertRaisesRegex(ValueError, "positive integer"):
            load_workflow_spec(self.write(starter_workflow("demo").replace(
                "stages:\n", "context_economy:\n  max_tool_calls_before_checkpoint: 0\n\nstages:\n", 1
            )))
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            load_workflow_spec(self.write(starter_workflow("demo").replace(
                "stages:\n", "context_economy:\n  max_checkpoint_continuations: -1\n\nstages:\n", 1
            )))

    def test_documented_example_workflows_parse(self):
        repo = Path(__file__).resolve().parents[1]
        simple = load_workflow_spec(repo / "examples" / "workflow_simple.yaml")
        complex_spec = load_workflow_spec(repo / "examples" / "workflow_complex_discovery.yaml")
        self.assertFalse(simple.stages["build"].steps[0].discovery.enabled)
        self.assertTrue(complex_spec.stages["build"].steps[0].discovery.enabled)
        self.assertEqual(complex_spec.commit.mode, "mechanical_all")

    def test_modules_example_workflow_parses(self):
        repo = Path(__file__).resolve().parents[1]
        spec = load_workflow_spec(repo / "examples" / "workflow_fan_redteam_and_code_review.yaml")
        step = spec.stages["build"].steps[0]
        self.assertTrue(step.code_review.enabled)
        self.assertEqual(step.code_review.placement, "pre_redteam")
        self.assertTrue(step.redteam_fan.enabled)
        self.assertEqual([lens.key for lens in step.redteam_fan.lenses],
                         ["payload-bound", "fault-drop", "session-teardown", "serialized-txn"])
        self.assertEqual(step.redteam_fan.verify_votes, 3)

    # --- code_review module ---

    def test_code_review_defaults_disabled(self):
        spec = load_workflow_spec(self.write(starter_workflow("demo")))
        self.assertFalse(spec.code_review.enabled)
        step = spec.stages["build"].steps[0]
        self.assertFalse(step.code_review.enabled)
        self.assertEqual(step.code_review.placement, "post_dev")
        self.assertEqual(step.code_review.scope, "diff")

    def test_code_review_top_level_and_step_override_parse(self):
        block = "code_review:\n  enabled: true\n  placement: final\n  effort: max\n\n"
        text = starter_workflow("demo").replace("stages:\n", block + "stages:\n", 1)
        text = text.replace(
            "        phases:\n",
            "        code_review:\n          enabled: true\n          placement: pre_redteam\n          apply_fixes: true\n          scope: step\n        phases:\n",
            1,
        )
        spec = load_workflow_spec(self.write(text))
        self.assertEqual(spec.code_review.placement, "final")
        self.assertEqual(spec.code_review.effort, "max")
        step = spec.stages["build"].steps[0]
        self.assertEqual(step.code_review.placement, "pre_redteam")
        self.assertTrue(step.code_review.apply_fixes)
        self.assertEqual(step.code_review.scope, "step")

    def test_code_review_invalid_enum_values_fail(self):
        for block, pattern in [
            ("code_review:\n  enabled: true\n  placement: someday\n\n", "placement must be one of"),
            ("code_review:\n  enabled: true\n  effort: extreme\n\n", "effort must be one of"),
            ("code_review:\n  enabled: true\n  scope: everything\n\n", "scope must be one of"),
        ]:
            with self.assertRaisesRegex(ValueError, pattern):
                load_workflow_spec(self.write(starter_workflow("demo").replace("stages:\n", block + "stages:\n", 1)))

    def test_code_review_requires_dev_phase(self):
        text = starter_workflow("demo").replace(
            "        phases:\n          - scope\n          - dev\n",
            "        code_review:\n          enabled: true\n        phases:\n          - scope\n",
            1,
        )
        with self.assertRaisesRegex(ValueError, "code_review.enabled requires a 'dev' phase"):
            load_workflow_spec(self.write(text))

    # --- redteam_fan module ---

    def test_redteam_fan_defaults_disabled(self):
        spec = load_workflow_spec(self.write(starter_workflow("demo")))
        self.assertFalse(spec.redteam_fan.enabled)
        step = spec.stages["build"].steps[0]
        self.assertFalse(step.redteam_fan.enabled)
        self.assertEqual(step.redteam_fan.verify_votes, 1)
        self.assertEqual(step.redteam_fan.lenses, ())

    def test_redteam_fan_step_config_parses(self):
        fan = ("        redteam_fan:\n          enabled: true\n          verify_votes: 3\n"
               "          completeness_critic: true\n          lenses:\n"
               "            - key: lens-a\n              prompt: attack a\n"
               "            - key: lens-b\n              prompt: attack b\n")
        text = starter_workflow("demo").replace("        phases:\n", fan + "        phases:\n", 1)
        spec = load_workflow_spec(self.write(text))
        step = spec.stages["build"].steps[0]
        self.assertTrue(step.redteam_fan.enabled)
        self.assertEqual(step.redteam_fan.verify_votes, 3)
        self.assertTrue(step.redteam_fan.completeness_critic)
        self.assertEqual([lens.key for lens in step.redteam_fan.lenses], ["lens-a", "lens-b"])

    def test_redteam_fan_requires_two_lenses_when_enabled(self):
        fan = ("        redteam_fan:\n          enabled: true\n          lenses:\n"
               "            - key: only-one\n              prompt: attack\n")
        text = starter_workflow("demo").replace("        phases:\n", fan + "        phases:\n", 1)
        with self.assertRaisesRegex(ValueError, "requires at least 2 lenses"):
            load_workflow_spec(self.write(text))

    def test_redteam_fan_duplicate_lens_key_fails(self):
        fan = ("        redteam_fan:\n          enabled: true\n          lenses:\n"
               "            - key: dup\n              prompt: a\n"
               "            - key: dup\n              prompt: b\n")
        text = starter_workflow("demo").replace("        phases:\n", fan + "        phases:\n", 1)
        with self.assertRaisesRegex(ValueError, "duplicate key 'dup'"):
            load_workflow_spec(self.write(text))

    def test_redteam_fan_invalid_verify_votes_fails(self):
        fan = ("        redteam_fan:\n          enabled: true\n          verify_votes: 0\n          lenses:\n"
               "            - key: a\n              prompt: a\n"
               "            - key: b\n              prompt: b\n")
        text = starter_workflow("demo").replace("        phases:\n", fan + "        phases:\n", 1)
        with self.assertRaisesRegex(ValueError, "verify_votes must be a positive integer"):
            load_workflow_spec(self.write(text))

    def test_redteam_fan_requires_redteam_phase(self):
        # A step with dev but no redteam phase cannot enable the fan.
        fan = ("        redteam_fan:\n          enabled: true\n          lenses:\n"
               "            - key: a\n              prompt: a\n"
               "            - key: b\n              prompt: b\n")
        text = starter_workflow("demo").replace(
            "        phases:\n          - scope\n          - dev\n          - redteam\n",
            fan + "        phases:\n          - scope\n          - dev\n",
            1,
        )
        with self.assertRaisesRegex(ValueError, "redteam_fan.enabled requires a 'redteam' phase"):
            load_workflow_spec(self.write(text))
