# Prompt for claude: Upgrade AIWK Renderer with Phase Smoke Tests and Mature Workflow Semantics

You are claude developing AIWK itself.

You are working in a 3-folder VS Code workspace:

```text
~/dev/t_robotics   # robotics repo / target repo, do not edit source for this task
~/dev/.aiwk        # AIWK workflow project folders
~/dev/aiwk         # AIWK tool source code, edit here for this task
```

AIWK is installed in a venv:

```text
~/dev/aiwk/.venv
```

Use explicit venv paths:

```bash
~/dev/aiwk/.venv/bin/aiwk --help
~/dev/aiwk/.venv/bin/python -m aiwk --help
```

Do not use system Python pip. Do not use `--break-system-packages`.

## Mission

AIWK currently has:

```text
Pass 1 — durable substrate
  init, preflight, context-pack, checkpoint, starter spec/invariant/gate files

Pass 2 — workflow spec + basic renderer
  workflow.yaml + aiwk render claude-workflow
```

The current renderer emits workflows that are structurally too weak for the user’s robotics workflows. It renders a simple phase loop instead of the mature handwritten pattern.

Your mission is **Pass 2.5: mature Claude workflow renderer**.

Do not implement robotics features. Do not edit `~/dev/t_robotics` source code. Edit AIWK source under `~/dev/aiwk` and regenerate generated workflow artifacts under `~/dev/.aiwk`.

The target output is that AIWK can render Claude Workflow JS files that are meaningfully comparable to the user’s mature handwritten workflows.

## Why the current renderer is insufficient

The current generated workflow is roughly:

```js
for (const step of steps) {
  for (const phase of step.phases) {
    await agent({ model, effort, prompt, schema });
  }
}
```

That is too primitive. It has no bounded repair loops, no reviewer retry loop, weak role semantics, and poor operational affordances.

The mature handwritten workflow style has:

```text
Scope Writer
  → Developer
  → Red Team
      if failures: route findings back to Developer, bounded retries
  → Reviewer
      if rejected: route findings back to Developer fix pass, bounded retries
  → Commit
      only after accepted review
```

A recent handwritten workflow, `p3s_adapter_socket_integration_workflow.js`, is the reference shape. It includes:

```text
- MAX_DEV_RED_CYCLES
- MAX_REVIEW_ATTEMPTS
- role-specific schemas
- agentOptions(...)
- Scoping Test Writer
- Developer cycles
- Adversarial Red Team cycles
- Code Reviewer attempts
- Developer fix pass for review findings
- safe commit agent
- fromStep recovery support
- Beads context injection
```

AIWK should render workflows with that architecture.

## Overall implementation strategy

Work in phases. For each phase:

1. Make a small focused change.
2. Run the phase smoke test.
3. If it fails, fix and rerun.
4. Try at most 2–3 times.
5. If you cannot make the smoke test pass after 2–3 serious attempts, stop and report:
   - what you changed;
   - exact failing command/output;
   - what you think is wrong;
   - what decision/help you need from the user.

Do not keep thrashing indefinitely.

Keep context focused. After each phase, write a short handoff note in your response or in an AIWK dev note file if appropriate:

```text
Phase:
Files changed:
Smoke tests run:
Pass/fail:
Remaining issue:
```

## Context-bloat discipline

Codex is good at multi-file editing, but this task can bloat quickly. Use these rules:

```text
- Read AIWK renderer source and tests first; avoid broad repeated repo scans.
- Do not reread all generated workflows after every small edit; inspect targeted output.
- Keep one implementation phase in mind at a time.
- Prefer grep/ripgrep for exact symbols over opening many files.
- Use small tests that assert generated output contains required structural markers.
- Do not implement broad roadmap items beyond the current phase.
- Do not edit t_robotics source.
- Do not try to solve robotics architecture; just preserve supplied workflow semantics in AIWK output.
```

If you get lost, stop and summarize rather than continuing.

## Runtime compatibility warning

Check the existing handwritten Claude Workflow runtime style before assuming the generated JS API. The known-good style appears to use:

```js
await agent(prompt, agentOptions(...))
```

not necessarily:

```js
await agent({ model, effort, prompt, schema })
```

If AIWK currently renders the object-form call, verify whether the runner supports it. If not, update the renderer to emit the known-good `agent(prompt, options)` style.

## Required workflow args / affordances

Generated workflows must preserve:

```text
stage
fromStep
onlyStep
preflightSummary
handoffPath
beadsSnapshot
```

Meanings:

```text
stage:
  Select workflow stage, usually "build".

fromStep:
  Resume from a specific step, skipping earlier accepted steps.

onlyStep:
  Run exactly one step.

preflightSummary:
  Compact deterministic preflight JSON/text supplied by operator.

handoffPath:
  Path to a durable handoff file or extra context file.

beadsSnapshot:
  Compact Beads state supplied by operator.
```

