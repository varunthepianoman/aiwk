# AIWK Codex Renderer: Design and Implementation Plan

Status: proposed

## Purpose

Add a Codex execution backend without weakening the workflow guarantees already
provided by `workflow.yaml`, durable specs, handoffs, objective gates, bounded
fix/review loops, and commit policy.

The operator experience should parallel the existing Claude renderer:

```bash
aiwk render codex-workflow --config /path/to/aiwk.yaml
```

The command should validate the same provider-neutral `WorkflowSpec` and emit a
self-contained runner plus coordinator runbook. The runner should execute Codex
roles with explicit working directory, sandbox, model/reasoning settings,
structured results, durable handoffs, retries, gate evidence, and resumable
thread state.

This is a renderer/runtime project. It must not fork the workflow schema into
Claude-specific and Codex-specific dialects.

## Decision: SDK-first, with AIWK owning orchestration

Use the Codex SDK as the primary execution interface and keep orchestration in
generated AIWK code.

AIWK remains responsible for:

- stage and step selection;
- role ordering;
- parallel fan-out and result collection;
- bounded developer/red-team/reviewer cycles;
- durable handoff and evidence paths;
- objective gate invocation;
- resume routing;
- commit policy;
- final structured workflow status.

Each Codex thread performs one scoped role invocation. The generated runner
supplies the role prompt, `cwd`, sandbox, model/reasoning settings, and prior
handoffs, then validates the structured result.

This boundary is preferable to asking one parent Codex conversation to
improvise the workflow with native subagents. Native subagents are useful
interactively, but host-level orchestration gives AIWK stable state transitions,
explicit thread IDs, deterministic retry limits, and control over objective
gates.

### Primary interface: Codex SDK

The official SDK is intended for programmatic control of local Codex agents and
supports starting, continuing, and resuming threads. It is the right default for
coding-focused workflows owned by AIWK.

Candidate output:

```text
generated/<project>.codex_workflow.mjs
```

Start with the TypeScript/JavaScript SDK because AIWK already emits JavaScript,
the Claude renderer contains reusable JavaScript routing patterns, and the SDK
is documented for server-side Node.js 18+. A JavaScript ESM artifact avoids
making the Python CLI itself own asynchronous orchestration.

The Python SDK may later be attractive because AIWK is Python, but it is
currently documented as beta. Do not choose it first unless the compatibility
spike demonstrates a materially better fit.

### Fallback: `codex exec`

`codex exec` is a useful prototype and compatibility fallback because it offers
non-interactive execution, explicit sandboxing, JSONL events, JSON-Schema final
output, and session resumption.

It is less attractive as the final backend because AIWK would manage
subprocesses, event streams, thread IDs, and parallel roles itself. Use it if
the SDK cannot provide required structured-output, resume, sandbox, or
cancellation behavior.

### Not recommended for v1

- Do not build directly on app-server. It is the lower-level rich-client
  interface; official guidance recommends the SDK for automation.
- Do not add Codex MCP plus the Agents SDK. That is appropriate when Codex is
  one specialist in a broader agent workflow. AIWK already owns software
  delivery orchestration, gates, and handoffs.
- Do not depend on the VS Code extension or desktop app. They are operator
  surfaces, not runtime prerequisites.

## Required compatibility spike

Before the full renderer, prove the selected installed runtime can:

1. Start a thread in a selected `cwd`.
2. Run a writer with workspace-write access.
3. Run a verifier with read-only access.
4. Capture the thread ID and resume in a new process.
5. Request and validate an AIWK role JSON result.
6. Distinguish success, model failure, timeout, interruption, and malformed
   output.
7. Run at least two read-only verifier threads concurrently.
8. Cancel or time out a turn without hanging.
9. Reuse local authentication without copying credentials into the project.
10. Select configured model/reasoning settings or report an exact unsupported
    setting.

Decision after the spike:

- If the SDK covers all items, use it directly.
- If only structured output is missing, use the SDK plus a validated JSON
  envelope and one bounded same-thread schema-repair turn.
- If resume, sandbox, or cancellation is insufficient, implement an initial
  `codex exec` backend and retain SDK integration as follow-up.
- Never drop structured validation, sandbox separation, or durable resume just
  to claim completion.

## Provider boundaries

### Reuse unchanged

Keep these provider-neutral:

- `aiwk/workflow_spec.py`
- `aiwk/config.py`
- `aiwk/gate_runner.py`
- `aiwk/context_pack.py`
- `aiwk/checkpoint.py`
- `aiwk/git_utils.py`
- durable spec, invariant, and gate files;
- handoff names and required fields;
- objective gate evidence format;
- stage/step/phase semantics;
- commit modes and message templates.

### Extract only genuinely shared rendering helpers

Avoid copying the entire 1,600-line Claude renderer. First characterize current
behavior, then extract small shared helpers for:

