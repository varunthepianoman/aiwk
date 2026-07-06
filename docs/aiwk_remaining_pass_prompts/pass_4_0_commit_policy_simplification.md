# Pass 4.0 Prompt: Commit Policy Simplification

You are working in the existing AIWK repository at:

```text
~/dev/aiwk
```

This is **Pass 4.0: Commit Policy Simplification**.

## Context

AIWK now has:

```text
Pass 1.0 — durable substrate ✅
Pass 2.0 — workflow.yaml + Claude workflow renderer ✅
Pass 2.5/2.6 — mature runtime-compatible Claude Workflow renderer ✅
Pass 3.0 — Objective Gate DSL + enforced reviewer/gate separation ✅
Pass 3.1 — gate-run evidence/logs ✅
```

Pass 3.1 made objective gates much more trustworthy:

```text
- generated workflows call one deterministic `aiwk gate-run` command
- gate-run writes durable evidence JSON
- gate-run writes full logs
- generated workflows enforce rc/count thresholds
```

The next problem is commit behavior.

The current “smart safe commit agent” is overbuilt. It spends tokens trying to infer and stage exact paths from agent-reported schema fields. In runtime validation, this already caused a bad failure mode: the Red Team created a useful file, but because it reported a test-name description instead of a path, the commit agent did not stage it.

For AIWK-generated workflows, commit should be dumb and mechanical. The intelligence should live before commit:

```text
preflight clean before launch
objective gate passes
reviewer rejects unrelated dirty files before commit
then commit mechanically
```

## Goal

Add configurable commit policy support:

```text
commit_mode: none | mechanical_all | mechanical_paths
```

The primary target for this pass is:

```text
commit_mode: mechanical_all
```

`mechanical_all` should use a tiny low-effort Sonnet commit agent that runs:

```bash
cd <repo>
git status --short
git add -A
git commit -m "<commit_message>"
git status --short
git rev-parse HEAD
```

No architecture reasoning. No path inference. No smart staging.

## Important constraints

- Edit AIWK source under `~/dev/aiwk`.
- Do not edit `~/dev/t_robotics` source.
- Do not hand-patch generated JS except by regenerating from AIWK.
- Do not implement Beads integration.
- Do not implement templates.
- Do not implement token accounting.
- Do not implement timeout/evidence hash work from Pass 3.2.
- Preserve objective gate behavior from Pass 3/3.1.
- Preserve runtime-compatible generated JS:
  - `meta.name` present
  - no `export default`
  - no `process.env`
  - no `permissionMode`
  - no `env:`
  - Node syntax valid
- Preserve backward compatibility for existing workflow specs.

## Workflow config shape

Add commit policy support to `workflow.yaml`.

Suggested top-level shape:

```yaml
commit:
  mode: mechanical_all
  message_template: "{step_id}: {step_title}"
  agent:
    model: sonnet
    effort: low
```

Also allow per-step override:

```yaml
stages:
  build:
    steps:
      - id: DEMO_SS0
        title: Demo step
        commit:
          mode: mechanical_all
          message_template: "{step_id}: {step_title}"
```

Supported modes:

```text
none
  - Do not run a commit phase.
  - Return a structured result indicating commit skipped.

mechanical_all
  - Run tiny commit agent.
  - Use git add -A.
  - Commit with rendered message.

mechanical_paths
  - Keep existing explicit-path behavior if it already exists.
  - If not easy to preserve cleanly, implement as documented future work and fail clearly if selected.
```

Recommended default for initialized new projects:

```yaml
commit:
  mode: mechanical_all
  message_template: "{step_id}: {step_title}"
  agent:
    model: sonnet
    effort: low
```

If you are concerned about safety, make the default explicit in generated starter `workflow.yaml` rather than hidden.

## Parser/validation requirements

Extend workflow spec parsing:

- Parse top-level `commit`.
- Parse per-step `commit`.
- Step-level commit config overrides top-level commit config.
- Validate `mode` is one of:
  - `none`
  - `mechanical_all`
  - `mechanical_paths`
- Validate `message_template` is a string if present.
- Validate agent model/effort if present using existing model/effort validation patterns.
- Unknown commit mode should fail clearly.

Message template variables:

Support at least:

```text
{step_id}
{step_title}
{project}
```

Optional:

```text
{stage}
```

If an unknown template variable is used, fail clearly during render.

## Generated JS requirements

Replace the over-smart commit prompt with a small commit policy mechanism.

Generated JS should include:

```text
COMMIT_SCHEMA
commitAgentPrompt
commitPolicyForStep
renderCommitMessage
```

