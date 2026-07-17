# AIWK User Guide

This guide walks through a complete AIWK project from installation to handoff. Commands assume:

```text
AIWK source/install:  ~/dev/aiwk
Target Git repository: ~/dev/my_repo
Workflow projects:     ~/dev/.aiwk
```

Adjust those paths for your environment.

## 1. Install AIWK

Create a dedicated virtual environment and install the repository in editable mode:

```bash
cd ~/dev/aiwk
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/aiwk --help
```

Avoid installing with a system-Python override such as `--break-system-packages`. AIWK-generated wrappers and rendered gate commands capture the interpreter used during initialization/rendering, so consistently use the intended virtual environment.

Convenience variable:

```bash
AIWK=~/dev/aiwk/.venv/bin/aiwk
```

## 2. Choose a template

```bash
$AIWK templates list
```

Templates currently shipped:

| Template | Use when |
| --- | --- |
| `generic` | You need a general Scope/Dev/Red/Review workflow. |
| `ros2_refactor` | You are refactoring ROS 2 C++ packages with `colcon` gates. |
| `bugfix_redteam` | You want reproduction and regression tests before a narrowly scoped fix. |

Templates deliberately contain placeholders and conservative starter commands. They are not ready-to-run project specifications.

The ROS 2 template follows the requested placeholder shape, including separate `source` commands. Because every gate command runs in its own shell, sourced environment state does not persist into later commands. Before serious use, combine sourcing and `colcon` in the same command or repeat the required source prefix in each build/test/result command.

## 3. Initialize a project

```bash
$AIWK init \
  --project my_refactor \
  --repo ~/dev/my_repo \
  --workflow-folder ~/dev/.aiwk \
  --template generic
```

Initialization creates `~/dev/.aiwk/my_refactor/` and does not initialize, stage, or commit anything in `~/dev/my_repo`.

The generated `aiwk.yaml` identifies the target repository and workflow folder. The generated shell wrappers contain absolute paths to this config and pin the current Python interpreter.

Initialization also creates `master_coordinator_prompt.md`, a generated launch runbook with exact project paths, commands, stage/step IDs, and context-collection instructions.

## 4. Edit the durable source of truth

Before rendering, edit these files.

### `spec/project.spec.md`

State:

- the concrete outcome;
- authoritative code, documents, protocols, or tests;
- explicit non-goals;
- workflow-specific sequencing or safety notes.

Write this for a cold-start reviewer. Avoid relying on conversation history.

### `spec/invariants.yaml`

Record properties every implementation and review must preserve. AIWK embeds the file as context but does not interpret its schema, so use a structure that is readable to humans and agents.

```yaml
invariants:
  - id: preserve_wire_format
    description: Existing serialized messages remain backward compatible.
  - id: deterministic_tests
    description: New behavior must have deterministic tests.
```

### `spec/gates.yaml`

Record semantic acceptance criteria. This file is reviewer context; executable checks belong in `workflow.yaml` objective gates.

```yaml
gates:
  - id: narrow_scope
    require:
      - only the named subsystem changes
    reject:
      - unrelated cleanup
```

### `workflow.yaml`

Define stages, steps, prompts, objective commands, commit policy, and optional advisory external-memory snapshot behavior. See the [workflow reference](workflow-reference.md) for every supported field.

At minimum, replace:

- TODO step titles and prompts;
- placeholder test/build commands;
- package names in specialized templates;
- broad goals with testable step boundaries.

## 5. Configure objective gates

Objective gates are the deterministic half of acceptance. The reviewer evaluates architecture and scope; the gate reports command results. Both must be green.

Good gate commands are:

- noninteractive;
- reproducible from the target-repo root;
- narrow enough to finish reliably;
- explicit about environment setup;
- safe to rerun after a Developer Fix Pass.

Example:

```yaml
objective_gates:
  default:
    enabled: true
    timeout_seconds: 300
    setup:
      commands:
        - python --version
    build:
      commands:
        - python -m py_compile src/service.py
    test:
      commands:
        - python -m unittest discover -s tests
    result:
      commands:
        - "true"
    checks:
      - name: no_debug_marker
        command: 'grep -R "DEBUG_ONLY" src tests'
        max_count: 0
```

Quote command values such as `"true"` so the limited YAML reader treats them as strings rather than booleans.

Gate command failures are evidence, not runner failures. If a build exits 7, `gate-run` normally exits zero after successfully capturing `build_rc:7` and `gate_clean:false`.

