"""Render a durable AIWK workflow as mature Claude Workflow JavaScript."""

from __future__ import annotations

import json
import hashlib
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


def _context_file(path: Path) -> str:
    """Embed a durable-context file in full.

    Durable spec/invariants/gates are the authoritative in-prompt context, so
    they are embedded whole (no length bound); the sha256 is provenance only.
    """
    text = _beads_blind_text(_read_context_file(path))
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return (
        f"Path: {path}\n"
        f"sha256: {digest}\n\n"
        f"{text}"
    )


def _beads_blind_text(text: str) -> str:
    """Suppress legacy live Beads command guidance in generated prompts."""
    replacements = {
        "LIVE BEADS DISCIPLINE": "EXTERNAL MEMORY DISCIPLINE SUPPRESSED",
        "ACTIVE BEADS PROJECT LEDGER SNAPSHOT": "OPTIONAL EXTERNAL MEMORY SNAPSHOT",
        "bd prime": "[external-memory command suppressed]",
        "bd list": "[external-memory command suppressed]",
        "bd create": "[external-memory command suppressed]",
        "bd update": "[external-memory command suppressed]",
        "bd remember": "[external-memory command suppressed]",
        "Use bd remember": "Use durable AIWK handoffs",
        "create one only if": "record only if",
        "Beads issue": "external-memory item",
    }
    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)
    return result


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
        "handoffsPath": project_root / "state" / "handoffs",
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
        "projectSpec": _context_file(context_paths["projectSpecPath"]),
        "invariants": _context_file(context_paths["invariantsPath"]),
        "gates": _context_file(context_paths["gatesPath"]),
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

    def rendered_discovery(step) -> dict[str, object]:
        return {
            "enabled": step.discovery.enabled,
            "model": step.discovery.model,
            "effort": step.discovery.effort,
        }

    def rendered_code_review(step) -> dict[str, object]:
        cr = step.code_review
        return {
            "enabled": cr.enabled,
            "placement": cr.placement,
            "effort": cr.effort,
            "applyFixes": cr.apply_fixes,
            "scope": cr.scope,
        }

    def rendered_redteam_fan(step) -> dict[str, object]:
        fan = step.redteam_fan
        return {
            "enabled": fan.enabled,
            "verify": fan.verify,
            "verifyVotes": fan.verify_votes,
            "model": fan.model,
            "effort": fan.effort,
            "completenessCritic": fan.completeness_critic,
            "lenses": [{"key": lens.key, "prompt": lens.prompt} for lens in fan.lenses],
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
                    "prompt": {key: _beads_blind_text(value) for key, value in step.prompt.items()},
                    "objectiveGate": rendered_gate(step.objective_gate),
                    "commitPolicy": rendered_commit(step),
                    "discovery": rendered_discovery(step),
                    "codeReview": rendered_code_review(step),
                    "redteamFan": rendered_redteam_fan(step),
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
    external_memory_config = asdict(spec.external_memory)
    if spec.external_memory.mode == "snapshot" and spec.external_memory.include_in_agent_prompts:
        external_memory_context_js = r'''function getExternalMemorySnapshot(runtime) {
  return runtime.BACKCOMPAT_BEADS_SNAPSHOT || "";
}

function externalMemoryContext(runtime) {
  const snapshot = getExternalMemorySnapshot(runtime);
  if (!snapshot) return "";
  return `=== OPTIONAL EXTERNAL MEMORY SNAPSHOT ===
This is advisory operator-supplied long-term memory.
It may be stale or incomplete.
Current source, specs, gate evidence, and git state override this snapshot.
Do not mutate the external memory system.
Do not run bd commands.
Label: ${EXTERNAL_MEMORY_CONFIG.label}

${snapshot}`;
}'''
    else:
        external_memory_context_js = r'''function externalMemoryContext(runtime) {
  return "";
}'''
    external_memory_role_js = 'function externalMemoryRoleGuidance(role) { return ""; }'

    template = r'''// Generated by aiwk. Edit workflow.yaml/spec files, then render again.
export const meta = __META__;

const STATIC_CONTEXT = __STATIC_CONTEXT__;
const DURABLE_CONTEXT = __DURABLE_CONTEXT__;
const EXTERNAL_MEMORY_CONFIG = __EXTERNAL_MEMORY_CONFIG__;
const CONTEXT_ECONOMY = __CONTEXT_ECONOMY__;
const ALL_STEPS = __STAGES__;
const MAX_DEV_RED_CYCLES = 2;
const MAX_REVIEW_ATTEMPTS = 2;
const MAX_CHECKPOINT_CONTINUATIONS = Number(CONTEXT_ECONOMY.max_checkpoint_continuations ?? 1);

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

const HANDOFF_REQUIRED = [
  "handoff_path", "files_changed", "files_inspected", "tests_run",
  "gate_evidence_paths", "known_dirty_paths", "next_agent_should_read",
];

const HANDOFF_PROPERTIES = {
  handoff_path: { type: "string" },
  files_changed: { type: "array", items: { type: "string" } },
  files_inspected: { type: "array", items: { type: "string" } },
  tests_run: {
    type: "array",
    items: {
      type: "object", additionalProperties: false,
      required: ["command", "rc", "result", "evidence_path"],
      properties: {
        command: { type: "string" },
        rc: { type: ["integer", "null"] },
        result: { type: "string" },
        evidence_path: { type: "string" },
      },
    },
  },
  gate_evidence_paths: { type: "array", items: { type: "string" } },
  known_dirty_paths: { type: "array", items: { type: "string" } },
  next_agent_should_read: { type: "array", items: { type: "string" } },
};

const DISCOVERY_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["status", "summary", "repo_map", "likely_files", "likely_tests", "do_not_rediscover", "handoff", "notes", ...HANDOFF_REQUIRED],
  properties: {
    status: { type: "string", enum: ["done", "blocked", "needs_decision", "checkpoint"] },
    summary: { type: "string" },
    repo_map: { type: "string" },
    likely_files: { type: "array", items: { type: "string" } },
    likely_tests: { type: "array", items: { type: "string" } },
    do_not_rediscover: { type: "array", items: { type: "string" } },
    handoff: { type: "string" },
    notes: { type: "string" },
    reason: { type: "string" },
    remaining_work: { type: "array", items: { type: "string" } },
    continue_role: { type: "string" },
    continue_step: { type: "string" },
    ...HANDOFF_PROPERTIES,
  },
};

const SCOPE_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["status", "summary", "test_files_written", "scope_ok", "external_memory_notes", "handoff", "notes", ...HANDOFF_REQUIRED],
  properties: {
    status: { type: "string", enum: ["done", "blocked", "needs_decision", "checkpoint"] },
    summary: { type: "string" },
    test_files_written: { type: "array", items: { type: "string" } },
    scope_ok: { type: "boolean" },
    external_memory_notes: { type: "string" },
    handoff: { type: "string" },
    notes: { type: "string" },
    reason: { type: "string" },
    remaining_work: { type: "array", items: { type: "string" } },
    continue_role: { type: "string" },
    continue_step: { type: "string" },
    ...HANDOFF_PROPERTIES,
  },
};

const IMPL_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["status", "summary", "tests_added", "scope_ok", "self_build_passed", "external_memory_items_opened", "external_memory_items_closed", "external_memory_written", "handoff", "notes", ...HANDOFF_REQUIRED],
  properties: {
    status: { type: "string", enum: ["done", "blocked", "scope_violation", "needs_decision", "invalid_test", "checkpoint"] },
    summary: { type: "string" },
    tests_added: { type: "array", items: { type: "string" } },
    scope_ok: { type: "boolean" },
    self_build_passed: { type: ["boolean", "null"] },
    external_memory_items_opened: { type: "array", items: { type: "string" } },
    external_memory_items_closed: { type: "array", items: { type: "string" } },
    external_memory_written: { type: ["boolean", "null"] },
    handoff: { type: "string" },
    notes: { type: "string" },
    reason: { type: "string" },
    remaining_work: { type: "array", items: { type: "string" } },
    continue_role: { type: "string" },
    continue_step: { type: "string" },
    ...HANDOFF_PROPERTIES,
  },
};

const RED_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["status", "summary", "adversarial_tests_written", "tests_passed", "failures_found", "external_memory_notes", "handoff", "notes", ...HANDOFF_REQUIRED],
  properties: {
    status: { type: "string", enum: ["all_passed", "failures_found", "blocked", "needs_decision", "checkpoint"] },
    summary: { type: "string" },
    adversarial_tests_written: { type: "array", items: { type: "string" } },
    tests_passed: { type: "boolean" },
    failures_found: { type: "array", items: { type: "object", additionalProperties: false, required: ["test_name", "detail"], properties: { test_name: { type: "string" }, detail: { type: "string" } } } },
    external_memory_notes: { type: "string" },
    handoff: { type: "string" },
    notes: { type: "string" },
    reason: { type: "string" },
    remaining_work: { type: "array", items: { type: "string" } },
    continue_role: { type: "string" },
    continue_step: { type: "string" },
    ...HANDOFF_PROPERTIES,
  },
};

const REVIEW_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["accepted", "build_passed", "gtests_passed", "scope_clean", "findings", "external_memory_notes", "verdict_reason", "handoff", ...HANDOFF_REQUIRED],
  properties: {
    status: { type: "string", enum: ["done", "blocked", "needs_decision", "checkpoint"] },
    accepted: { type: "boolean" },
    build_passed: { type: "boolean" },
    gtests_passed: { type: "boolean" },
    scope_clean: { type: "boolean" },
    findings: { type: "array", items: { type: "object", additionalProperties: false, required: ["severity", "detail"], properties: { severity: { type: "string", enum: ["blocker", "major", "minor"] }, detail: { type: "string" } } } },
    external_memory_notes: { type: "string" },
    verdict_reason: { type: "string" },
    handoff: { type: "string" },
    reason: { type: "string" },
    remaining_work: { type: "array", items: { type: "string" } },
    continue_role: { type: "string" },
    continue_step: { type: "string" },
    ...HANDOFF_PROPERTIES,
  },
};

// Per-finding verdict returned by an adversarial refuter in the fanned red-team
// verify stage. `real` false means the refuter believes the finding is not a
// genuine defect. Refuters are prompted to default to refuted when uncertain.
const FAN_VERDICT_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["real", "reason"],
  properties: {
    real: { type: "boolean" },
    reason: { type: "string" },
  },
};

// Optional completeness critic: names attack surfaces no lens covered. Advisory
// only -- the workflow never auto-adds lenses; it surfaces the gap for the author.
const FAN_CRITIC_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["uncovered_surfaces", "suggested_lenses", "notes"],
  properties: {
    uncovered_surfaces: { type: "array", items: { type: "string" } },
    suggested_lenses: {
      type: "array",
      items: {
        type: "object", additionalProperties: false,
        required: ["key", "rationale"],
        properties: { key: { type: "string" }, rationale: { type: "string" } },
      },
    },
    notes: { type: "string" },
  },
};

// Cheap /code-review filter report. Distinct from REVIEW_SCHEMA (the holistic
// reviewer): this is the machine-readable result of the /code-review skill run
// on the diff, so the workflow can route a blocking finding back to dev/fix.
const CODE_REVIEW_SCHEMA = {
  type: "object", additionalProperties: false,
  required: ["status", "placement", "clean", "findings", "fixes_applied", "summary", "handoff", ...HANDOFF_REQUIRED],
  properties: {
    status: { type: "string", enum: ["done", "blocked", "needs_decision", "checkpoint"] },
    placement: { type: "string", enum: ["post_dev", "pre_redteam", "final"] },
    clean: { type: "boolean" },
    findings: { type: "array", items: { type: "object", additionalProperties: false, required: ["severity", "detail"], properties: { severity: { type: "string", enum: ["blocker", "major", "minor"] }, file: { type: "string" }, detail: { type: "string" } } } },
    fixes_applied: { type: "boolean" },
    summary: { type: "string" },
    handoff: { type: "string" },
    notes: { type: "string" },
    reason: { type: "string" },
    remaining_work: { type: "array", items: { type: "string" } },
    continue_role: { type: "string" },
    continue_step: { type: "string" },
    ...HANDOFF_PROPERTIES,
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
Durable per-agent handoffs directory: ${STATIC_CONTEXT.handoffsPath}

=== PROJECT SPEC (spec/project.spec.md) ===
${DURABLE_CONTEXT.projectSpec}

=== INVARIANTS (spec/invariants.yaml) ===
${DURABLE_CONTEXT.invariants}

=== GATES (spec/gates.yaml) ===
${DURABLE_CONTEXT.gates}`;

__EXTERNAL_MEMORY_CONTEXT_JS__

__EXTERNAL_MEMORY_ROLE_JS__

function uniqueNonEmpty(values) {
  const result = [];
  const seen = new Set();
  for (const value of values || []) {
    const text = String(value || "").trim();
    if (!text || seen.has(text)) continue;
    seen.add(text);
    result.push(text);
  }
  return result;
}

function sanitizePathComponent(value) {
  const safe = String(value || "unknown").replace(/[^A-Za-z0-9_.-]+/g, "_").replace(/^_+|_+$/g, "");
  return safe || "unknown";
}

function handoffPathFor(step, role, cycle, attempt, continuation, agentId) {
  const filename = `${sanitizePathComponent(step.id)}_${sanitizePathComponent(role).toUpperCase()}_C${Number(cycle || 0)}_A${Number(attempt || 0)}_K${Number(continuation || 0)}_${sanitizePathComponent(agentId)}.md`;
  return `${STATIC_CONTEXT.handoffsPath}/${filename}`;
}

function handoffTemplateText(step, role, cycle, attempt, continuation) {
  return `# Handoff: ${step.id} ${role} cycle ${cycle} attempt ${attempt} continuation ${continuation}

## Summary
- status:
- short verdict:

## Role and step
- role:
- step:
- cycle:
- attempt:
- continuation:

## Scope
- allowed scope executed:
- explicitly avoided non-goals:

## Files inspected
- <path>:<line-range or symbol> — <why>

## Files changed
- <path> — <why>

## Important symbols or line ranges
- <path>:<line-range> <symbol> — <finding/decision>

## Commands and tests run
- command:
- rc:
- result:
- evidence path:

## Gate evidence consulted
- <path> — <what it showed>

## Findings closed
- <finding id/name> — <resolution>

## Known limitations
- <limitation/risk> — <impact>

## Remaining work
- <severity> <description> <recommended next action>

## Recommended next reads
- <handoff/log/source path>

## Paths accepted or intentionally untouched
- accepted changed paths:
- intentionally untouched paths:
- known dirty paths:

## Next agent instructions
- read this first;
- do not rediscover:
- focus on:
- rerun only if:`;
}

function contextEconomyPolicy(role) {
  return `Context economy rule:
- Read supplied handoff(s) first.
- Do not redo broad repository discovery already summarized there.
- Use targeted reads of named files/symbols for grounding before edits/review.
- Broad grep/find/read sweeps are allowed only if the handoff is missing, stale, contradicted, or insufficient; state the reason.
- Batch shell discovery when possible.
- Redirect long test/build output to logs and print summaries/tails.
- For long commands use this pattern:
  <long command> > /tmp/${STATIC_CONTEXT.project}_${role}.log 2>&1
  rc=$?
  echo "rc=$rc"
  tail -80 /tmp/${STATIC_CONTEXT.project}_${role}.log
- Continue within the same agent when useful. Do not checkpoint or exit merely because the transcript or tool-call count is growing.
- If you genuinely cannot continue safely because of an external blocker, write the durable handoff and return blocked/needs_decision with concrete remaining work.`;
}

function testSummaryLines(testsRun) {
  const tests = Array.isArray(testsRun) ? testsRun : [];
  return tests.length ? tests.slice(-8).map((test) =>
    `- ${test.command || "(unknown command)"} rc=${test.rc ?? "?"} result=${test.result || ""} evidence=${test.evidence_path || ""}`
  ).join("\n") : "- (none reported yet)";
}

function priorContextBlock(state, findings = "") {
  const handoffs = uniqueNonEmpty(state?.priorHandoffPaths || []);
  const gates = uniqueNonEmpty(state?.gateEvidencePaths || []);
  const changed = uniqueNonEmpty(state?.changedPaths || []);
  const inspected = uniqueNonEmpty(state?.inspectedPaths || []);
  const dirty = uniqueNonEmpty(state?.knownDirtyPaths || []);
  const handoffLines = handoffs.length ? handoffs.map((path) => `- ${path}`).join("\n") : "- (none yet)";
  const gateLines = gates.length ? gates.map((path) => `- ${path}`).join("\n") : "- (none yet)";
  const changedLines = changed.length ? changed.map((path) => `- ${path}`).join("\n") : "- (none reported yet)";
  const inspectedLines = inspected.length ? inspected.slice(-20).map((path) => `- ${path}`).join("\n") : "- (none reported yet)";
  const dirtyLines = dirty.length ? dirty.map((path) => `- ${path}`).join("\n") : "- (none reported yet)";
  return `Prior handoff paths:
${handoffLines}

Current changed paths reported by prior agents:
${changedLines}

Recently inspected paths reported by prior agents:
${inspectedLines}

Latest gate evidence/log paths:
${gateLines}

Compact test summary from prior agents:
${testSummaryLines(state?.testsRun)}

Known dirty paths reported by prior agents:
${dirtyLines}

Allowed edit paths:
- Prefer paths named in the current step prompt, prior handoffs, changed-path lists, and relevant spec/gate sections.
- Broaden only when those paths are missing, stale, contradicted, or insufficient; state why.

Forbidden scope:
- Do not modify files outside this step's durable scope, unrelated generated artifacts, logs, transcripts, or build outputs.
- Do not add generic whole-repository untracked-file policing.

Specific findings being addressed:
${findings || "- (none supplied)"}

Read these first. Do not repeat broad repository discovery already summarized there unless the handoff is missing, stale, contradicted by source, or insufficient for the local task.
If a handoff is contradicted by source, objective gate evidence, or committed specs, source/gates/specs win and you must explain the contradiction.`;
}

function handoffInstructions(step, role, cycle, attempt, continuation, agentId) {
  const path = handoffPathFor(step, role, cycle, attempt, continuation, agentId);
  return `Durable handoff requirement:
- Before returning, create the directory ${STATIC_CONTEXT.handoffsPath}.
- Write this exact handoff markdown file: ${path}
- Use this template and fill it concretely:

${handoffTemplateText(step, role, cycle, attempt, continuation)}

- Return handoff_path exactly as: ${path}
- Also return files_changed, files_inspected, tests_run, gate_evidence_paths, known_dirty_paths, and next_agent_should_read.
- If you cannot write the handoff file, return a blocked/incomplete status and explain why.`;
}

function collectHandoffPaths(output) {
  if (!output) return [];
  return uniqueNonEmpty([
    output.handoff_path,
    ...(Array.isArray(output.next_agent_should_read) ? output.next_agent_should_read : []),
  ]);
}

function collectGatePaths(gate) {
  if (!gate) return [];
  return uniqueNonEmpty([gate.evidence_path, gate.log_path]);
}

function rememberHandoff(state, output) {
  state.priorHandoffPaths = uniqueNonEmpty([
    ...(state.priorHandoffPaths || []),
    ...collectHandoffPaths(output),
  ]);
  state.changedPaths = uniqueNonEmpty([
    ...(state.changedPaths || []),
    ...(Array.isArray(output?.files_changed) ? output.files_changed : []),
  ]);
  state.inspectedPaths = uniqueNonEmpty([
    ...(state.inspectedPaths || []),
    ...(Array.isArray(output?.files_inspected) ? output.files_inspected : []),
  ]);
  state.knownDirtyPaths = uniqueNonEmpty([
    ...(state.knownDirtyPaths || []),
    ...(Array.isArray(output?.known_dirty_paths) ? output.known_dirty_paths : []),
  ]);
  state.testsRun = [
    ...(Array.isArray(state.testsRun) ? state.testsRun : []),
    ...(Array.isArray(output?.tests_run) ? output.tests_run : []),
  ];
}

function rememberGateEvidence(state, gate) {
  state.gateEvidencePaths = uniqueNonEmpty([
    ...(state.gateEvidencePaths || []),
    ...collectGatePaths(gate),
  ]);
}

function isCheckpoint(output) {
  return output && output.status === "checkpoint";
}

function validHandoffFor(output, expectedPath) {
  if (!output || typeof output.handoff_path !== "string" || !output.handoff_path.trim()) return false;
  return !expectedPath || output.handoff_path === expectedPath;
}

function checkpointReturn(step, role, output, stage, results, reason = "checkpoint_requested") {
  return {
    halted_at: `${step.id}:${role}_checkpoint`,
    reason,
    checkpoint: {
      status: "checkpoint",
      handoff_path: output?.handoff_path || "",
      reason: output?.reason || "unspecified",
      remaining_work: output?.remaining_work || [],
      continue_role: output?.continue_role || role,
      continue_step: output?.continue_step || step.id,
    },
    stage,
    results,
  };
}

function missingHandoffReturn(step, role, stage, results) {
  return { halted_at: `${step.id}:${role}`, reason: "missing_handoff_path", stage, results };
}

function invalidHandoffReturn(step, role, expectedPath, actualPath, stage, results) {
  return {
    halted_at: `${step.id}:${role}`,
    reason: "invalid_handoff_path",
    expected_handoff_path: expectedPath,
    actual_handoff_path: actualPath || "",
    stage,
    results,
  };
}

function checkpointContinuationBlock(role, checkpointHandoffPath, remainingWork, continuation) {
  if (!checkpointHandoffPath) return "";
  const remaining = Array.isArray(remainingWork) ? remainingWork.join("\n- ") : String(remainingWork || "");
  return `=== CHECKPOINT CONTINUATION ${continuation}: ${role} ===
This is the same logical role and same step continuing after a checkpoint.
Read this checkpoint handoff first: ${checkpointHandoffPath}
Continue the remaining work before advancing workflow state:
- ${remaining || "(remaining_work was empty; inspect the checkpoint handoff and finish the role)"}
Do not consume a new Red-Team cycle or reset reviewer-attempt state because of this continuation.
Write a new unique continuation handoff path for this invocation.`;
}

async function invokeSubstantiveRoleWithContinuations({
  step, role, cycle = 0, attempt = 0, agentId, state, runtime, stage, results,
  label, model, effort, schema, promptFor,
}) {
  let continuation = 0;
  let checkpointHandoffPath = "";
  let remainingWork = [];
  while (continuation <= MAX_CHECKPOINT_CONTINUATIONS) {
    const invocationId = `${agentId}_k${continuation}`;
    const expectedHandoffPath = handoffPathFor(step, role, cycle, attempt, continuation, invocationId);
    const prompt = promptFor({
      continuation,
      expectedHandoffPath,
      checkpointHandoffPath,
      remainingWork,
      continuationBlock: checkpointContinuationBlock(role, checkpointHandoffPath, remainingWork, continuation),
    });
    const output = await agent(
      withRuntimeContext(prompt, runtime),
      agentOptions({ label: `${label} k${continuation}`, phase: step.id, model, effort, schema })
    );
    if (!output?.handoff_path) return { halt: missingHandoffReturn(step, role, stage, results) };
    if (!validHandoffFor(output, expectedHandoffPath)) {
      return { halt: invalidHandoffReturn(step, role, expectedHandoffPath, output?.handoff_path, stage, results) };
    }
    rememberHandoff(state, output);
    if (isCheckpoint(output)) {
      if (continuation >= MAX_CHECKPOINT_CONTINUATIONS) {
        return { halt: checkpointReturn(step, role, output, stage, results, "checkpoint_continuation_limit_exceeded") };
      }
      state.checkpoints = [
        ...(Array.isArray(state.checkpoints) ? state.checkpoints : []),
        {
          role,
          step: step.id,
          cycle,
          attempt,
          continuation,
          handoff_path: output.handoff_path,
          remaining_work: output.remaining_work || [],
        },
      ];
      checkpointHandoffPath = output.handoff_path;
      remainingWork = output.remaining_work || [];
      continuation += 1;
      continue;
    }
    return { output };
  }
  return { halt: { halted_at: `${step.id}:${role}_checkpoint`, reason: "checkpoint_continuation_limit_exceeded", stage, results } };
}

function withRuntimeContext(prompt, runtime) {
  return `${CONTEXT}

Preflight summary supplied by operator:
${runtime.PREFLIGHT_SUMMARY}

Handoff path supplied by operator:
${runtime.HANDOFF_PATH || "(none)"}
If handoffPath is supplied, read it before editing. Treat it as durable operator-provided context.
If it conflicts with source/specs, source/specs win.
AIWK context-pack files are under ${STATIC_CONTEXT.statePath}.

${externalMemoryContext(runtime)}

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

const START_AT_ROLE_ORDER = {
  scope: 10,
  discovery: 20,
  dev: 30,
  redteam: 40,
  gate: 50,
  review: 60,
  dev_fix: 70,
  commit: 80,
};

function normalizeStartAtRole(value) {
  if (value === undefined || value === null || value === "") return null;
  const text = String(value).trim().toLowerCase().replaceAll("-", "_");
  const aliases = {
    developer: "dev",
    red_team: "redteam",
    objective_gate: "gate",
    reviewer: "review",
    devfix: "dev_fix",
    developer_fix: "dev_fix",
  };
  const role = aliases[text] || text;
  if (!Object.prototype.hasOwnProperty.call(START_AT_ROLE_ORDER, role)) {
    throw new Error(`unknown_startAtRole:${value}`);
  }
  return role;
}

function intArg(value, fallback, name) {
  if (value === undefined || value === null || value === "") return fallback;
  const number = Number(value);
  if (!Number.isInteger(number) || number <= 0) throw new Error(`${name}_must_be_positive_integer`);
  return number;
}

function roleRank(role) {
  if (!role) return 0;
  return START_AT_ROLE_ORDER[role] || 0;
}

function roleIsAtOrAfter(startAtRole, role) {
  return !startAtRole || roleRank(role) >= roleRank(startAtRole);
}

function validateStartAtRoleArgs(startAtRole, onlyStep, handoffPath, gateEvidencePaths) {
  if (!startAtRole) return null;
  if (!onlyStep) return "startAtRole_requires_onlyStep";
  if (startAtRole !== "scope" && !handoffPath && uniqueNonEmpty(gateEvidencePaths).length === 0) {
    return "startAtRole_requires_handoffPath_or_gateEvidencePath";
  }
  return null;
}

function stepSupportsStartAtRole(step, role) {
  if (!role) return true;
  if (role === "discovery") return !!(step.discovery && step.discovery.enabled) || step.phases.includes("discovery");
  if (role === "gate") return !!(step.objectiveGate && step.objectiveGate.enabled !== false);
  if (role === "dev_fix") return step.phases.includes("review");
  return step.phases.includes(role);
}

function validateStartAtRoleForStep(step, role) {
  if (!role || stepSupportsStartAtRole(step, role)) return null;
  return `startAtRole_${role}_not_available_for_step:${step.id}`;
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

This gate performs a clean build, full test suite, and clang-tidy over several packages and typically takes several minutes (up to ~10). Run it as a SINGLE FOREGROUND Bash call with an explicit long timeout (set timeout: 600000 — the 10-minute maximum — on the Bash call) so it completes within that one tool call and you receive its stdout directly. Do NOT run it in the background: a workflow subagent is NOT re-invoked on background-task completion, so a backgrounded gate would leave you polling an empty file until you are nudged and you would never return its result. Do not impose a shorter wall-clock cutoff of your own; the gate has its own internal per-section timeouts that govern real hangs, so honor those return codes. Only if the foreground Bash call itself reaches the 10-minute ceiling should you report that as a timeout (with the command's timed_out/rc if any) rather than guessing a result.

\`\`\`sh
${command}
\`\`\`

When the command has finished, return the JSON object it printed to stdout, verbatim, without changing exit codes, counts, paths, or raw_tail.
Do not summarize instead of returning fields. If a command times out internally, return its timed_out and rc fields.
If the command fails, return its JSON/error exactly and include evidence/log paths if present.
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

function buildReviewerPrompt(step, gate, gateClean, state, attempt, continuation, agentId, findings = "") {
  return `=== Code Reviewer: ${step.id} — ${step.title} ===
You are an adversarial Code Reviewer.
A separate Objective Build Gate runs deterministic build/test/check commands.
You do not need to rerun the gate commands unless the gate output is contradictory or obviously stale.
The workflow script enforces the objective gate. You cannot make a red build/test/check pass by returning accepted:true.
Your job is architecture correctness, scope discipline, stale assumptions, code quality, and interpreting gate failures into actionable fix guidance.
If the objective gate shows build_rc/test_rc/result_rc nonzero or check count above threshold, explain what is wrong and how to fix it.
Your acceptance is necessary but not sufficient.
Reject broad or fragile changes and stale assumptions.
${externalMemoryRoleGuidance("review")}

Important review/commit ordering:
This review runs before the Commit phase. Expected in-scope changes may be modified or untracked at review time. Do not reject solely because expected in-scope files are modified or untracked. Reject unrelated dirty files, generated workflow artifacts, logs, build outputs, transcripts, or scope creep. The Commit phase is responsible for staging per the configured commit policy and for final clean status.
If commit mode is mechanical_all, the Commit phase will run git add -A, so reject unrelated dirty files before accepting.
Gate/review must confirm that git add -A is safe because the tree contains only accepted in-scope changes.

${contextEconomyPolicy("review")}
${priorContextBlock(state, findings)}
Review the current repository diff, durable handoffs, changed paths, and fresh objective-gate evidence. Use targeted verification around concrete file, symbol, command, and evidence references. Only rediscover broadly when necessary and state why.
Do not assume every reviewed change came solely from the latest Developer invocation; review current workflow state and evidence instead.
${handoffInstructions(step, "REVIEW", 0, attempt, continuation, agentId)}

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
Do not selectively stage. Do not rewrite the commit message creatively.
Do not commit if review or objective gate acceptance failed; if you are invoked after a failed review/gate, report failed.
If status_after is not empty, fail loudly and set clean_after:false.
If git commit says nothing to commit, report that exactly.
${externalMemoryRoleGuidance("commit")}
Return the final status and commit hash if a commit was created.`;
  }
__MECHANICAL_PATHS_BRANCH__
  throw new Error(`unsupported_commit_mode:${policy.mode}`);
}

function formatRedFindings(red) {
  return (red?.failures_found || []).map((finding) => `[FAIL] ${finding.test_name}: ${finding.detail}`).join("\n") || red?.notes || "Red Team reported failures.";
}

function formatCodeReviewFindings(cr) {
  return (cr?.findings || [])
    .map((f) => `[${(f.severity || "").toUpperCase()}] ${f.file ? f.file + ": " : ""}${f.detail}`)
    .join("\n") || cr?.summary || "Code review reported findings.";
}

// Blocking = a blocker/major finding that should short-circuit back to dev/fix
// BEFORE a red-team cycle is spent (the cheap-filter rationale). Minor findings
// are advisory and do not gate.
function codeReviewBlocking(cr) {
  if (!cr) return false;
  if (cr.clean === true) return false;
  return (cr.findings || []).some((f) => f.severity === "blocker" || f.severity === "major");
}

// Emit the /code-review filter agent. Reads the diff (or the step's touched
// files) and reports diff-readable logic bugs -- the cheap complement to the
// expensive red-team harness. Runs the /code-review skill via the Skill tool the
// agents already have; applies fixes with --fix only when configured.
async function runCodeReview(step, placement, state, runtime, stage, results) {
  const cr = step.codeReview;
  const scopeArg = cr.scope === "step" ? "the files this step touched" : "the current working-tree diff";
  const fixArg = cr.applyFixes ? " --fix" : "";
  const agentId = `code_review_${placement}`;
  const outcome = await invokeSubstantiveRoleWithContinuations({
    step, role: "code_review", cycle: 0, attempt: 0, agentId,
    state, runtime, stage, results,
    label: `${step.id} code-review ${placement}`, model: step.model, effort: cr.effort, schema: CODE_REVIEW_SCHEMA,
    promptFor: ({ continuation, continuationBlock }) => `${continuationBlock}
=== CODE-REVIEW FILTER: ${step.id} — ${step.title} (${placement}) ===
You are a cheap, narrow code-review FILTER, distinct from the holistic Code Reviewer.
Invoke the /code-review skill at effort ${cr.effort} over ${scopeArg}${fixArg}.
Purpose: catch diff-readable logic bugs (e.g. a fix that edits one branch and forgets another) for the cost of one pass, so the expensive red-team harness work is reserved for behavioral/protocol/security defects that need runtime proof. Do NOT attempt runtime adversarial testing here.
Report findings as machine-readable CODE_REVIEW_SCHEMA. Set placement:"${placement}". Set clean:true only if no blocker/major finding remains. If you ran with --fix, set fixes_applied accordingly.
${contextEconomyPolicy("code_review")}
${priorContextBlock(state)}
${handoffInstructions(step, "CODE_REVIEW", 0, 0, continuation, `${agentId}_k${continuation}`)}`,
  });
  return outcome;
}

// Emit the fanned red-team round: one blindered lens agent per configured lens
// (run as a pipeline so each lens's findings verify as soon as that lens
// finishes -- fast lenses are not blocked by the slow one), each finding
// adversarially verified by `verifyVotes` refuters, aggregated into ONE
// RED_SCHEMA report so downstream cycle/convergence routing is unchanged.
async function runFannedRedTeam(step, cycle, state, runtime, stage, results) {
  const fan = step.redteamFan;
  const attackPhase = `${step.id} red team ${cycle} attack`;
  const verifyPhase = `${step.id} red team ${cycle} verify`;
  const majority = Math.floor(fan.verifyVotes / 2) + 1;

  const perLens = await pipeline(
    fan.lenses,
    (lens) => agent(
      `=== FANNED RED TEAM LENS [${lens.key}]: ${step.id} — ${step.title} (cycle ${cycle}) ===
You are ONE red-team lens. You are BLIND to the other lenses on purpose.
Attack ONLY your assigned surface; do not broaden. Write adversarial WHITE BOX tests/spec checks and run deterministic repros. Do not silently patch the implementation.
Report failures in structured form (RED_SCHEMA).
${externalMemoryRoleGuidance("redteam")}
Your lens mandate:
${lens.prompt}

${step.prompt.redteam}`,
      agentOptions({ label: `attack:${lens.key}`, phase: attackPhase, model: fan.model, effort: fan.effort, schema: RED_SCHEMA })
    ),
    (red, lens) => {
      const findings = (red && red.failures_found) || [];
      if (!fan.verify || findings.length === 0) {
        return { lens, red, confirmed: findings };
      }
      return parallel(findings.map((finding) => () =>
        parallel(Array.from({ length: fan.verifyVotes }, (_unused, voteIndex) => () =>
          agent(
            `=== FANNED RED-TEAM VERIFIER (lens ${lens.key}, vote ${voteIndex + 1}): ${step.id} ===
Adversarially verify one red-team finding. TRY TO REFUTE it. Default to real:false when uncertain.
Finding: ${finding.test_name}
Detail: ${finding.detail}`,
            agentOptions({ label: `verify:${lens.key}`, phase: verifyPhase, model: fan.model, effort: fan.effort, schema: FAN_VERDICT_SCHEMA })
          )
        )).then((votes) => {
          const refuted = (votes || []).filter(Boolean).filter((v) => v.real === false).length;
          return refuted >= majority ? null : finding;
        })
      )).then((verified) => ({ lens, red, confirmed: verified.filter(Boolean) }));
    }
  );

  const lensResults = (perLens || []).filter(Boolean);
  const confirmed = lensResults.flatMap((entry) => entry.confirmed || []);
  const attackTests = lensResults.flatMap((entry) => (entry.red && entry.red.adversarial_tests_written) || []);
  const anyBlocked = lensResults.some((entry) => entry.red && (entry.red.status === "blocked" || entry.red.status === "needs_decision"));

  let critic = null;
  if (fan.completenessCritic) {
    critic = await agent(
      `=== FANNED RED-TEAM COMPLETENESS CRITIC: ${step.id} — ${step.title} (cycle ${cycle}) ===
The following attack lenses ran: ${fan.lenses.map((l) => l.key).join(", ")}.
Confirmed findings so far:
${confirmed.map((f) => `- ${f.test_name}: ${f.detail}`).join("\n") || "(none)"}
Name attack surfaces NO lens covered. Suggest new lens keys + rationale. You are advisory only; do not run attacks.`,
      agentOptions({ label: `${step.id} fan critic ${cycle}`, phase: attackPhase, model: fan.model, effort: fan.effort, schema: FAN_CRITIC_SCHEMA })
    );
  }

  // Aggregate into the SAME RED_SCHEMA the single-agent path produces so the
  // caller's cycle/convergence logic is untouched.
  const status = anyBlocked ? "blocked" : (confirmed.length === 0 ? "all_passed" : "failures_found");
  const criticNote = critic
    ? `\nCompleteness critic — uncovered: ${(critic.uncovered_surfaces || []).join("; ") || "(none)"}; suggested lenses: ${(critic.suggested_lenses || []).map((s) => s.key).join(", ") || "(none)"}`
    : "";
  return {
    status,
    summary: `Fanned red team: ${fan.lenses.length} lenses, ${confirmed.length} confirmed finding(s) after verify (votes=${fan.verifyVotes}).${criticNote}`,
    adversarial_tests_written: attackTests,
    tests_passed: confirmed.length === 0,
    failures_found: confirmed,
    external_memory_notes: "",
    handoff: "",
    notes: criticNote.trim(),
    lens_results: lensResults.map((entry) => ({ key: entry.lens.key, confirmed: (entry.confirmed || []).length })),
  };
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
  let START_AT_ROLE;
  try { START_AT_ROLE = normalizeStartAtRole(WORKFLOW_ARGS.startAtRole || null); }
  catch (error) { return { halted_at: "selection", reason: error.message, stage: STAGE, results: [] }; }
  let RESUME_CYCLE;
  let RESUME_ATTEMPT;
  try {
    RESUME_CYCLE = intArg(WORKFLOW_ARGS.resumeCycle, 1, "resumeCycle");
    RESUME_ATTEMPT = intArg(WORKFLOW_ARGS.resumeAttempt, START_AT_ROLE === "dev_fix" ? 2 : 1, "resumeAttempt");
  }
  catch (error) { return { halted_at: "selection", reason: error.message, stage: STAGE, results: [] }; }
  const BACKCOMPAT_BEADS_SNAPSHOT = WORKFLOW_ARGS.beadsSnapshot || "";
  const PREFLIGHT_SUMMARY = WORKFLOW_ARGS.preflightSummary || "(no preflightSummary supplied)";
  const HANDOFF_PATH = WORKFLOW_ARGS.handoffPath || "";
  const RESUME_GATE_EVIDENCE_PATHS = uniqueNonEmpty([
    WORKFLOW_ARGS.gateEvidencePath,
    ...(Array.isArray(WORKFLOW_ARGS.gateEvidencePaths) ? WORKFLOW_ARGS.gateEvidencePaths : []),
  ]);
  const RESUME_CHANGED_PATHS = uniqueNonEmpty([
    ...(Array.isArray(WORKFLOW_ARGS.changedPaths) ? WORKFLOW_ARGS.changedPaths : []),
    ...(Array.isArray(WORKFLOW_ARGS.resumeChangedPaths) ? WORKFLOW_ARGS.resumeChangedPaths : []),
  ]);
  const RESUME_FINDINGS = typeof WORKFLOW_ARGS.resumeFindings === "string" ? WORKFLOW_ARGS.resumeFindings : "";
  const runtime = { BACKCOMPAT_BEADS_SNAPSHOT, PREFLIGHT_SUMMARY, HANDOFF_PATH };
  const results = [];
  let steps;
  const startAtRoleError = validateStartAtRoleArgs(START_AT_ROLE, ONLY_STEP, HANDOFF_PATH, RESUME_GATE_EVIDENCE_PATHS);
  if (startAtRoleError) return { halted_at: "selection", reason: startAtRoleError, stage: STAGE, results };
  try { steps = selectSteps(STAGE, FROM_STEP, ONLY_STEP); }
  catch (error) { return { halted_at: "selection", reason: error.message, stage: STAGE, results }; }

  for (const step of steps) {
    const startAtRoleStepError = validateStartAtRoleForStep(step, START_AT_ROLE);
    if (startAtRoleStepError) return { halted_at: `${step.id}:selection`, reason: startAtRoleStepError, stage: STAGE, results };
    const handoffState = {
      priorHandoffPaths: uniqueNonEmpty([runtime.HANDOFF_PATH]),
      gateEvidencePaths: [...RESUME_GATE_EVIDENCE_PATHS],
      changedPaths: [...RESUME_CHANGED_PATHS],
      inspectedPaths: [],
      knownDirtyPaths: [],
      testsRun: [],
      checkpoints: [],
    };
    const stepResult = { step: step.id, start_at_role: START_AT_ROLE, scope: null, discovery: null, dev_cycles: [], review_attempts: [], impl: null, gate: null, gate_clean: true, review: null, commit: null };
    results.push(stepResult);

    if (step.phases.includes("scope") && roleIsAtOrAfter(START_AT_ROLE, "scope")) {
      const scoped = await invokeSubstantiveRoleWithContinuations({
        step, role: "scope", cycle: 0, attempt: 0, agentId: "scope",
        state: handoffState, runtime, stage: STAGE, results,
        label: `${step.id} scope`, model: step.model, effort: step.effort, schema: SCOPE_SCHEMA,
        promptFor: ({ continuation, continuationBlock }) => `${continuationBlock}
=== SCOPING TEST WRITER: ${step.id} — ${step.title} ===
Write BLACK BOX tests/spec artifacts ONLY. No implementation code.
Strictly follow the step scope.
${externalMemoryRoleGuidance("scope")}
${contextEconomyPolicy("scope")}
${priorContextBlock(handoffState)}
${handoffInstructions(step, "SCOPE", 0, 0, continuation, `scope_k${continuation}`)}

${step.prompt.scope}`,
      });
      if (scoped.halt) return scoped.halt;
      const scope = scoped.output;
      stepResult.scope = scope;
      if (!scope || scope.status !== "done" || scope.scope_ok !== true) {
        return { halted_at: `${step.id}:scope`, reason: scope?.status || "scope_rejected", stage: STAGE, results };
      }
    }

    const discoveryEnabled = (!!(step.discovery && step.discovery.enabled) || step.phases.includes("discovery")) && roleIsAtOrAfter(START_AT_ROLE, "discovery");
    if (discoveryEnabled) {
      const discovered = await invokeSubstantiveRoleWithContinuations({
        step, role: "discovery", cycle: 0, attempt: 0, agentId: "discovery",
        state: handoffState, runtime, stage: STAGE, results,
        label: `${step.id} discovery`, model: step.discovery?.model || step.model, effort: step.discovery?.effort || "high", schema: DISCOVERY_SCHEMA,
        promptFor: ({ continuation, continuationBlock }) => `${continuationBlock}
=== DISCOVERY AGENT: ${step.id} — ${step.title} ===
You are the Discovery agent. Perform broad but bounded repository/source discovery for this step.
Do not edit production code unless the workflow phase explicitly asks for edits. Your output is a compact repo map handoff for Developer.
Identify exact files, symbols, tests, command entrypoints, and risks likely relevant to this step.
Tell Developer what NOT to rediscover.
${contextEconomyPolicy("discovery")}
${priorContextBlock(handoffState)}
${handoffInstructions(step, "DISCOVERY", 0, 0, continuation, `discovery_k${continuation}`)}

Discovery task from workflow.yaml:
${step.prompt.discovery || "Create a compact repo map for this step. Identify likely files/symbols/tests and boundaries; do not implement."}`,
      });
      if (discovered.halt) return discovered.halt;
      const discovery = discovered.output;
      stepResult.discovery = discovery;
      if (!discovery || discovery.status !== "done") {
        return { halted_at: `${step.id}:discovery`, reason: discovery?.status || "discovery_escalation", stage: STAGE, results };
      }
    }

    let lastImpl = null;
    const skipDevRedForStartRole = START_AT_ROLE && roleRank(START_AT_ROLE) > roleRank("redteam");
    const devRedStartCycle = (START_AT_ROLE === "dev" || START_AT_ROLE === "redteam") ? RESUME_CYCLE : 1;
    let redPassed = skipDevRedForStartRole || !(step.phases.includes("dev") || step.phases.includes("redteam"));
    let redFindings = RESUME_FINDINGS;
    const redTestFiles = [];
    const devCycles = step.phases.includes("dev") ? MAX_DEV_RED_CYCLES : 1;
    for (let cycle = devRedStartCycle; cycle <= devCycles && !redPassed; cycle++) {
      const skipInitialDevForRedteamEntry = START_AT_ROLE === "redteam" && cycle === devRedStartCycle;
      const runDevThisCycle = step.phases.includes("dev") &&
        !skipInitialDevForRedteamEntry &&
        (!START_AT_ROLE || START_AT_ROLE === "dev" || START_AT_ROLE === "redteam" || roleIsAtOrAfter(START_AT_ROLE, "dev"));
      const runRedThisCycle = step.phases.includes("redteam") &&
        (!START_AT_ROLE || START_AT_ROLE === "dev" || START_AT_ROLE === "redteam" || roleIsAtOrAfter(START_AT_ROLE, "redteam"));
      if (runDevThisCycle) {
        const implemented = await invokeSubstantiveRoleWithContinuations({
          step, role: "dev", cycle, attempt: 0, agentId: `dev_${cycle}`,
          state: handoffState, runtime, stage: STAGE, results,
          label: `${step.id} dev ${cycle}`, model: step.model, effort: step.effort, schema: IMPL_SCHEMA,
          promptFor: ({ continuation, continuationBlock }) => `${continuationBlock}
=== DEVELOPER: ${step.id} — ${step.title} (cycle ${cycle}) ===
Implement only this sub-step. Pass the Scoping Tests.
Respect invariants and out-of-scope boundaries.
If Red Team or Reviewer findings are supplied, address exactly those findings.
${externalMemoryRoleGuidance("dev")}
${contextEconomyPolicy("dev")}
${priorContextBlock(handoffState, redFindings)}
${stepResult.discovery?.handoff_path ? "Discovery did the broad map for this step. Target the files/symbols named in the Discovery handoff and avoid global rediscovery by default. You may verify source locally before edits." : "No Discovery handoff exists for this step; keep discovery proportional and explain any broad grep/read sweeps."}
${handoffInstructions(step, "DEV", cycle, 0, continuation, `dev_${cycle}_k${continuation}`)}

${step.prompt.dev}${redFindings ? `\n\nThe Red Team found these failures:\n${redFindings}` : ""}`,
        });
        if (implemented.halt) return implemented.halt;
        const impl = implemented.output;
        lastImpl = impl;
        stepResult.impl = impl;
        if (!impl || impl.status !== "done" || impl.scope_ok !== true) {
          stepResult.dev_cycles.push({ cycle, impl });
          return { halted_at: `${step.id}:dev`, reason: impl?.status || "implementer_escalation", stage: STAGE, results };
        }
      }

      // Optional cheap /code-review filter placed BEFORE the red-team round
      // (post_dev / pre_redteam). A blocking finding short-circuits back to
      // dev/fix without spending a red-team cycle.
      if (runDevThisCycle && step.codeReview && step.codeReview.enabled &&
          (step.codeReview.placement === "post_dev" || step.codeReview.placement === "pre_redteam")) {
        const crOutcome = await runCodeReview(step, step.codeReview.placement, handoffState, runtime, STAGE, results);
        if (crOutcome.halt) return crOutcome.halt;
        const cr = crOutcome.output;
        stepResult.code_review = stepResult.code_review || [];
        stepResult.code_review.push({ cycle, placement: step.codeReview.placement, cr });
        if (codeReviewBlocking(cr)) {
          // Feed findings into the next dev cycle's redFindings channel and skip
          // the red team this cycle (the expensive oracle runs only on clean diffs).
          redFindings = formatCodeReviewFindings(cr);
          redPassed = false;
          continue;
        }
      }

      if (runRedThisCycle) {
        let red;
        if (step.redteamFan && step.redteamFan.enabled) {
          // Fanned red team: parallel blindered lenses + adversarial verify,
          // aggregated into one RED_SCHEMA report (see runFannedRedTeam).
          red = await runFannedRedTeam(step, cycle, handoffState, runtime, STAGE, results);
        } else {
          const redTeamed = await invokeSubstantiveRoleWithContinuations({
            step, role: "redteam", cycle, attempt: 0, agentId: `redteam_${cycle}`,
            state: handoffState, runtime, stage: STAGE, results,
            label: `${step.id} red team ${cycle}`, model: step.model, effort: "high", schema: RED_SCHEMA,
            promptFor: ({ continuation, continuationBlock }) => `${continuationBlock}
=== ADVERSARIAL RED TEAM: ${step.id} — ${step.title} (cycle ${cycle}) ===
You are the Red Team. Read the Developer implementation.
Write adversarial WHITE BOX tests/spec checks designed to break it.
Run relevant deterministic tests. Do not silently patch implementation.
Report failures in structured form.
${externalMemoryRoleGuidance("redteam")}
${contextEconomyPolicy("redteam")}
${priorContextBlock(handoffState)}
Start from the current diff, Developer handoff, and targeted verification. Do not redo broad repo discovery unless necessary.
${handoffInstructions(step, "REDTEAM", cycle, 0, continuation, `redteam_${cycle}_k${continuation}`)}

${step.prompt.redteam}`,
          });
          if (redTeamed.halt) return redTeamed.halt;
          red = redTeamed.output;
        }
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
    let accepted = START_AT_ROLE === "commit" ? true : !(step.phases.includes("review") || gateEnabled);
    let priorReviewFindings = RESUME_FINDINGS;
    let lastReview = null;
    let lastGate = null;
    let lastGateClean = !gateEnabled;
    const reviewStartAttempt = ["gate", "review", "dev_fix"].includes(START_AT_ROLE) ? RESUME_ATTEMPT : 1;
    const reviewAttempts = step.phases.includes("review") ? Math.max(MAX_REVIEW_ATTEMPTS, reviewStartAttempt) : reviewStartAttempt;
    for (let attempt = reviewStartAttempt; attempt <= reviewAttempts && !accepted; attempt++) {
      const skipFixForDirectGateOrReviewEntry = ["gate", "review"].includes(START_AT_ROLE) && attempt === reviewStartAttempt;
      if (attempt > 1 && !skipFixForDirectGateOrReviewEntry) {
        const fixed = await invokeSubstantiveRoleWithContinuations({
          step, role: "dev_fix", cycle: 0, attempt, agentId: `dev_fix_${attempt}`,
          state: handoffState, runtime, stage: STAGE, results,
          label: `${step.id} dev fix ${attempt}`, model: step.model, effort: step.effort, schema: IMPL_SCHEMA,
          promptFor: ({ continuation, continuationBlock }) => `${continuationBlock}
=== DEVELOPER FIX PASS: ${step.id} — ${step.title} (review attempt ${attempt}) ===
Implement only this sub-step and respect all invariants and boundaries.
Address exactly these Code Reviewer findings:
The findings block may also contain Objective Build Gate failures. Address both sources exactly.
${priorReviewFindings}
${contextEconomyPolicy("dev_fix")}
${priorContextBlock(handoffState, priorReviewFindings)}
${handoffInstructions(step, "DEV_FIX", 0, attempt, continuation, `dev_fix_${attempt}_k${continuation}`)}

${step.prompt.dev}`,
        });
        if (fixed.halt) return fixed.halt;
        const fixImpl = fixed.output;
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
      rememberGateEvidence(handoffState, gate);

      let review = null;
      if (step.phases.includes("review")) {
        const reviewed = await invokeSubstantiveRoleWithContinuations({
          step, role: "review", cycle: 0, attempt, agentId: `review_${attempt}`,
          state: handoffState, runtime, stage: STAGE, results,
          label: `${step.id} review ${attempt}`, model: step.model, effort: "high", schema: REVIEW_SCHEMA,
          promptFor: ({ continuation, continuationBlock }) =>
            `${continuationBlock}\n${buildReviewerPrompt(step, gate, gateClean, handoffState, attempt, continuation, `review_${attempt}_k${continuation}`, priorReviewFindings)}`,
        });
        if (reviewed.halt) return reviewed.halt;
        review = reviewed.output;
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

    // Optional final comprehensive /code-review pass: one audit of the whole
    // accepted step diff before commit. Unlike the pre-redteam filter this does
    // not loop back to dev/fix (review already accepted); a blocking finding
    // halts the step so a human decides.
    if (step.codeReview && step.codeReview.enabled && step.codeReview.placement === "final" &&
        roleIsAtOrAfter(START_AT_ROLE, "review")) {
      const crOutcome = await runCodeReview(step, "final", handoffState, runtime, STAGE, results);
      if (crOutcome.halt) return crOutcome.halt;
      const cr = crOutcome.output;
      stepResult.code_review = stepResult.code_review || [];
      stepResult.code_review.push({ cycle: 0, placement: "final", cr });
      if (codeReviewBlocking(cr)) {
        return { halted_at: `${step.id}:code_review_final`, reason: "code_review_blocking_finding", stage: STAGE, results };
      }
    }

    if (step.phases.includes("commit") && roleIsAtOrAfter(START_AT_ROLE, "commit")) {
      const commitPolicy = commitPolicyForStep(step);
      const changed = Array.from(new Set([
        ...(lastImpl?.files_changed || []),
        ...(stepResult.scope?.test_files_written || []),
        ...RESUME_CHANGED_PATHS,
        ...redTestFiles,
      ])).filter(Boolean);
      if (commitPolicy.mode === "none") {
        stepResult.commit = { status: "skipped", summary: "commit_mode none", commit_hash: null, commit_rc: 0, status_before: "", status_after: "", clean_after: true, notes: "" };
      } else {
        const commitResult = await agent(
          withRuntimeContext(commitAgentPrompt(step, commitPolicy, changed), runtime),
          agentOptions({ label: `${step.id} commit`, phase: step.id, model: commitPolicy.model, effort: commitPolicy.effort, schema: COMMIT_SCHEMA })
        );
        stepResult.commit = commitResult;
        if (!commitResult || commitResult.status === "failed") {
          return { halted_at: `${step.id}:commit`, reason: "commit_failed", stage: STAGE, results };
        }
        // Trust the agent's clean_after boolean (which it sets from `git status --short`)
        // as the authoritative cleanliness signal. status_after is advisory context only:
        // agents frequently return prose there ("clean; branch ... ahead by N") which is
        // NOT dirtiness, so re-parsing it as a raw short-status string false-halts an
        // actually-clean tree. Only fall back to the status_after string when the agent
        // omitted clean_after entirely.
        const commitClean = ["committed", "nothing_to_commit", "skipped"].includes(commitResult.status) &&
          (typeof commitResult.clean_after === "boolean"
            ? commitResult.clean_after === true
            : !String(commitResult.status_after || "").trim());
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
    stepResult.handoff_paths = handoffState.priorHandoffPaths;
    stepResult.gate_evidence_paths = handoffState.gateEvidencePaths;
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
        "__EXTERNAL_MEMORY_CONFIG__": _json(external_memory_config),
        "__CONTEXT_ECONOMY__": _json(asdict(spec.context_economy)),
        "__EXTERNAL_MEMORY_CONTEXT_JS__": external_memory_context_js,
        "__EXTERNAL_MEMORY_ROLE_JS__": external_memory_role_js,
        "__STAGES__": _json(stages),
        "__MECHANICAL_PATHS_BRANCH__": '''  if (policy.mode === "mechanical_paths") {
    return `=== SAFE COMMIT AGENT: ${step.id} — ${step.title} ===
Commit only after accepted review. Run git status --short before and after staging.
NEVER use git add -A. NEVER use git add . NEVER use git commit -a.
Stage these explicit paths only:
${changed.length ? changed.map((path) => `  - ${path}`).join("\\n") : "  (none reported; do not create an empty commit)"}
${externalMemoryRoleGuidance("commit")}
Commit with: git commit -m ${shellQuote(message)}
Return COMMIT_SCHEMA fields including commit_rc, status_after, and clean_after.`;
  }''' if uses_mechanical_paths else "",
    }
    for marker, value in replacements.items():
        template = template.replace(marker, value)
    return template