- resolved workflow metadata;
- embedded durable context;
- role prompt context;
- commit-policy metadata;
- role result JSON Schemas;
- canonical handoff/evidence paths;
- provider-aware coordinator instructions.

Possible layout:

```text
aiwk/
  render.py
  renderer_context.py
  role_schemas.py
  coordinator.py
  renderers/
    claude_workflow.py
    codex_workflow.py
```

Do not extract provider-specific prompt wording or agent-call syntax merely to
maximize reuse. Claude output should remain behavior-compatible throughout.

## CLI and output

Add a sibling target:

```bash
aiwk render codex-workflow \
  --config /path/to/aiwk.yaml \
  [--workflow-spec /path/to/workflow.yaml] \
  [--out /path/to/generated.mjs]
```

Return:

```json
{
  "status": "rendered",
  "provider": "codex",
  "workflow_spec": "/absolute/path/workflow.yaml",
  "output_path": "/absolute/path/generated/project.codex_workflow.mjs",
  "coordinator_path": "/absolute/path/master_coordinator_prompt.md"
}
```

Keep `claude-workflow` and its output path backward compatible. Make the
coordinator prompt provider-aware with exact render, preflight, syntax-check,
and launch commands. Project requirements remain in durable inputs, never only
in generated operator prose.

## Generated runtime

### Launch and resume state

Preserve current controls where provider-neutral:

- `stage`, `onlyStep`, `fromStep`, and `startAtRole`;
- `resumeCycle` and `resumeAttempt`;
- `preflightSummary`, `handoffPath`, and `gateEvidencePath`;
- `resumeFindings`;
- optional advisory external-memory snapshot.

Persist thread IDs and role completion records atomically, for example:

```text
state/codex/<stage>/<step>/runtime_state.json
```

Record the workflow/spec fingerprint, current role/cycle/attempt, role thread
IDs, completed handoffs, latest gate evidence, terminal/resumable status, and
runtime version. Never store credentials.

Reject resume when the durable fingerprint changed unless the operator chooses
a fresh role boundary. Never combine an old thread with materially changed
specifications silently.

### Role invocation

Every role receives:

- stable identity and mandate;
- current step prompt;
- durable spec/invariant/gate context or documented paths;
- accepted prior handoffs;
- gate evidence when relevant;
- known dirty paths and scope constraints;
- required result schema;
- requirement to complete a durable handoff.

Recommended permissions:

| Role | Sandbox | Policy |
| --- | --- | --- |
| Scope / Discovery | read-only | No source edits |
| Developer / Developer fix | workspace-write | Sole source writer |
| Code review / Red team / Final review | read-only | Findings only |
| Gate | no model write access | `aiwk gate-run` owns execution |
| Commit | workspace-write | Only when commit policy authorizes |

If a read-only Codex thread cannot write its handoff path, return structured
handoff content and let the trusted host runner write it. Do not grant source
write access solely for handoff emission.

### Structured results

Preserve fields such as:

- `status`
- `handoff_path`
- `files_changed` and `files_inspected`
- `tests_run`
- `gate_evidence_paths`
- `known_dirty_paths`
- role-specific findings or acceptance decision
- `next_agent_should_read`

Validate every result. Allow one bounded schema-repair turn on the same thread.
If repair fails, halt structurally; never infer missing fields from prose.

### Routing

Mirror mature AIWK routing:

1. Scope, optionally Discovery.
2. Developer.
3. Optional code-review filter and developer correction.
4. Red team or parallel fan and developer correction.
5. Objective gate.
6. Holistic reviewer.
7. Bounded developer-fix, gate, and review retries.
8. Optional commit according to policy.

The runner, not a model, owns counters and next-role decisions.

For a red-team fan, launch one independent read-only thread per lens against the
same frozen diff/spec fingerprint. Bound concurrency, collect results, and run
verification/critic roles according to existing configuration. Never run
parallel writers in one worktree.

## Gates, permissions, and authentication

- Continue invoking `aiwk gate-run`; Codex must not simulate deterministic gate
  commands.
- Preserve current timeouts, return codes, output capture, check counts,
  evidence paths, and `gate_clean` semantics.
- Use least-privileged sandboxes per role.
- In non-interactive runs, an approval requirement becomes a structured failure;
  the runner must not wait indefinitely for UI input.
- Reuse local Codex authentication for operator-launched work.
- Never copy `auth.json`, API keys, or tokens into generated files, state,
  prompts, handoffs, or logs.
- CI credentials and secret isolation are a later deployment concern.

## Reliable mechanical renames

Developer prompts should distinguish semantic edits from mechanical symbol/path
migrations. For broad class, function, namespace, include, or file changes:

1. Inventory definitions, declarations, call sites, tests, build files,
   documentation, serialized names, and compatibility references with `rg` or
   an indexed language search.
2. Define an exact old-to-new map before editing.
3. Use language-aware rename or a reviewed scripted replacement bounded to an
   explicit file list. Do not hand-retype dozens of occurrences.