Use `setup` for checks or preparation with filesystem effects, not for shell-only environment state that a later command needs. Every listed command starts a new shell.

## 6. Choose a commit policy

For a clean, isolated worktree:

```yaml
commit:
  mode: mechanical_all
  message_template: "{step_id}: {step_title}"
  agent:
    model: sonnet
    effort: low
```

`mechanical_all` is intentionally simple. It runs `git add -A` only after objective gate and reviewer acceptance, then requires an empty `git status --short`. The reviewer prompt warns that unrelated dirty files must be rejected before this phase.

Use `none` when another process owns commits. Use `mechanical_paths` only when you specifically need the legacy explicit-path behavior and accept its reliance on agent-reported file paths.

## 7. Run preflight

```bash
CFG=~/dev/.aiwk/my_refactor/aiwk.yaml
$AIWK preflight --config "$CFG"
```

Example compact output:

```json
{"status":"ok","project":"my_refactor","repo":"/home/me/dev/my_repo","head":"...","branch":"main","dirty_relevant":false,"dirty_relevant_files":[],"log_path":"..."}
```

When `relevant_paths` is empty, all Git status paths are considered relevant. When it contains prefixes, only matching paths set `dirty_relevant`. Detailed status is written below the AIWK project’s `logs/` directory.

Preflight is observational: it does not clean, reset, stage, or commit the target repository.

## 8. Render the workflow

```bash
$AIWK render claude-workflow --config "$CFG"
```

Defaults:

- input: `<project-folder>/workflow.yaml`;
- output: `<project-folder>/generated/<project>.claude_workflow.js`.

Override either path when testing variants:

```bash
$AIWK render claude-workflow \
  --config "$CFG" \
  --workflow-spec /tmp/experimental-workflow.yaml \
  --out /tmp/experimental-workflow.js
```

Render validates references, phases, commands, timeouts, commit templates, and configuration types. It also embeds the current contents of project spec, invariants, and gates. Rerender whenever any durable input changes.

Every render refreshes `master_coordinator_prompt.md`. Do not put unique requirements or decisions in that file; move them to `workflow.yaml` or the appropriate durable spec first.

If Node is available, check syntax:

```bash
node --check ~/dev/.aiwk/my_refactor/generated/my_refactor.claude_workflow.js
```

## 9. Launch through Claude Workflow

AIWK generates the script but does not itself launch Claude. Supply the generated script to your Claude Workflow runtime.

The recommended entry point is the generated coordinator prompt:

```text
~/dev/.aiwk/my_refactor/master_coordinator_prompt.md
```

Give it to the coordinating operator/agent. It instructs the coordinator to rerender, run fresh preflight, verify prerequisite sections from durable evidence, create a prestart context pack, collect any explicitly configured advisory snapshot text, construct concrete arguments, launch the workflow, and report structured halts. The generated workflow—not the coordinator—owns role sequencing.

Supported runtime arguments:

```json
{
  "stage": "build",
  "onlyStep": "GENERIC_SS0",
  "startAtRole": null,
  "resumeCycle": 1,
  "resumeAttempt": 1,
  "preflightSummary": "Use the latest AIWK preflight JSON.",
  "handoffPath": "/home/me/dev/.aiwk/my_refactor/state/PREVIOUS_handoff.md",
  "gateEvidencePath": null,
  "resumeFindings": "",
  "beadsSnapshot": "Optional advisory external-memory snapshot when explicitly enabled"
}
```

Argument behavior:

- `stage`: selects a named stage, defaulting to `default_stage`.
- `onlyStep`: runs exactly one step within the selected stage.
- `fromStep`: skips earlier steps and resumes from the named step.
- `onlyStep` and `fromStep` are mutually exclusive.
- `startAtRole`: fresh-launch intra-step entry point. It requires `onlyStep` and durable evidence through `handoffPath` or `gateEvidencePath`; it does not resume old workflow runtime memory.
- `resumeCycle`: development/red-team cycle to use with `startAtRole: "dev"` or `"redteam"`.
- `resumeAttempt`: review/fix attempt to use with `startAtRole: "gate"`, `"review"`, or `"dev_fix"`.
- `gateEvidencePath`: optional prior objective-gate evidence path to seed context. A fresh gate still runs before review when the selected role requires it.
- `resumeFindings`: optional compact findings text for `dev`, `dev_fix`, or `review` entry.
- `preflightSummary`: operator-provided deterministic context.
- `handoffPath`: durable context the agents are instructed to read before editing.
- `beadsSnapshot`: backward-compatible argument name for optional advisory external-memory snapshot text. It is ignored unless snapshot mode is explicitly enabled.

