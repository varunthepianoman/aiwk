# Pass 4.1 Prompt: Final Clean-Status Enforcement and Runtime Validation

You are working in the existing AIWK repository at:

```text
~/dev/aiwk
```

This is **Pass 4.1: Final Clean-Status Enforcement and Runtime Validation**.

## Context

AIWK now has:

```text
Pass 1.0 — durable substrate ✅
Pass 2.0 — workflow.yaml + Claude workflow renderer ✅
Pass 2.5/2.6 — mature runtime-compatible Claude workflow renderer ✅
Pass 3.0 — Objective Gate DSL ✅
Pass 3.1 — gate-run evidence/logs ✅
Pass 4.0 — commit policy simplification ✅
```

Pass 4.0 introduced commit modes, especially:

```text
commit_mode: mechanical_all
```

`mechanical_all` uses a tiny low-effort Sonnet commit agent to run:

```bash
git status --short
git add -A
git commit -m "<message>"
git status --short
git rev-parse HEAD
```

This pass closes the loop: after commit, generated workflows should verify the final repo state and make runtime validation decisive.

## Goal

Add final clean-status enforcement after commit, and update the runtime validation workflow so a successful run proves:

```text
workflow accepted by Claude runtime
onlyStep respected
objective gate ran
review accepted
commit phase ran
expected files committed
final git status is clean
structured result is all_steps_accepted
```

## Important constraints

- Edit AIWK source under `~/dev/aiwk`.
- Do not edit `~/dev/t_robotics` source.
- Do not hand-patch generated JS except by regenerating from AIWK.
- Do not implement Beads integration.
- Do not implement templates.
- Do not implement timeout/evidence hash work.
- Preserve objective gate behavior.
- Preserve commit policy behavior.
- Preserve runtime-compatible generated JS:
  - `meta.name` present
  - no `export default`
  - no `process.env`
  - no `permissionMode`
  - no `env:`
  - Node syntax valid

## Feature 1: post-commit status enforcement

Generated workflows should compute/require final commit cleanliness when commit mode is active.

Add a small post-commit status check.

Because workflow JS cannot run shell directly, this should be done by the commit agent itself or by a tiny low-effort status-check agent.

Preferred: keep it inside the mechanical commit agent to avoid another subagent.

Commit agent prompt for `mechanical_all` should run:

```bash
cd <repo>
status_before=$(git status --short)
git add -A
git commit -m "<commit_message>"
commit_rc=$?
status_after=$(git status --short)
head_after=$(git rev-parse HEAD)
printf ...
```

The agent should return structured `COMMIT_SCHEMA`.

Extend `COMMIT_SCHEMA` if needed:

```text
status: committed | nothing_to_commit | failed | skipped
summary
commit_hash
commit_rc
status_before
status_after
clean_after
notes
```

Generated workflow should enforce:

```js
const commitClean = commitResult && (
  commitResult.status === "committed" ||
  commitResult.status === "nothing_to_commit" ||
  commitResult.status === "skipped"
) && commitResult.clean_after !== false;
```

For `commit_mode: mechanical_all`, if `clean_after` is false or `status_after` is non-empty, return:

```text
halted_at: "<step_id>:commit"
reason: "commit_left_dirty_tree"
```

If commit failed, return:

```text
halted_at: "<step_id>:commit"
reason: "commit_failed"
```

For `commit_mode: none`, do not require clean-after by default. It is expected that no commit was performed.

## Feature 2: runtime validation target cleanup/support

Update the disposable runtime validation setup/config if needed.

The desired runtime validation behavior:

```text
- reset target before run
- generated workflow runs RUNTIME_SS0
- dev creates runtime_marker.txt
- red team may create a test artifact
- objective gate passes
- reviewer accepts pre-commit in-scope dirty files
- commit mode mechanical_all stages everything
- final git status is clean
- commit hash returned
```

If the runtime validation target has pycache/logs that should not be committed, ensure they are ignored in the disposable target with `.gitignore`, or ensure the generated process cleans them. Do not overfit core AIWK to pycache; fix the disposable test project if needed.