For `mechanical_all`, `commitAgentPrompt` should be short and deterministic:

```text
You are the mechanical commit runner.

Run exactly:

cd <repo>
git status --short
git add -A
git commit -m "<commit_message>"
git status --short
git rev-parse HEAD

Do not inspect architecture.
Do not review code.
Do not edit files.
Do not choose paths.
If git commit says nothing to commit, report that exactly.
Return the final status and commit hash if a commit was created.
```

The commit agent should use:

```text
model: sonnet
effort: low
schema: COMMIT_SCHEMA
```

`COMMIT_SCHEMA` should include at least:

```text
status: committed | nothing_to_commit | failed | skipped
summary
commit_hash
status_before
status_after
notes
```

For `commit_mode: none`:

- Do not launch a commit agent.
- Return a commit result:

```json
{
  "status": "skipped",
  "summary": "commit_mode none",
  "commit_hash": null
}
```

For `mechanical_paths`:

- Preserve existing behavior if already implemented.
- Otherwise fail clearly at render time or runtime with a message that `mechanical_paths` is not implemented yet.

## Reviewer prompt update

Reviewer should still run before commit and must continue to enforce pre-commit cleanliness discipline:

```text
This review runs before the Commit phase.
Expected in-scope changes may be modified or untracked at review time.
Do not reject solely because expected in-scope files are modified or untracked.
Reject unrelated dirty files, generated workflow artifacts, logs, build outputs, transcripts, or scope creep.
The Commit phase is responsible for mechanical staging, committing, and final status reporting.
```

For `mechanical_all`, reviewer should explicitly understand:

```text
The Commit phase will run git add -A, so reject unrelated dirty files before accepting.
```

## Runtime validation project update

Update the disposable runtime validation project if it exists:

```text
~/dev/.aiwk/aiwk_runtime_validation/workflow.yaml
```

Set:

```yaml
commit:
  mode: mechanical_all
  message_template: "{step_id}: {step_title}"
  agent:
    model: sonnet
    effort: low
```

The runtime validation should commit both the marker and any Red Team test artifacts that remain in the disposable target, because `git add -A` is expected.

Do not touch production repositories.

## Tests to add/update

### 1. Parser tests

Add tests for:

- top-level `commit.mode: mechanical_all`
- top-level `commit.mode: none`
- per-step commit override
- unknown commit mode fails clearly
- invalid message_template type fails clearly
- unknown template variable fails clearly

### 2. Renderer tests

Generated JS with `mechanical_all` contains:

```text
COMMIT_SCHEMA
commitAgentPrompt
mechanical commit runner
git add -A
git commit -m
git rev-parse HEAD
model: "sonnet" or equivalent runtime-compatible model setting
effort: "low"
```

Generated JS with `commit_mode: none`:

```text
does not call commit agent
contains status skipped / commit_mode none
```

Generated JS should no longer contain the long explicit-path commit prompt by default:

```text
NEVER use git add -A
git ls-files --error-unmatch
Only if tracked, stage it explicitly
```

Those may remain only if `mechanical_paths` mode is selected.

### 3. Runtime compatibility tests

Generated JS must still:

```text
include meta.name
not include export default
not include process.env
not include permissionMode
not include env:
preserve onlyStep/fromStep/preflightSummary/handoffPath/beadsSnapshot
preserve objective gate wiring
preserve mature markers:
  MAX_DEV_RED_CYCLES
  MAX_REVIEW_ATTEMPTS
  SCOPING TEST WRITER
  ADVERSARIAL RED TEAM
  DEVELOPER FIX PASS
  Code Reviewer
```

### 4. Direct render tests

Render a workflow with `mechanical_all` and verify Node syntax if Node is available.

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

## Runtime validation request to report

After the patch, report the same runtime validation request:

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

Do not claim runtime success. The user will run Claude Workflow runtime validation.

## Stop rules

Stop and report if:

- Implementing commit policy requires a large renderer rewrite.
- Runtime-compatible JS constraints are violated.
- Objective gate behavior breaks.
- Tests fail after 2–3 serious fix attempts.
- You are tempted to add complex smart staging logic back into `mechanical_all`.

## Final report format

Report exactly:

```text
AIWK source files changed:
Tests added/changed:
Commit policy behavior:
Workflow.yaml/config changes:
Generated workflow files updated:
Commands run:
Test results:
Node syntax results:
Runtime validation request to run next:
Remaining limitations:
Recommended next pass:
```

Important:
Do not claim Claude runtime success. The user will run the generated Claude Workflow runtime validation.