Unknown stages or step IDs return a structured selection halt rather than silently running another step.

## 10. Understand one generated step

For the standard phase list, AIWK runs:

```text
Scope Writer
  ↓
optional Discovery Agent
  ↓
Developer ⇄ Adversarial Red Team  (maximum 2 Dev/Red cycles)
  ↓
Objective Build Gate
  ↓
Code Reviewer
  ↓ rejection or red gate
Developer Fix Pass → gate → reviewer  (maximum 2 review attempts total)
  ↓ accepted gate and review
Commit policy
  ↓
Final clean-status check
```

The workflow halts with structured `halted_at`, `reason`, `stage`, and `results` fields when a role blocks, retries are exhausted, the gate remains red, commit fails, or the commit leaves a dirty tree.

### Durable per-agent handoffs

Every generated non-gate/non-commit role is told to write a concrete handoff file before it returns:

```text
state/handoffs/<STEP>_<ROLE>_C<CYCLE>_<AGENT_ID>.md
```

The role also returns `handoff_path`, `files_changed`, `files_inspected`, `tests_run`, `gate_evidence_paths`, `known_dirty_paths`, and `next_agent_should_read` in structured output. The workflow threads prior handoff paths into downstream prompts, so later agents start from durable summaries instead of rediscovering the whole repository from scratch.

Use `handoffPath` in runtime args for an operator-created or previous-session handoff. Generated per-agent handoffs then accumulate inside the step result as `handoff_paths`.

### Discovery agents

Enable Discovery when a step crosses unfamiliar package boundaries, has many possible file targets, or would otherwise make Dev/Red Team/Review repeat broad search:

```yaml
discovery:
  enabled: true
  model: opus
  effort: high
```

Or only for one step:

```yaml
steps:
  - id: LARGE_SS1
    discovery:
      enabled: true
```

Discovery runs after Scope and before Developer. It should read supplied handoffs first, perform bounded repo discovery, write a compact repo-map handoff, and tell Developer what not to rediscover.

### Context economy

Configure continuation limits for explicit checkpoint outputs:

```yaml
context_economy:
  max_checkpoint_continuations: 1
```

Generated prompts tell agents to read supplied handoffs first, avoid repeated broad discovery, redirect long command output to logs, and return summaries/tails. They no longer tell agents to stop after a fixed tool-call count or major test milestone. If a role explicitly returns `status:"checkpoint"` anyway, the workflow reinvokes the same logical role/step with the checkpoint handoff and remaining work until completion or `max_checkpoint_continuations`.

## 11. Inspect objective evidence

Run the same gate outside Claude when debugging:

```bash
$AIWK gate-run \
  --config "$CFG" \
  --gate default \
  --step GENERIC_SS0 \
  --attempt 1
```

Evidence locations:

```text
state/gates/<step>_<gate>_attempt<attempt>_<timestamp>.json
logs/gates/<step>_<gate>_attempt<attempt>_<timestamp>.log
```

The JSON contains top-level section return codes, per-command timing and output tails, check counts, Git state before and after, and integrity hashes. The log contains complete captured stdout/stderr.

Timeout behavior:

- timeout is per command;
- section timeout overrides gate timeout;
- check timeout overrides gate timeout;
- default is 300 seconds;
- timed-out commands record return code 124 and later sections still run;
- setup timeout is recorded but does not alone make the gate red.

## 12. Pause, hand off, or resume

```bash
$AIWK context-pack \
  --config "$CFG" \
  --phase DEV_TO_REVIEW \
  --step GENERIC_SS0 \
  --include-diff \
  --max-diff-lines 80
```

Optional inputs:

```bash
--gate-evidence path/to/evidence.json
--beads-snapshot-file path/to/external_memory_snapshot.txt
```

The flag name is retained for compatibility. When supplied, context-pack records the file under `external_memory` / “Optional external memory snapshot,” not as live Beads state.

Without an explicit gate evidence path, `context-pack` uses the lexically latest JSON under `state/gates/` when available. It writes stable phase paths:

```text
state/DEV_TO_REVIEW_context.json
state/DEV_TO_REVIEW_handoff.md
```