## Generated workflow architecture target

Generated JS should include, at minimum:

```text
normalizeWorkflowArgs(...)
STAGE
ONLY_STEP
BEADS_LEDGER_SNAPSHOT
PREFLIGHT_SUMMARY
HANDOFF_PATH
CONTEXT
withBeadsContext(...)
agentOptions(...)
schemas:
  SCOPE_SCHEMA
  IMPL_SCHEMA
  RED_SCHEMA
  REVIEW_SCHEMA
buildReviewerPrompt(...)
ALL_STEPS or equivalent generated from workflow.yaml
fromStep handling
onlyStep handling
MAX_DEV_RED_CYCLES = 2
MAX_REVIEW_ATTEMPTS = 2
Scope Writer
Dev / Red Team retry loop
Reviewer / Dev fix retry loop
safe commit agent
structured return:
  { halted_at, reason, stage, results }
```

## Role semantics to render

### Scope Writer

Must say:

```text
Write BLACK BOX tests/spec artifacts ONLY.
No implementation code.
Strictly follow the step scope.
```

### Developer

Must say:

```text
Implement only this sub-step.
Pass the Scoping Tests.
Respect invariants and out-of-scope boundaries.
If Red Team or Reviewer findings are supplied, address exactly those findings.
```

### Red Team

Must say:

```text
You are the Red Team.
Read the Developer implementation.
Write adversarial WHITE BOX tests/spec checks designed to break it.
Run relevant deterministic tests.
Do not silently patch implementation.
Report failures in structured form.
```

### Reviewer

Must say:

```text
You are an adversarial Code Reviewer.
Verify scope, invariants, build/tests, and task boundaries.
Reject broad/fragile changes.
Reject stale assumptions.
```

### Commit Agent

Must say:

```text
Commit only after accepted review.
Never use git add -A.
Never use git add .
Never use git commit -a.
Stage explicit paths only.
Never stage generated workflow script itself unless explicitly in scope.
Never stage build artifacts, logs, transcripts, or unrelated files.
Run git status --short before and after staging.
```

## Schemas to emit

Generated workflows should emit/define schemas comparable to:

```text
SCOPE_SCHEMA:
  status: done | blocked | needs_decision
  summary
  test_files_written
  scope_ok
  beads_notes
  handoff
  notes

IMPL_SCHEMA:
  status: done | blocked | scope_violation | needs_decision | invalid_test
  summary
  files_changed
  tests_added
  scope_ok
  self_build_passed
  beads_issues_opened
  beads_issues_closed
  beads_memory_written
  handoff
  notes

RED_SCHEMA:
  status: all_passed | failures_found | blocked | needs_decision
  summary
  adversarial_tests_written
  tests_passed
  failures_found: [{ test_name, detail }]
  beads_notes
  handoff
  notes

REVIEW_SCHEMA:
  accepted
  build_passed
  gtests_passed
  scope_clean
  findings: [{ severity, detail }]
  beads_notes
  verdict_reason
  handoff
```

The exact schema implementation can vary, but these control fields must exist so the JS can route retries.

---

# Phase Plan for claude

## Phase 0 — Audit current renderer and add characterization tests

### Full prompt for yourself

Inspect AIWK’s current Claude workflow renderer and its tests. Identify where `workflow.yaml` is parsed and where the JS template is emitted. Add failing characterization tests for the mature workflow structure before changing behavior.

Do not modify robotics source. Do not regenerate all workflows yet unless needed for inspection.

### Required smoke tests

Run:

```bash
cd ~/dev/aiwk
~/dev/aiwk/.venv/bin/python -m pytest -q
```

Then add/adjust tests so this command checks renderer output contains mature markers. At minimum, tests should assert rendered JS contains:

```text
MAX_DEV_RED_CYCLES
MAX_REVIEW_ATTEMPTS
SCOPING TEST WRITER
ADVERSARIAL RED TEAM
DEVELOPER FIX PASS
Code Reviewer
commitAgentPrompt
fromStep
onlyStep
beadsSnapshot
preflightSummary
handoffPath
NEVER use git add -A
```

After adding tests, run:

```bash
cd ~/dev/aiwk
~/dev/aiwk/.venv/bin/python -m pytest -q
```

It is acceptable for the new tests to fail before implementation. Record the failure clearly.

### Stop rule

If you cannot find the renderer or test harness within 2–3 attempts, stop and report.

---

## Phase 1 — Emit mature control-flow skeleton

### Full prompt for yourself

Update the Claude workflow renderer so generated JS uses the mature control-flow skeleton:

```text
Scope Writer
  → Developer
  → Red Team
      failures route back to Developer up to MAX_DEV_RED_CYCLES
  → Reviewer
      rejection routes back to Developer fix pass up to MAX_REVIEW_ATTEMPTS
  → Commit
```

Use structured outputs to control routing. Preserve `stage`, `fromStep`, and add/ensure `onlyStep`.

Make the smallest renderer changes needed to pass the structural tests from Phase 0.

### Required smoke tests

Run:

```bash
cd ~/dev/aiwk
~/dev/aiwk/.venv/bin/python -m pytest -q
```

Then render one workflow:

```bash
~/dev/aiwk/.venv/bin/aiwk render claude-workflow \
  --config ~/dev/.aiwk/handoff_refactor_dataloop/aiwk.yaml
```

Inspect generated output:

```bash
grep -E "MAX_DEV_RED_CYCLES|MAX_REVIEW_ATTEMPTS|SCOPING TEST WRITER|ADVERSARIAL RED TEAM|DEVELOPER FIX PASS|Code Reviewer|commitAgentPrompt|onlyStep|fromStep" \
  ~/dev/.aiwk/handoff_refactor_dataloop/generated/*.js
```

Expected: all markers present.

Also run JS syntax check if Node is available:

```bash
node --check ~/dev/.aiwk/handoff_refactor_dataloop/generated/*.js
```

### Stop rule

If tests pass but generated JS clearly lacks retry routing, stop and report instead of pretending it is done.

---

## Phase 2 — Add role-specific prompt rendering and schemas

### Full prompt for yourself

Upgrade the renderer/template so generated workflows include role-specific prompts and schemas:

```text
SCOPE_SCHEMA
IMPL_SCHEMA
RED_SCHEMA
REVIEW_SCHEMA
agentOptions(...)
adaptiveThinking()
disabledThinking()
role-specific instructions
```

The generated prompt text should distinguish Scope, Dev, Red Team, Reviewer, and Commit roles. It should route Red Team findings and Reviewer findings back into Developer prompts.

### Required smoke tests

Run:

```bash
cd ~/dev/aiwk
~/dev/aiwk/.venv/bin/python -m pytest -q
```

Render:

```bash
~/dev/aiwk/.venv/bin/aiwk render claude-workflow \
  --config ~/dev/.aiwk/adapter_socket_integration_wou/aiwk.yaml
```

Smoke grep:

```bash
grep -E "SCOPE_SCHEMA|IMPL_SCHEMA|RED_SCHEMA|REVIEW_SCHEMA|agentOptions|adaptiveThinking|disabledThinking|The Red Team found these failures|Address exactly these Code Reviewer findings|schema:" \
  ~/dev/.aiwk/adapter_socket_integration_wou/generated/*.js
```

Expected: all markers present.

Syntax check:

```bash
node --check ~/dev/.aiwk/adapter_socket_integration_wou/generated/*.js
```

### Stop rule

If the workflow renders but schemas are not connected to agent calls, stop and report.

---

## Phase 3 — Inject durable AIWK context and workflow affordances

### Full prompt for yourself

Generated workflows must use durable AIWK files as source-of-truth. Add render-time injection or clear runtime references to:

```text
spec/project.spec.md
spec/invariants.yaml
spec/gates.yaml
state/
```

Also ensure generated workflows accept and include:

```text
preflightSummary
handoffPath
beadsSnapshot
```

The renderer should not stuff everything blindly if files are huge, but for current AIWK projects, inlining spec/invariants/gates into `CONTEXT` is acceptable.

### Required smoke tests

Run:

```bash
cd ~/dev/aiwk
~/dev/aiwk/.venv/bin/python -m pytest -q
```

Render all four workflows:

```bash
for cfg in ~/dev/.aiwk/*/aiwk.yaml; do
  ~/dev/aiwk/.venv/bin/aiwk render claude-workflow --config "$cfg"
done
```

Smoke grep each generated JS:

```bash
for js in ~/dev/.aiwk/*/generated/*.js; do
  echo "== $js =="
  grep -E "project.spec.md|invariants.yaml|gates.yaml|preflightSummary|handoffPath|beadsSnapshot|ACTIVE BEADS" "$js"
  node --check "$js"
done
```

Expected: each generated workflow has context markers and passes syntax.

### Stop rule

If inlining spec files becomes messy or breaks JS escaping, stop and report with the failing generated snippet. Do not hack around by removing context.

---

## Phase 4 — Safe commit behavior and AIWK venv/script discipline

### Full prompt for yourself

Ensure generated workflows include safe commit-agent prompts and do not rely on system Python wrappers.

Commit prompts must forbid:

```text
git add -A
git add .
git commit -a
```

They must require explicit-path staging and `git status --short`.

If AIWK generated helper scripts call `python -m aiwk`, either:
1. update them to use a configurable Python path, or
2. document/emit venv activation requirements clearly.

