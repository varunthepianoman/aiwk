# Prompt for Codex: Upgrade AIWK Claude Workflow Renderer to Match Mature Handwritten Workflows

You are Codex developing AIWK itself. You are in a 3-folder VS Code workspace:

```text
~/dev/t_robotics   # robotics repo / target repo
~/dev/.aiwk        # AIWK workflow project folders
~/dev/aiwk         # AIWK tool source code
```

AIWK is installed in:

```text
~/dev/aiwk/.venv
```

Use explicit venv paths when running AIWK:

```bash
~/dev/aiwk/.venv/bin/aiwk --help
~/dev/aiwk/.venv/bin/python -m aiwk --help
```

Do not use system Python pip. Do not use `--break-system-packages`.

## Mission

AIWK Pass 1 and Pass 2 exist:

- Pass 1: durable substrate — `init`, `preflight`, `context-pack`, `checkpoint`, starter spec/invariant/gate files.
- Pass 2: `workflow.yaml` + basic `aiwk render claude-workflow`.

The current generated Claude workflow JS is too primitive for serious robotics workflows. Your job is to improve AIWK’s Claude workflow renderer so generated JS files preserve the core affordances of the user’s mature handwritten workflows.

This is effectively **Pass 2.5: mature Claude renderer**, before broad Pass 3 spec/gate/invariant automation.

Do not implement robotics features. Edit AIWK source and, if useful, regenerate the `.aiwk` project workflows. Do not edit `~/dev/t_robotics` source code unless explicitly instructed.

## Why this is needed

The generated workflow source YAML files under `~/dev/.aiwk/<project>/` are useful, but the rendered JS is too thin. It resembles a simple one-pass loop:

```js
for (const step of steps) {
  for (const phase of step.phases) {
    await agent({ model, effort, prompt, schema });
  }
}
```

That is not enough. It loses the mature structure from the handwritten workflow.

The known-good handwritten workflow style has these key features:

1. A Scoping Test Writer runs first and writes tests/specs only.
2. Developer runs after Scope.
3. Red Team runs after Developer and writes adversarial tests.
4. If Red Team finds failures, findings route back to Developer for up to N cycles.
5. Reviewer runs only after Red Team passes.
6. If Reviewer rejects, findings route back to Developer for up to N review-fix attempts.
7. Commit agent runs only after Reviewer accepts.
8. Each phase has role-specific model/effort/thinking/permissionMode/schema.
9. It supports `stage`, `fromStep`, and ideally `onlyStep`.
10. It injects durable project context such as `preflightSummary`, `handoffPath`, and `beadsSnapshot`.
11. It returns structured JSON with `halted_at`, `reason`, `stage`, and per-step results.
12. It enforces safe commit discipline and never uses `git add -A`.

A concrete example of the mature pattern appears in the user’s recent `/home/varunkamat/dev/t_robotics/z_workflows/p3s_socket_e2e_beads_workflow_v2.js`:

- It defines `MAX_DEV_RED_CYCLES` and `MAX_REVIEW_ATTEMPTS`.
- It runs `Scoping Test Writer` before implementation.
- It loops Dev → Red Team until Red Team passes or retries are exhausted.
- It loops Review → Dev fix pass until accepted or retries are exhausted.
- It commits only after accepted review.
- It has role-specific `agentOptions(...)` and schemas.
- It accumulates changed files from implementation, scope tests, and red-team tests.

Treat that workflow as the behavioral reference for renderer output.

## Current AIWK output problems to fix

### Problem 1: no retry loops

Generated JS should not stop permanently when Red Team finds a failure. It should route Red Team findings back to Developer for bounded retries.

Required behavior:

```text
Scope
  → Dev cycle 1
  → Red Team cycle 1
      if failures: Dev cycle 2 with red findings
      if pass: Reviewer
  → Reviewer attempt 1
      if rejected: Developer fix pass with reviewer findings
      if accepted: Commit
```

Use defaults:

```text
MAX_DEV_RED_CYCLES = 2
MAX_REVIEW_ATTEMPTS = 2
```

These should be configurable later, but hardcoded defaults are acceptable for the first renderer upgrade.

### Problem 2: weak role semantics

Generated JS must preserve role-specific semantics:

```text
scope:
  - writes black-box tests/specs only
  - no implementation code
  - typically sonnet/high/thinking disabled

dev:
  - implements only current sub-step
  - must satisfy scope tests
  - consumes red-team/reviewer findings when present
  - usually opus/high/adaptive thinking for hard robotics phases

red_team:
  - adversarial white-box reviewer/test writer
  - tries to break implementation
  - writes tests when appropriate
  - should not silently patch implementation

review:
  - adversarial code reviewer
  - confirms scope, tests, invariants, boundaries
  - rejects broad fragile changes

commit:
  - stages explicit paths only
  - no `git add -A`
  - no unrelated files
```

### Problem 3: renderer may use wrong Claude Workflow runtime API

Check the actual existing handwritten workflows and the current runner convention. The user’s known-good workflow uses the style:

```js
await agent(prompt, agentOptions(...))
```

not necessarily:

```js
await agent({ model, effort, prompt, schema })
```

Do not assume the object-style API works. Make the renderer compatible with the runner used by existing working workflows, or support a configurable runtime style.

### Problem 4: weak context integration

The rendered workflow must read/inject AIWK durable files, not just `workflow.yaml`.

At minimum, generated JS prompts should reference and/or include:

```text
spec/project.spec.md
spec/invariants.yaml
spec/gates.yaml
state/
```

If full file reading at runtime is not supported, the renderer should inline their text at render time or include a helper that shells/reads them if the workflow environment permits it.

The immediate goal is not a fully general Pass 3, but the generated prompt must at least say:

```text
Durable source-of-truth files:
- <project>/spec/project.spec.md
- <project>/spec/invariants.yaml
- <project>/spec/gates.yaml
```

and inject their content when reasonably possible.

### Problem 5: preserve core workflow args

Preserve these affordances:

```text
stage
fromStep
onlyStep
preflightSummary
handoffPath
beadsSnapshot
```

`stage` selects workflow stage.
`fromStep` resumes from a step.
`onlyStep` runs exactly one step.
`preflightSummary` injects compact deterministic preflight JSON.
`handoffPath` points to a durable handoff file to read/include/summarize.
`beadsSnapshot` injects current Beads state.

### Problem 6: generated wrappers use system Python

Generated AIWK helper scripts currently may call:

```bash
python -m aiwk
```

That will fail on this machine unless the venv is activated. Prefer explicit configurable Python path in scripts or document that wrappers require venv activation.

For this machine, use:

```bash
/home/varunkamat/dev/aiwk/.venv/bin/python -m aiwk
```

or:

```bash
/home/varunkamat/dev/aiwk/.venv/bin/aiwk
```

Do not rely on system Python.

### Problem 7: no safe commit discipline

Rendered workflows should include commit-agent prompts with explicit path staging only:

```text
- NEVER use git add -A
- NEVER use git add .
- NEVER use git commit -a
- stage only changed files reported by prior agents
- verify `git status --short`
- never stage workflow script itself unless explicitly in scope
- never stage build artifacts/logs/transcripts
```

### Problem 8: schemas too weak or generic

Add/standardize schemas like:

```text
SCOPE_SCHEMA:
  status, summary, test_files_written, scope_ok, notes, handoff

IMPL_SCHEMA:
  status, summary, files_changed, tests_added, scope_ok,
  self_build_passed, beads_issues_opened, beads_issues_closed,
  notes, handoff

RED_SCHEMA:
  status, summary, adversarial_tests_written, tests_passed,
  failures_found, notes, handoff

REVIEW_SCHEMA:
  accepted, build_passed, gtests_passed, scope_clean,
  findings, verdict_reason, notes, handoff
```

The exact field names can evolve, but generated workflows need structured outputs strong enough to drive retry decisions.

## Product-roadmap guidance

Do not jump straight to broad Pass 3/4/5. The immediate priority is:

```text
Pass 2.5 — mature Claude workflow renderer
```

This is aligned with the practical priority ladder:

```text
Priority 0 — preserve core workflow affordances
  stage/fromStep/onlyStep/preflightSummary/handoffPath/beadsSnapshot

Priority 1 — mandatory handoff summaries
  Every phase emits compact durable handoff text.

Priority 2 — read-discipline policy
  Stop agents from repeatedly rediscovering the repo.

Priority 3 — deterministic preflight/context-pack
  Use AIWK scripts to generate compact JSON and verbose logs.

Priority 4 — deterministic test runner summary
  Later.

Priority 5 — deterministic commit wrapper
  Later, but commit prompts should be safe now.

Priority 6 — audit/import
  Later.
```