Give the Markdown path to a resumed workflow through `handoffPath`. Source and committed specs remain authoritative if a handoff is stale or contradictory.

Generated role handoffs are separate from `context-pack`: `context-pack` is operator-driven, while `state/handoffs/` files are role-by-role runtime artifacts.

## 13. Generated wrappers

Each project includes:

```bash
scripts/preflight.sh
scripts/context_pack.sh PHASE_ID
scripts/checkpoint_commit.sh STEP_ID
```

They call the pinned Python interpreter and absolute project config. The context wrapper exposes the basic phase form; use the main CLI for rich context options.

The checkpoint wrapper invokes `aiwk checkpoint`, which stages every target-repo change and commits with the supplied step ID. It is not the same mechanism as the generated workflow’s commit policy.

## 14. Recovery patterns

### Resume after an accepted earlier step

Use `fromStep` so the workflow does not rerun prior steps:

```json
{"stage":"build","fromStep":"GENERIC_SS1","handoffPath":"..."}
```

### Continue after a checkpoint

Use the `checkpoint.handoff_path` returned by the halted workflow:

```json
{"stage":"build","onlyStep":"GENERIC_SS1","handoffPath":"/home/me/dev/.aiwk/my_refactor/state/handoffs/GENERIC_SS1_DEV_C1_dev_1.md"}
```

The continuation agent should read that handoff first, verify targeted files second, and avoid broad rediscovery unless the handoff is stale, contradicted, or insufficient.

### Relaunch inside one step at Red Team or Reviewer

Use `startAtRole` when prior durable handoffs prove that earlier roles in the step do not need to rerun. This starts a fresh workflow run at the chosen role; it does not recover old JavaScript variables or Claude runtime memory.

```json
{
  "stage": "build",
  "onlyStep": "GENERIC_SS1",
  "startAtRole": "redteam",
  "resumeCycle": 1,
  "handoffPath": "/home/me/dev/.aiwk/my_refactor/state/handoffs/GENERIC_SS1_DEV_C1_A0_K0_dev_1_k0.md",
  "preflightSummary": "..."
}
```

```json
{
  "stage": "build",
  "onlyStep": "GENERIC_SS1",
  "startAtRole": "review",
  "resumeAttempt": 1,
  "handoffPath": "/home/me/dev/.aiwk/my_refactor/state/handoffs/GENERIC_SS1_REDTEAM_C1_A0_K0_redteam_1_k0.md",
  "gateEvidencePath": "/home/me/dev/.aiwk/my_refactor/state/gates/latest.json",
  "preflightSummary": "..."
}
```

For `startAtRole: "review"`, AIWK skips Scope/Discovery/Dev/Red Team, seeds the reviewer with durable handoff context, runs a fresh objective gate when configured, then runs the reviewer. If gate/review fails, the normal Developer Fix → Gate → Review loop continues.

### Isolate one failing step

Use `onlyStep`, rerendering first if configuration changed:

```json
{"stage":"build","onlyStep":"GENERIC_SS1"}
```

### Investigate a red objective gate

Run `gate-run` manually, inspect its full log, and compare its evidence hash and Git snapshots. A reviewer cannot override a red build/test/check result.

### Commit left the tree dirty

Inspect `status_after` in the structured commit result. The workflow intentionally halts with `commit_left_dirty_tree`; it does not hide or clean residual changes.

## 15. Troubleshooting

### YAML parse or validation errors

Use two-space indentation, block mappings/lists, and quoted strings for values that look like booleans or numbers. Advanced YAML features are unsupported. See the [workflow reference](workflow-reference.md).

### Generated script uses the wrong Python

Render with the intended AIWK virtual environment. `pythonPath` is captured from the rendering interpreter.

### Gate command works manually but not in AIWK

Remember every configured command starts independently with `cwd` set to the repository root. Shell state such as `cd subdir` or `source setup.sh` does not carry into the next command. Put dependent operations in the same shell snippet or repeat setup.

### A grep-like check exits 1

Exit 1 with empty stdout is retained as check `rc:1`, but count is zero. Gate cleanliness is based on timeout and count threshold for checks, not check return code alone.

### Non-Git repository

Preflight and checkpoint require Git. `gate-run` can execute commands in a non-Git directory; integrity metadata records null Git fields and explanatory notes.

### Tests and local development

```bash
cd ~/dev/aiwk
.venv/bin/python -m pytest -q
```