For this environment, explicit venv path is preferred:

```text
/home/varunkamat/dev/aiwk/.venv/bin/python -m aiwk
```

### Required smoke tests

Run:

```bash
cd ~/dev/aiwk
~/dev/aiwk/.venv/bin/python -m pytest -q
```

Render all workflows:

```bash
for cfg in ~/dev/.aiwk/*/aiwk.yaml; do
  ~/dev/aiwk/.venv/bin/aiwk render claude-workflow --config "$cfg"
done
```

Check safe commit markers:

```bash
for js in ~/dev/.aiwk/*/generated/*.js; do
  echo "== $js =="
  grep -E "NEVER use git add -A|NEVER use git add \.|NEVER use git commit -a|git status --short|explicit paths" "$js"
done
```

Check generated scripts if AIWK emits them:

```bash
grep -R "python -m aiwk" ~/dev/.aiwk || true
grep -R "/home/varunkamat/dev/aiwk/.venv/bin" ~/dev/.aiwk || true
```

If `python -m aiwk` remains in wrappers, explain whether this is acceptable because the venv is expected to be active, or patch it if the project supports a configurable Python path.

### Stop rule

If changing wrapper generation cascades beyond the renderer and risks breaking init/preflight/checkpoint, stop and ask before broad refactoring.

---

## Phase 5 — Regenerate four robotics workflows and compare against target semantics

### Full prompt for yourself

Regenerate all four robotics workflows and inspect whether they preserve the intended task boundaries.

Projects:

```text
~/dev/.aiwk/handoff_refactor_dataloop
~/dev/.aiwk/integration_refactor_after_handshake
~/dev/.aiwk/adapter_socket_integration_wou
~/dev/.aiwk/echo_910_911_912_7nq
```

Key boundaries:

### handoff_refactor_dataloop

Must include:

```text
- data loop calls sm.tick(dispatcher_state)
- tick drains queued request_to_write
- GoalExecutor remains
- HandshakeExecutor polling disappears
- no socket adapter integration
- no 910/911/912
- no RPC_RETURN
```

### integration_refactor_after_handshake

Must include:

```text
- update E2E tests/specs after handshake refactor
- keep /execute_procedure boundary
- keep read-only RTDE control-plane probe
- remove stale executor/HandshakeExecutor assumptions
- no params-valid bit
- no register payload fallback
```

### adapter_socket_integration_wou

Must include the new seam:

```text
GoalExecutor / set_request
  → queued request
  → data-loop tick
  → TickResult::request_to_write
  → DataPlaneTcpSession::transfer_parameters
  → write rpc_id only after success
```

Must include:

```text
- failed socket transfer prevents rpc_id trigger
- failed socket transfer cannot leave goal waiting forever
- no 910/911/912 dispatcher wiring
- no RPC_RETURN
- no register fallback
```

### echo_910_911_912_7nq

Must include:

```text
- only after wou
- wire 910/911/912
- flip assertNotIn to assertIn
- validate with live SS3, not just grep
- no register fallback
- no RPC_RETURN
```

### Required smoke tests

Render all:

```bash
for cfg in ~/dev/.aiwk/*/aiwk.yaml; do
  ~/dev/aiwk/.venv/bin/aiwk render claude-workflow --config "$cfg"
done
```

Syntax check all:

```bash
for js in ~/dev/.aiwk/*/generated/*.js; do
  node --check "$js"
done
```

Task-boundary greps:

```bash
grep -R "HandshakeExecutor.*poll\|executor.execute.*make_dispatcher_interface" ~/dev/.aiwk/*/generated/*.js || true
grep -R "910/911/912" ~/dev/.aiwk/adapter_socket_integration_wou/generated/*.js || true
grep -R "RPC_RETURN" ~/dev/.aiwk/*/generated/*.js || true
grep -R "params-valid\|payload registers\|register fallback" ~/dev/.aiwk/*/generated/*.js || true
```

Interpretation:

- Some negative terms may appear in “do not” sections. That is okay.
- But `adapter_socket_integration_wou` must not instruct agents to actually wire 910/911/912.
- No workflow should instruct agents to implement RPC_RETURN.
- No workflow should preserve the old executor/make_dispatcher_interface seam as the post-refactor stable architecture.

### Stop rule

If generated workflows still look thin compared to the handwritten reference after 2–3 passes, stop and report. Do not keep expanding scope into the whole Roadmap A.

---

## Final report format

When done, report:

```text
AIWK source files changed:
Tests added/changed:
Commands run:
Smoke tests passed:
Generated workflow files updated:
Remaining limitations:
Recommended next human QA:
```

Do not claim success unless generated JS has the mature retry-loop architecture and passes syntax checks.