Suggested disposable `.gitignore`:

```gitignore
__pycache__/
*.pyc
```

If `tests/test_runtime_marker_redteam.py` is an intended artifact, it should be committed by `git add -A`.

## Feature 3: result shape

Per-step result should include commit result:

```js
results.push({
  step: step.id,
  accepted,
  impl: lastImpl,
  review: lastReview,
  gate: lastGate,
  commit: commitResult
});
```

Final all-accepted result should only happen if commit is clean or commit mode is `none`.

## Tests to add/update

### 1. Renderer tests

Generated JS should contain:

```text
clean_after
commit_rc
commit_left_dirty_tree
commit_failed
status_after
commitResult
```

For `mechanical_all`, generated JS should enforce clean-after.

For `commit_mode: none`, generated JS should not halt merely because no commit was performed.

### 2. Schema tests

`COMMIT_SCHEMA` should include:

```text
commit_rc
clean_after
status_after
```

### 3. Runtime compatibility tests

Generated JS must still:

```text
include meta.name
not include export default
not include process.env
not include permissionMode
not include env:
preserve objective gate wiring
preserve mature markers
```

### 4. Disposable runtime validation config

Ensure the generated runtime validation workflow uses:

```yaml
commit:
  mode: mechanical_all
```

Ensure disposable target ignores generated Python caches if needed.

## Commands to run

Run tests:

```bash
cd ~/dev/aiwk
~/dev/aiwk/.venv/bin/python -m pytest -q
```

Regenerate all workflows:

```bash
for cfg in ~/dev/.aiwk/*/aiwk.yaml; do
  ~/dev/aiwk/.venv/bin/aiwk render claude-workflow --config "$cfg"
done
```

Syntax check generated workflows:

```bash
for js in ~/dev/.aiwk/*/generated/*.js; do
  echo "== $js =="
  node --check "$js"
done
```

If `node` is not on PATH but VS Code bundled Node is available, use that and report the path.

## Runtime validation instructions to report

Before running runtime validation, reset the disposable target:

```bash
cd ~/dev/aiwk_runtime_validation_target
git reset --hard HEAD
git clean -fdx
git status --short
```

Then run the generated workflow request:

```json
{
  "scriptPath": "/home/varunkamat/dev/.aiwk/aiwk_runtime_validation/generated/aiwk_runtime_validation.claude_workflow.js",
  "args": {
    "stage": "build",
    "onlyStep": "RUNTIME_SS0",
    "preflightSummary": "Use /home/varunkamat/dev/.aiwk/aiwk_runtime_validation/state/runtime_preflight.json. This is a disposable runtime validation; do not run broad repo discovery unless needed.",
    "handoffPath": "/home/varunkamat/dev/.aiwk/aiwk_runtime_validation/state/runtime_operator_handoff.md",
    "beadsSnapshot": "Runtime validation only. No Beads required. Target repo is disposable at /home/varunkamat/dev/aiwk_runtime_validation_target."
  }
}
```

After runtime validation, the user should verify:

```bash
cd ~/dev/aiwk_runtime_validation_target
git status --short
git log --oneline -5
cat runtime_marker.txt
```

Expected:

```text
git status --short is empty
runtime_marker.txt exists
runtime_marker.txt content is AIWK_RUNTIME_VALIDATED\n
new commit exists
workflow result reason is all_steps_accepted
```

Do not claim runtime success. The user will run it.

## Stop rules

Stop and report if:

- Final clean-status enforcement requires direct shell execution from workflow JS.
- Runtime-compatible JS constraints are violated.
- Commit policy behavior from Pass 4.0 breaks.
- Tests fail after 2–3 serious fix attempts.

## Final report format

Report exactly:

```text
AIWK source files changed:
Tests added/changed:
Commit clean-status behavior:
Workflow.yaml/config changes:
Generated workflow files updated:
Commands run:
Test results:
Node syntax results:
Runtime validation request to run next:
Post-runtime verification commands:
Remaining limitations:
Recommended next pass:
```