4. Use `git mv` for tracked file and directory renames.
5. Review the mechanical diff separately from semantic changes.
6. Search every old spelling afterwards and classify intentional survivors.
7. Search new spellings for missed declaration/definition pairs and accidental
   duplicate replacements.
8. Compile and run focused tests immediately before adding semantic changes.

Blind repository-wide replacement is not acceptable. Scope replacements by
symbol, path, file type, or explicit file list, then prove them with residual
searches and compiler/tests.

## Implementation phases

### Phase 0: characterization

- Pin Claude render output, CLI result, coordinator instructions, schemas,
  routing, fans, and commit modes.
- Identify provider-neutral fields both renderers must honor.
- Avoid changing generated Claude behavior.

### Phase 1: Codex compatibility spike

- Exercise thread start/resume, sandbox transitions, structured results,
  concurrency, timeout, and interruption.
- Record SDK versus `codex exec` decision here.

### Phase 2: shared context extraction

- Extract durable-context, schema, policy, path, and coordinator helpers.
- Keep Claude characterization tests green.

### Phase 3: minimal renderer

- Add `aiwk/renderers/codex_workflow.py` and the CLI target.
- Render Scope, Developer, Gate, Review, and `commit: none` first.
- Support clean start and structured halt before complex resume.

### Phase 4: parity routing

- Add Discovery, code review, red-team loops/fan, reviewer-fix loops,
  checkpoints, resume, and atomic runtime state.
- Add commit modes only after no-commit work is stable.

### Phase 5: failure tests

- Use a fake SDK adapter for deterministic tests.
- Add opt-in live smoke tests guarded by installed Codex/auth availability.
- Cover malformed output, failed commands, timeout, interruption, stale state,
  changed fingerprints, and partial fan completion.

### Phase 6: docs and migration

- Update README, user guide, workflow reference, and coordinator examples.
- Document Node/package prerequisites, auth, launch, resume, and troubleshooting.
- Keep Claude supported and do not auto-migrate projects.

## Tests

Add at least:

- `tests/test_render_codex_workflow.py`
- `tests/test_codex_runtime_state.py`
- `tests/test_renderer_context.py`
- CLI tests for both targets;
- provider-aware coordinator tests;
- fake-SDK routing/failure tests;
- render coverage for Discovery, code review, fan, gates, external memory, and
  every commit mode;
- Claude compatibility regressions;
- `node --check` for generated JavaScript;
- one opt-in local Codex smoke test excluded from normal unit tests.

The fake SDK must script responses, thread IDs, sandbox assertions, delays,
failures, and interruption without tokens, network, or auth.

## Acceptance criteria

1. `aiwk render codex-workflow` renders every supported `WorkflowSpec` feature.
2. Claude behavior and tests remain green.
3. A clean no-commit example completes Scope through Review with handoffs and
   gate evidence.
4. Writer roles can write and verifier roles cannot edit source.
5. Parallel red-team lenses converge through the verified-findings contract.
6. Resume survives process restart and safely rejects stale spec state.
7. Malformed output, timeout, interruption, approvals, and gate failures produce
   bounded retries or structured halts, never hangs.
8. No credential reaches generated artifacts, state, handoffs, or logs.
9. `commit: none` performs no Git mutation; authorized modes preserve existing
   cleanliness policy.
10. Operator documentation covers prerequisites, launch, resume, evidence, and
    troubleshooting.

## Effort

- Minimal useful backend: about 1-2 focused engineering days after the spike.
  This covers SDK wrapper, Scope/Developer/Gate/Review, structured results,
  no-commit behavior, unit tests, and one smoke test.
- Reliable AIWK-grade backend: about one focused engineering week. This adds
  full role parity, retries, read-only enforcement, persistent resume, parallel
  fans, fake-SDK failure tests, and provider-aware docs.
- Full operational hardening: about 1-2 weeks total depending on compatibility
  findings. This adds cancellation/partial-fan recovery, all commit modes, a
  live runtime matrix, and detailed diagnostics.

The main uncertainty is not prompt generation. It is proving structured
results, resume, sandbox transitions, interruption, and recovery against the
selected programmatic interface.

## Stop conditions

- Stop if Codex requires changing provider-neutral workflow semantics.
- Stop if shared extraction rewrites the mature Claude renderer before
  characterization tests are green.
- Stop if verifiers need source write access just to emit handoffs.
- Stop if implementation depends on undocumented app-server messages when the
  SDK or supported `codex exec` can provide the behavior.
- Stop if retries can produce concurrent writers in one worktree.
- Stop if old threads can resume silently against changed durable specs.
- Stop if credentials would enter project-controlled files or prompts.

## Official references

- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk.md)
- [Codex non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode.md)
- [Codex app-server](https://learn.chatgpt.com/docs/app-server.md)
- [Codex with the Agents SDK](https://learn.chatgpt.com/docs/mcp-server.md)
- [Codex subagents and custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents.md)

