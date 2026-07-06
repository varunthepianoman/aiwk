"""Render a durable AIWK workflow as mature Claude Workflow JavaScript."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
import sys

from ..config import Config
from ..workflow_spec import WorkflowSpec


def _json(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


def _read_context_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"(missing: {path})"


def render_claude_workflow(
    config: Config,
    config_path: Path,
    spec: WorkflowSpec,
    workflow_spec_path: Path | None = None,
) -> str:
    project_root = config_path.resolve().parent
    workflow_spec_path = (workflow_spec_path or project_root / "workflow.yaml").resolve()
    repo = str(Path(config.repo).expanduser().resolve())
    context_paths = {
        "projectSpecPath": project_root / "spec" / "project.spec.md",
        "invariantsPath": project_root / "spec" / "invariants.yaml",
        "gatesPath": project_root / "spec" / "gates.yaml",
        "statePath": project_root / "state",
    }
    static_context = {
        "project": config.project,
        "repo": repo,
        "projectFolder": str(project_root),
        "aiwkConfigPath": str(config_path.resolve()),
        "workflowSpecPath": str(workflow_spec_path),
        "pythonPath": sys.executable,
        **{name: str(path) for name, path in context_paths.items()},
    }
    durable_context = {
        "projectSpec": _read_context_file(context_paths["projectSpecPath"]),
        "invariants": _read_context_file(context_paths["invariantsPath"]),
        "gates": _read_context_file(context_paths["gatesPath"]),
    }
    def rendered_gate(gate_name: str | None) -> dict[str, object] | None:
        if gate_name is None:
            return None
        gate = spec.objective_gates[gate_name]
        return {
            "name": gate_name,
            "enabled": gate.enabled,
            "description": gate.description,
            "checks": [
                {
                    "name": check.name,
                    "max_count": check.max_count,
                }
                for check in gate.checks
            ],
        }

    def rendered_commit(step) -> dict[str, str]:
        policy = step.commit or spec.commit
        return {
            "mode": policy.mode,
            "messageTemplate": policy.message_template,
            "model": policy.model,
            "effort": policy.effort,
        }

    stages = {
        name: {
            "description": stage.description,
            "steps": [
                {
                    "id": step.id,
                    "title": step.title,
                    "model": step.model,
                    "effort": step.effort,
                    "phases": step.phases,
                    "prompt": step.prompt,
                    "objectiveGate": rendered_gate(step.objective_gate),
                    "commitPolicy": rendered_commit(step),
                    "stage": name,
                }
                for step in stage.steps
            ],
        }
        for name, stage in spec.stages.items()
    }
    uses_mechanical_paths = any(
        (step.commit or spec.commit).mode == "mechanical_paths"
        for stage in spec.stages.values() for step in stage.steps
    )
    beads_config = asdict(spec.beads)
    if spec.beads.enabled:
        beads_context_js = r'''function getActiveBeadsContext(runtime) {
  return runtime.BEADS_LEDGER_SNAPSHOT || `(no beadsSnapshot supplied; project hint: ${BEADS_CONFIG.project_hint || "none"})`;
}

function beadsContext(runtime) {
  const commands = (BEADS_CONFIG.before_edit_commands || []).map((command) => `  ${command}`).join("\n") || "  (no commands configured)";
  const guidance = (BEADS_CONFIG.remember_guidance || []).map((item) => `  - ${item}`).join("\n");
  return `=== ACTIVE BEADS PROJECT LEDGER SNAPSHOT ===
The workflow runtime cannot assume transcript memory. Use this snapshot to avoid duplicate work and understand blockers.
If this ledger conflicts with committed source/specs, committed source/specs and this workflow's explicit scope win.
${getActiveBeadsContext(runtime)}

=== LIVE BEADS DISCIPLINE ===
Before modifying code, run:
${commands}
If a relevant issue exists, update it. Create one only when allowed and useful.
Use bd remember for durable decisions when allowed. Do not use ad-hoc markdown task lists as durable trackers.
${guidance}`;
}'''
        beads_role_js = r'''function beadsRoleGuidance(role) {
  const guidance = {
    scope: "If Beads is enabled, note the issue/spec this scoping work corresponds to; avoid noisy issues.",
    dev: "If Beads is enabled, update relevant issue state and use bd remember for durable decisions when useful.",
    redteam: "If Beads is enabled, record only durable blocker defects, not transient local failures.",
    review: "If Beads is enabled, verify meaningful blockers appear in Beads or the workflow result.",
    commit: "If Beads is enabled, mention remaining blockers after commit.",
  };
  return guidance[role] || "";
}'''
    else:
        beads_context_js = r'''function getActiveBeadsContext(runtime) {
  return runtime.BEADS_LEDGER_SNAPSHOT || "";
}

function beadsContext(runtime) {
  const snapshot = getActiveBeadsContext(runtime);
  return snapshot ? `Optional operator-supplied tracker context:\n${snapshot}` : "";
}'''
        beads_role_js = 'function beadsRoleGuidance(role) { return ""; }'

    template = r'''// Generated by aiwk. Edit workflow.yaml/spec files, then render again.
export const meta = __META__;

const STATIC_CONTEXT = __STATIC_CONTEXT__;
const DURABLE_CONTEXT = __DURABLE_CONTEXT__;
const BEADS_CONFIG = __BEADS_CONFIG__;
const ALL_STEPS = __STAGES__;
const MAX_DEV_RED_CYCLES = 2;
const MAX_REVIEW_ATTEMPTS = 2;

function normalizeWorkflowArgs(rawArgs) {
  if (rawArgs === undefined || rawArgs === null) return {};
  if (typeof rawArgs === "string") {
    const trimmed = rawArgs.trim();
    if (!trimmed) return {};
    let parsed;
    try { parsed = JSON.parse(trimmed); }
    catch (error) { throw new Error(`Unable to parse Workflow args JSON string: ${error.message}`); }
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error("Workflow args JSON must contain an object");
    }
    return parsed;
  }
  if (typeof rawArgs !== "object" || Array.isArray(rawArgs)) {
    throw new Error("Workflow args must be an object or JSON object string");
  }
  return rawArgs;
}

function agentOptions(options) {
  if (!options || !options.model) throw new Error("agentOptions requires a model");
  if (!options.effort) throw new Error("agentOptions requires effort");
  const opts = { label: options.label, model: options.model, effort: options.effort };
  if (options.schema !== undefined) opts.schema = options.schema;
  if (options.phase !== undefined) opts.phase = options.phase;
  if (options.isolation !== undefined) opts.isolation = options.isolation;
  if (options.agentType !== undefined) opts.agentType = options.agentType;
  return opts;
}

const SCOPE_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["status", "summary", "test_files_written", "scope_ok", "beads_notes", "handoff", "notes"],
  properties: {
    status: { type: "string", enum: ["done", "blocked", "needs_decision"] },
    summary: { type: "string" },
    test_files_written: { type: "array", items: { type: "string" } },
    scope_ok: { type: "boolean" },
    beads_notes: { type: "string" },
    handoff: { type: "string" },
    notes: { type: "string" },
  },
};

const IMPL_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["status", "summary", "files_changed", "tests_added", "scope_ok", "self_build_passed", "beads_issues_opened", "beads_issues_closed", "beads_memory_written", "handoff", "notes"],
  properties: {
    status: { type: "string", enum: ["done", "blocked", "scope_violation", "needs_decision", "invalid_test"] },
    summary: { type: "string" },
    files_changed: { type: "array", items: { type: "string" } },
    tests_added: { type: "array", items: { type: "string" } },
    scope_ok: { type: "boolean" },
    self_build_passed: { type: ["boolean", "null"] },
    beads_issues_opened: { type: "array", items: { type: "string" } },
    beads_issues_closed: { type: "array", items: { type: "string" } },
    beads_memory_written: { type: ["boolean", "null"] },
    handoff: { type: "string" },
    notes: { type: "string" },
  },
};

const RED_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["status", "summary", "adversarial_tests_written", "tests_passed", "failures_found", "beads_notes", "handoff", "notes"],
  properties: {
    status: { type: "string", enum: ["all_passed", "failures_found", "blocked", "needs_decision"] },
    summary: { type: "string" },
    adversarial_tests_written: { type: "array", items: { type: "string" } },
    tests_passed: { type: "boolean" },
    failures_found: { type: "array", items: { type: "object", additionalProperties: false, required: ["test_name", "detail"], properties: { test_name: { type: "string" }, detail: { type: "string" } } } },
    beads_notes: { type: "string" },
    handoff: { type: "string" },
    notes: { type: "string" },
  },
};

const REVIEW_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["accepted", "build_passed", "gtests_passed", "scope_clean", "findings", "beads_notes", "verdict_reason", "handoff"],
  properties: {
    accepted: { type: "boolean" },
    build_passed: { type: "boolean" },
    gtests_passed: { type: "boolean" },
    scope_clean: { type: "boolean" },
    findings: { type: "array", items: { type: "object", additionalProperties: false, required: ["severity", "detail"], properties: { severity: { type: "string", enum: ["blocker", "major", "minor"] }, detail: { type: "string" } } } },
    beads_notes: { type: "string" },
    verdict_reason: { type: "string" },
    handoff: { type: "string" },
  },
};

const GATE_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["status", "project", "repo", "gate", "step", "attempt", "setup_rc", "build_rc", "test_rc", "result_rc", "check_results", "gate_clean", "evidence_path", "log_path", "raw_tail", "integrity"],
  properties: {
    status: { type: "string" },
    project: { type: "string" },
    repo: { type: "string" },
    gate: { type: "string" },
    step: { type: "string" },
    attempt: { type: "integer" },
    setup_rc: { type: "integer" },
    build_rc: { type: "integer" },
    test_rc: { type: "integer" },
    result_rc: { type: "integer" },
    check_results: {
      type: "array",
      items: {
        type: "object", additionalProperties: false,
        required: ["name", "command", "rc", "count", "max_count", "timed_out", "timeout_seconds", "duration_seconds", "detail"],
        properties: {
          name: { type: "string" },
          command: { type: "string" },
          rc: { type: "integer" },
          count: { type: "integer" },
          max_count: { type: "integer" },
          timed_out: { type: "boolean" },
          timeout_seconds: { type: "number" },
          duration_seconds: { type: "number" },
          detail: { type: "string" },
        },
      },
    },
    gate_clean: { type: "boolean" },
    evidence_path: { type: "string" },
    log_path: { type: "string" },
    raw_tail: { type: "string" },
    sections: { type: "object" },
    integrity: {
      type: "object",
      properties: {
        evidence_sha256: { type: "string" },
        log_sha256: { type: "string" },
        repo_head_before: { type: ["string", "null"] },
        repo_head_after: { type: ["string", "null"] },
      },
    },
  },
};

const COMMIT_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["status", "summary", "commit_hash", "commit_rc", "status_before", "status_after", "clean_after", "notes"],
  properties: {
    status: { type: "string", enum: ["committed", "nothing_to_commit", "failed", "skipped"] },
    summary: { type: "string" },
    commit_hash: { type: ["string", "null"] },
    commit_rc: { type: "integer" },
    status_before: { type: "string" },
    status_after: { type: "string" },
    clean_after: { type: "boolean" },
    notes: { type: "string" },
  },
};

const CONTEXT = `Project: ${STATIC_CONTEXT.project}
Repository: ${STATIC_CONTEXT.repo}
AIWK project folder: ${STATIC_CONTEXT.projectFolder}
Project spec path: ${STATIC_CONTEXT.projectSpecPath}
Invariants path: ${STATIC_CONTEXT.invariantsPath}
Gates path: ${STATIC_CONTEXT.gatesPath}
State/handoff directory: ${STATIC_CONTEXT.statePath}

=== PROJECT SPEC (spec/project.spec.md) ===
${DURABLE_CONTEXT.projectSpec}

=== INVARIANTS (spec/invariants.yaml) ===
${DURABLE_CONTEXT.invariants}

=== GATES (spec/gates.yaml) ===
${DURABLE_CONTEXT.gates}`;

__BEADS_CONTEXT_JS__

__BEADS_ROLE_JS__

function withBeadsContext(prompt, runtime) {
  return `${CONTEXT}

Preflight summary supplied by operator:
${runtime.PREFLIGHT_SUMMARY}

Handoff path supplied by operator:
${runtime.HANDOFF_PATH || "(none)"}
If handoffPath is supplied, read it before editing. Treat it as durable operator-provided context.
If it conflicts with source/specs, source/specs win.
AIWK context-pack files are under ${STATIC_CONTEXT.statePath}.

${beadsContext(runtime)}

Read the durable spec, invariants, and gates before editing. Use repository files as source of truth.
Use the supplied preflight summary; do not rerun broad preflight unless stale or contradicted.
Use the handoff path when supplied. Keep scope tight to this step and role.

=== WORKFLOW TASK ===
${prompt}`;
}

function selectSteps(stage, fromStep, onlyStep) {
  const selectedStage = ALL_STEPS[stage];
  if (!selectedStage) throw new Error(`unknown_stage:${stage}`);
  if (onlyStep && fromStep) throw new Error("onlyStep_and_fromStep_are_mutually_exclusive");
  if (onlyStep) {
    const selected = selectedStage.steps.find((step) => step.id === onlyStep);
    if (!selected) throw new Error(`unknown_onlyStep:${onlyStep}`);
    return [selected];
  }
  if (fromStep) {
    const index = selectedStage.steps.findIndex((step) => step.id === fromStep);
    if (index < 0) throw new Error(`unknown_fromStep:${fromStep}`);
    return selectedStage.steps.slice(index);
  }
  return selectedStage.steps;
}

function reviewAccepted(review) {
  return Boolean(
    review &&
    review.accepted === true &&
    review.scope_clean === true &&
    review.build_passed === true &&
    review.gtests_passed === true
  );
}

function shellQuote(value) {
  return `'${String(value).replaceAll("'", `'"'"'`)}'`;
}

function buildGatePrompt(step, gateConfig, attempt) {
  const command = `${shellQuote(STATIC_CONTEXT.pythonPath)} -m aiwk gate-run` +
    ` --config ${shellQuote(STATIC_CONTEXT.aiwkConfigPath)}` +
    ` --workflow-spec ${shellQuote(STATIC_CONTEXT.workflowSpecPath)}` +
    ` --gate ${shellQuote(gateConfig.name)}` +
    ` --step ${shellQuote(step.id)}` +
    ` --attempt ${attempt}` +
    ` --repo ${shellQuote(STATIC_CONTEXT.repo)}`;
  return `=== OBJECTIVE BUILD GATE: ${step.id} — ${step.title} ===
You are the OBJECTIVE BUILD GATE.
You do not judge design, scope, or quality.
Do not edit files.
Run exactly this one AIWK command. Do not run the gate commands manually.
Return the JSON it prints without changing exit codes, counts, paths, or raw_tail.
Do not summarize instead of returning fields. If a command times out internally, return its timed_out and rc fields.
If the command fails, return its JSON/error exactly and include evidence/log paths if present.

\`\`\`sh
${command}
\`\`\`
`;
}

function formatGateResult(gate) {
  if (!gate) return "Objective Build Gate: skipped.";
  const checks = Array.isArray(gate.check_results) ? gate.check_results : [];
  const checkSummary = checks.map((check) =>
    `${check.name}: count=${check.count} max_count=${check.max_count} (${check.detail || "no detail"})`
  ).join("\n") || "(no named checks)";
  return `Objective Build Gate result:
setup_rc=${gate.setup_rc} build_rc=${gate.build_rc} test_rc=${gate.test_rc} result_rc=${gate.result_rc}
Checks:
${checkSummary}
Raw output tail:
${gate.raw_tail || "(none)"}`;
}

function computeGateClean(gate, gateConfig = null) {
  if (!gate || gate.status !== "ok" || !gate.evidence_path || !gate.log_path) return false;
  const checks = Array.isArray(gate.check_results) ? gate.check_results : [];
  const configuredChecks = Array.isArray(gateConfig?.checks) ? gateConfig.checks : [];
  const reportedChecksClean = checks.every((check) => !check.timed_out && Number(check.count) <= Number(check.max_count ?? 0));
  const configuredChecksClean = configuredChecks.every((expected) => {
    const reported = checks.find((check) => check.name === expected.name);
    return !!reported && Number(reported.count) <= Number(expected.max_count ?? 0);
  });
  return Number(gate.build_rc) === 0 &&
         Number(gate.test_rc) === 0 &&
         Number(gate.result_rc) === 0 &&
         reportedChecksClean &&
         configuredChecksClean;
}

function buildReviewerPrompt(step, gate, gateClean) {
  return `=== Code Reviewer: ${step.id} — ${step.title} ===
You are an adversarial Code Reviewer.
A separate Objective Build Gate runs deterministic build/test/check commands.
You do not need to rerun the gate commands unless the gate output is contradictory or obviously stale.
The workflow script enforces the objective gate. You cannot make a red build/test/check pass by returning accepted:true.
Your job is architecture correctness, scope discipline, stale assumptions, code quality, and interpreting gate failures into actionable fix guidance.
If the objective gate shows build_rc/test_rc/result_rc nonzero or check count above threshold, explain what is wrong and how to fix it.
Your acceptance is necessary but not sufficient.
Reject broad or fragile changes and stale assumptions.
${beadsRoleGuidance("review")}

Important review/commit ordering:
This review runs before the Commit phase. Expected in-scope changes may be modified or untracked at review time. Do not reject solely because expected in-scope files are modified or untracked. Reject unrelated dirty files, generated workflow artifacts, logs, build outputs, transcripts, or scope creep. The Commit phase is responsible for explicit-path staging and final clean status.
If commit mode is mechanical_all, the Commit phase will run git add -A, so reject unrelated dirty files before accepting.

Objective gate clean: ${gateClean}
${formatGateResult(gate)}

Review task from workflow.yaml:
${step.prompt.review}`;
}

function commitPolicyForStep(step) {
  return step.commitPolicy;
}

function renderCommitMessage(step, policy) {
  return policy.messageTemplate
    .replaceAll("{step_id}", step.id)
    .replaceAll("{step_title}", step.title)
    .replaceAll("{project}", STATIC_CONTEXT.project)
    .replaceAll("{stage}", step.stage);
}

function commitAgentPrompt(step, policy, changed) {
  const message = renderCommitMessage(step, policy);
  if (policy.mode === "mechanical_all") {
    return `You are the mechanical commit runner.

Run exactly:
cd ${STATIC_CONTEXT.repo}
status_before=$(git status --short)
git add -A
git commit -m ${shellQuote(message)}
commit_rc=$?
status_after=$(git status --short)
head_after=$(git rev-parse HEAD)
printf 'commit_rc=%s\\nstatus_before=%s\\nstatus_after=%s\\nhead_after=%s\\n' "$commit_rc" "$status_before" "$status_after" "$head_after"

Do not inspect architecture. Do not review code. Do not edit files. Do not choose paths.
If git commit says nothing to commit, report that exactly.
${beadsRoleGuidance("commit")}
Return the final status and commit hash if a commit was created.`;
  }
__MECHANICAL_PATHS_BRANCH__
  throw new Error(`unsupported_commit_mode:${policy.mode}`);
}

function formatRedFindings(red) {
  return (red?.failures_found || []).map((finding) => `[FAIL] ${finding.test_name}: ${finding.detail}`).join("\n") || red?.notes || "Red Team reported failures.";
}

function formatReviewFindings(review) {
  return (review?.findings || []).map((finding) => `[${finding.severity}] ${finding.detail}`).join("\n") || review?.verdict_reason || "Code Reviewer rejected the change.";
}

async function runWorkflow(rawArgs) {
  let WORKFLOW_ARGS;
  try { WORKFLOW_ARGS = normalizeWorkflowArgs(rawArgs); }
  catch (error) { return { halted_at: "args", reason: error.message, stage: null, results: [] }; }

  const STAGE = WORKFLOW_ARGS.stage || meta.defaultStage;
  const FROM_STEP = WORKFLOW_ARGS.fromStep || null;
  const ONLY_STEP = WORKFLOW_ARGS.onlyStep || null;
  const BEADS_LEDGER_SNAPSHOT = WORKFLOW_ARGS.beadsSnapshot || "(no beadsSnapshot supplied)";
  const PREFLIGHT_SUMMARY = WORKFLOW_ARGS.preflightSummary || "(no preflightSummary supplied)";
  const HANDOFF_PATH = WORKFLOW_ARGS.handoffPath || "";
  const runtime = { BEADS_LEDGER_SNAPSHOT, PREFLIGHT_SUMMARY, HANDOFF_PATH };
  const results = [];
  let steps;
  try { steps = selectSteps(STAGE, FROM_STEP, ONLY_STEP); }
  catch (error) { return { halted_at: "selection", reason: error.message, stage: STAGE, results }; }

  for (const step of steps) {
    const stepResult = { step: step.id, scope: null, dev_cycles: [], review_attempts: [], impl: null, gate: null, gate_clean: true, review: null, commit: null };
    results.push(stepResult);

    if (step.phases.includes("scope")) {
      const scope = await agent(
        withBeadsContext(`=== SCOPING TEST WRITER: ${step.id} — ${step.title} ===
Write BLACK BOX tests/spec artifacts ONLY. No implementation code.
Strictly follow the step scope.
${beadsRoleGuidance("scope")}
${step.prompt.scope}`, runtime),
        agentOptions({ label: `${step.id} scope`, phase: step.id, model: step.model, effort: step.effort, schema: SCOPE_SCHEMA })
      );
      stepResult.scope = scope;
      if (!scope || scope.status !== "done" || scope.scope_ok !== true) {
        return { halted_at: `${step.id}:scope`, reason: scope?.status || "scope_rejected", stage: STAGE, results };
      }
    }

    let lastImpl = null;
    let redPassed = !(step.phases.includes("dev") || step.phases.includes("redteam"));
    let redFindings = "";
    const redTestFiles = [];
    const devCycles = step.phases.includes("dev") ? MAX_DEV_RED_CYCLES : 1;
    for (let cycle = 1; cycle <= devCycles && !redPassed; cycle++) {
      if (step.phases.includes("dev")) {
        const impl = await agent(
          withBeadsContext(`=== DEVELOPER: ${step.id} — ${step.title} (cycle ${cycle}) ===
Implement only this sub-step. Pass the Scoping Tests.
Respect invariants and out-of-scope boundaries.
If Red Team or Reviewer findings are supplied, address exactly those findings.
${beadsRoleGuidance("dev")}
${step.prompt.dev}${redFindings ? `\n\nThe Red Team found these failures:\n${redFindings}` : ""}`, runtime),
          agentOptions({ label: `${step.id} dev ${cycle}`, phase: step.id, model: step.model, effort: step.effort, schema: IMPL_SCHEMA })
        );
        lastImpl = impl;
        stepResult.impl = impl;
        if (!impl || impl.status !== "done" || impl.scope_ok !== true) {
          stepResult.dev_cycles.push({ cycle, impl });
          return { halted_at: `${step.id}:dev`, reason: impl?.status || "implementer_escalation", stage: STAGE, results };
        }
      }

      if (step.phases.includes("redteam")) {
        const red = await agent(
          withBeadsContext(`=== ADVERSARIAL RED TEAM: ${step.id} — ${step.title} (cycle ${cycle}) ===
You are the Red Team. Read the Developer implementation.
Write adversarial WHITE BOX tests/spec checks designed to break it.
Run relevant deterministic tests. Do not silently patch implementation.
Report failures in structured form.
${beadsRoleGuidance("redteam")}
${step.prompt.redteam}`, runtime),
          agentOptions({ label: `${step.id} red team ${cycle}`, phase: step.id, model: step.model, effort: "high", schema: RED_SCHEMA })
        );
        stepResult.dev_cycles.push({ cycle, impl: lastImpl, red });
        redTestFiles.push(...(red?.adversarial_tests_written || []));
        if (!red || red.status === "blocked" || red.status === "needs_decision") {
          return { halted_at: `${step.id}:redteam`, reason: red?.status || "red_team_escalation", stage: STAGE, results };
        }
        redPassed = red.status === "all_passed" && red.tests_passed === true;
        if (!redPassed) redFindings = formatRedFindings(red);
      } else {
        redPassed = true;
      }
    }
    if (!redPassed) {
      return { halted_at: `${step.id}:redteam`, reason: "red_team_failed_after_retries", stage: STAGE, results };
    }

    const gateEnabled = !!(step.objectiveGate && step.objectiveGate.enabled !== false);
    let accepted = !(step.phases.includes("review") || gateEnabled);
    let priorReviewFindings = "";
    let lastReview = null;
    let lastGate = null;
    let lastGateClean = !gateEnabled;
    const reviewAttempts = step.phases.includes("review") ? MAX_REVIEW_ATTEMPTS : 1;
    for (let attempt = 1; attempt <= reviewAttempts && !accepted; attempt++) {
      if (attempt > 1) {
        const fixImpl = await agent(
          withBeadsContext(`=== DEVELOPER FIX PASS: ${step.id} — ${step.title} (review attempt ${attempt}) ===
Implement only this sub-step and respect all invariants and boundaries.
Address exactly these Code Reviewer findings:
The findings block may also contain Objective Build Gate failures. Address both sources exactly.
${priorReviewFindings}

${step.prompt.dev}`, runtime),
          agentOptions({ label: `${step.id} dev fix ${attempt}`, phase: step.id, model: step.model, effort: step.effort, schema: IMPL_SCHEMA })
        );
        lastImpl = fixImpl;
        stepResult.impl = fixImpl;
        if (!fixImpl || fixImpl.status !== "done" || fixImpl.scope_ok !== true) {
          stepResult.review_attempts.push({ attempt, fix: fixImpl });
          return { halted_at: `${step.id}:review_fix`, reason: fixImpl?.status || "implementer_escalation", stage: STAGE, results };
        }
      }
      const gate = gateEnabled ? await agent(
        buildGatePrompt(step, step.objectiveGate, attempt),
        agentOptions({ label: `${step.id} objective gate ${attempt}`, phase: step.id, model: step.model, effort: "medium", schema: GATE_SCHEMA })
      ) : null;
      const gateClean = gateEnabled ? computeGateClean(gate, step.objectiveGate) : true;
      lastGate = gate;
      lastGateClean = gateClean;

      let review = null;
      if (step.phases.includes("review")) {
        review = await agent(
          withBeadsContext(buildReviewerPrompt(step, gate, gateClean), runtime),
          agentOptions({ label: `${step.id} review ${attempt}`, phase: step.id, model: step.model, effort: "high", schema: REVIEW_SCHEMA })
        );
        accepted = gateClean && reviewAccepted(review);
      } else {
        accepted = gateClean;
      }
      lastReview = review;
      stepResult.gate = gate;
      stepResult.gate_clean = gateClean;
      stepResult.review = review;
      stepResult.review_attempts.push({ attempt, gate, gateClean, review });
      if (!accepted) {
        const findings = [];
        if (!gateClean) findings.push(formatGateResult(gate));
        if (review && !review.accepted) findings.push(formatReviewFindings(review));
        priorReviewFindings = findings.join("\n\n") || "Objective gate or reviewer rejected the step.";
      }
    }
    if (!accepted) {
      const reason = !lastGateClean ? "objective_gate_failed_after_retries" : "review_rejected_after_retries";
      return { halted_at: `${step.id}:review`, reason, stage: STAGE, results };
    }

    if (step.phases.includes("commit")) {
      const commitPolicy = commitPolicyForStep(step);
      const changed = Array.from(new Set([
        ...(lastImpl?.files_changed || []),
        ...(stepResult.scope?.test_files_written || []),
        ...redTestFiles,
      ])).filter(Boolean);
      if (commitPolicy.mode === "none") {
        stepResult.commit = { status: "skipped", summary: "commit_mode none", commit_hash: null, commit_rc: 0, status_before: "", status_after: "", clean_after: true, notes: "" };
      } else {
        const commitResult = await agent(
          withBeadsContext(commitAgentPrompt(step, commitPolicy, changed), runtime),
          agentOptions({ label: `${step.id} commit`, phase: step.id, model: commitPolicy.model, effort: commitPolicy.effort, schema: COMMIT_SCHEMA })
        );
        stepResult.commit = commitResult;
        if (!commitResult || commitResult.status === "failed") {
          return { halted_at: `${step.id}:commit`, reason: "commit_failed", stage: STAGE, results };
        }
        const commitClean = ["committed", "nothing_to_commit", "skipped"].includes(commitResult.status) &&
          commitResult.clean_after !== false && !String(commitResult.status_after || "").trim();
        if (!commitClean) {
          return { halted_at: `${step.id}:commit`, reason: "commit_left_dirty_tree", stage: STAGE, results };
        }
      }
    }
    stepResult.accepted = accepted;
    stepResult.impl = lastImpl;
    stepResult.gate = lastGate;
    stepResult.gate_clean = lastGateClean;
    stepResult.review = lastReview;
    stepResult.final_review = lastReview;
  }
  return { halted_at: null, reason: "all_steps_accepted", stage: STAGE, results };
}

const result = await runWorkflow(typeof args === "undefined" ? undefined : args);
return result;
'''
    replacements = {
        "__META__": _json({
            "name": spec.project,
            "project": spec.project,
            "description": spec.description,
            "defaultStage": spec.default_stage,
        }),
        "__STATIC_CONTEXT__": _json(static_context),
        "__DURABLE_CONTEXT__": _json(durable_context),
        "__BEADS_CONFIG__": _json(beads_config),
        "__BEADS_CONTEXT_JS__": beads_context_js,
        "__BEADS_ROLE_JS__": beads_role_js,
        "__STAGES__": _json(stages),
        "__MECHANICAL_PATHS_BRANCH__": '''  if (policy.mode === "mechanical_paths") {
    return `=== SAFE COMMIT AGENT: ${step.id} — ${step.title} ===
Commit only after accepted review. Run git status --short before and after staging.
NEVER use git add -A. NEVER use git add . NEVER use git commit -a.
Stage these explicit paths only:
${changed.length ? changed.map((path) => `  - ${path}`).join("\\n") : "  (none reported; do not create an empty commit)"}
${beadsRoleGuidance("commit")}
Commit with: git commit -m ${shellQuote(message)}
Return COMMIT_SCHEMA fields including commit_rc, status_after, and clean_after.`;
  }''' if uses_mechanical_paths else "",
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template