So implement the renderer upgrade first. Do not attempt the entire long-term roadmap in one patch.

## Acceptance criteria for AIWK renderer upgrade

1. `aiwk render claude-workflow` produces JS with mature Scope → Dev/Red retry → Review retry → Commit architecture.
2. Generated JS supports `stage`, `fromStep`, `onlyStep`, `preflightSummary`, `handoffPath`, and `beadsSnapshot`.
3. Generated JS uses or can be configured to use the same `agent(prompt, options)` runtime style as existing handwritten workflows.
4. Generated prompts include project spec, invariants, and gates content or paths.
5. Generated prompts include role-specific instructions.
6. Generated workflows include structured schemas and use schema output to control flow.
7. Generated workflows halt clearly with structured reasons on scope failure, dev failure, red-team failure after retries, review rejection after retries, or unknown stage.
8. Generated workflows commit only after accepted review.
9. AIWK unit tests cover renderer output shape. At minimum, tests should assert the generated JS contains:
   - `MAX_DEV_RED_CYCLES`
   - `MAX_REVIEW_ATTEMPTS`
   - `SCOPING TEST WRITER`
   - `ADVERSARIAL RED TEAM`
   - `DEVELOPER FIX PASS`
   - `Code Reviewer`
   - `commitAgentPrompt`
   - `fromStep`
   - `onlyStep`
   - `beadsSnapshot`
   - safe staging language forbidding `git add -A`
10. Regenerate the four project workflows under `~/dev/.aiwk` and report what changed.

## Robotics-specific workflow content to preserve

When regenerating the four robotics workflows, preserve these boundaries.

### Workflow A: `handoff_refactor_dataloop`

Purpose: handshake redesign rewrite.

Key architecture:

```text
Goal thread:
  GoalExecutor::execute(...)
  snapshot()
  set_request(...)
  wait_for_change(...)

Data loop:
  read dispatcher_state
  sm.tick(dispatcher_state)
  if TickResult::request_to_write:
      adapter writes/commits request
```

Must preserve:

```text
- tick() is the only transition-rule call site.
- GoalExecutor remains.
- HandshakeExecutor disappears.
- No goal-thread dispatcher polling.
- No reusable state machine transport thread.
```

### Workflow B: `integration_refactor_after_handshake`

Purpose: update socket E2E integration tests/specs after handshake refactor.

Must preserve:

```text
- /execute_procedure action-client boundary
- read-only RTDE control-plane probe
- no register data-plane gates
- no params-valid bit
- no 910/911/912 wiring unless explicitly scoped
```

### Workflow C: `adapter_socket_integration_wou`

Purpose: live adapter socket integration for `t_robotics-wou`.

Must patch old seam:

```text
OLD / stale:
  executor.execute → URDriver::make_dispatcher_interface → transfer_parameters

NEW:
  GoalExecutor / set_request
  → queued request
  → data-loop tick
  → TickResult::request_to_write
  → DataPlaneTcpSession::transfer_parameters
  → write rpc_id only after success
```

Critical acceptance:

```text
If socket transfer fails before rpc_id write:
  - do not trigger rpc_id
  - do not let goal thread hang forever
  - surface clear failure
  - leave dispatcher READY / reset-safe
```

Do not wire 910/911/912 here.

### Workflow D: `echo_910_911_912_7nq`

Purpose: after `wou`, wire 910/911/912 echo handlers.

Must preserve:

```text
- only after wou lands
- flip pinned assertNotIn to assertIn
- validate with live SS3, not just grep
- no register fallback
- no RPC_RETURN
```

## Concrete first steps

1. Inspect current AIWK renderer source under `~/dev/aiwk`.
2. Inspect current generated files under `~/dev/.aiwk/*/generated/`.
3. Add renderer tests that characterize the desired mature output.
4. Upgrade renderer.
5. Run AIWK tests.
6. Regenerate the four workflows.
7. Report:
   - source files changed in AIWK;
   - tests added/updated;
   - generated workflow files updated;
   - where generated JS now matches mature handwritten architecture;
   - remaining limitations.

Do not edit `~/dev/t_robotics` source code.
