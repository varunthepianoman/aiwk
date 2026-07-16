# AIWK Architecture and Execution Model

AIWK separates durable intent, deterministic evidence, provider-specific execution, and repository mutations. This document explains those boundaries.

## System layout

```text
Durable project inputs
  aiwk.yaml
  workflow.yaml
  spec/project.spec.md
  spec/invariants.yaml
  spec/gates.yaml
          │
          ├── aiwk render claude-workflow
          │       ├── generated/<project>.claude_workflow.js
          │       └── master_coordinator_prompt.md
          │
          ├── aiwk gate-run
          │       ├── state/gates/*.json
          │       └── logs/gates/*.log
          │
          └── aiwk context-pack
                  ├── state/<phase>_context.json
                  └── state/<phase>_handoff.md

Target Git repository
  source, tests, builds, commits
```

The target repository and AIWK project are separate concerns. `init` writes only the workflow folder. Operational commands explicitly target the repository recorded in `aiwk.yaml` or supplied with `--repo`.

## Durable versus generated data

Durable author-edited inputs:

- `workflow.yaml` controls stages, steps, objective commands, commit behavior, and optional advisory external-memory snapshot behavior.
- `project.spec.md` defines outcome and boundaries.
- `invariants.yaml` records properties to preserve.
- `gates.yaml` records semantic reviewer gates.

Generated or operational artifacts:

- Claude Workflow JavaScript;
- master coordinator launch runbook;
- objective gate evidence/logs;
- preflight logs;
- context packs and handoffs.

Never make durable workflow changes only in generated JS. The next render will replace them.

The same rule applies to `master_coordinator_prompt.md`. It is a thin launch/control-plane artifact: exact paths, fresh-context commands, runtime argument construction, halt policy, and completion checks. It references durable requirements rather than copying them, and every render replaces it.

## Render-time snapshot

Rendering performs four jobs:

1. Parse and validate the limited YAML workflow schema.
2. Resolve inherited commit policies and objective-gate references.
3. Read and embed project spec, invariant, and gate contents.
4. Emit runtime-compatible JavaScript with paths and the current Python interpreter.

Because the spec contents are embedded, generated JS is a snapshot. Editing a durable input does not mutate an existing script; rerender explicitly.

## Runtime-compatible JavaScript

The generated artifact follows the established Claude Workflow script shape:

- exports `meta` with a non-empty `name`;
- uses top-level workflow execution rather than `export default`;
- calls agents as `agent(prompt, agentOptions(...))`;
- avoids Node-specific `process.env` and unsupported permission/env options;
- returns structured `{halted_at, reason, stage, results}` data.

AIWK can syntax-check output with Node, but Claude Workflow runtime execution occurs outside AIWK.

## Step routing

The normal control flow is:

```text
Scope
  │ blocked / needs decision → halt
  ▼
Discovery (optional)
  ▼
Developer ─────┐
  ▼            │ failures
Red Team ──────┘  (at most MAX_DEV_RED_CYCLES = 2)
  │ passed
  ▼
Objective Gate
  ▼
Reviewer
  │ rejected or gate red
  ▼
Developer Fix → Objective Gate → Reviewer
                  (at most MAX_REVIEW_ATTEMPTS = 2 total)
  │ accepted = gateClean && reviewer.accepted && scope_clean
  ▼
Commit policy
  ▼
Clean-status enforcement
```

The reviewer cannot turn a red objective gate green. Its acceptance is necessary but insufficient. Conversely, a green command gate cannot approve architectural scope or code quality by itself.

## Runtime selection and recovery

`stage` selects a stage or defaults to `meta.defaultStage`. `onlyStep` selects exactly one step; `fromStep` slices the selected stage from a recovery point. Both together are rejected.

`startAtRole` is an intra-step fresh-launch entry point. It requires `onlyStep` plus durable evidence such as `handoffPath` or `gateEvidencePath`, then generated routing skips earlier roles inside the selected step. For example, `startAtRole: "review"` skips Scope/Discovery/Dev/Red Team, seeds handoff context, runs a fresh objective gate when configured, and invokes Reviewer. This is not Claude Workflow runtime-frame resume; AIWK does not recover old script variables across launches.

Recovery is an operator decision. AIWK does not infer that an earlier step was accepted from Git history. Use handoff paths and explicit runtime arguments.

## Objective gate execution

The Claude Objective Gate role does not manually interpret a large shell block. Its only task is to run one generated, interpreter-pinned command:

```text
<python> -m aiwk gate-run --config ... --workflow-spec ... --gate ... --step ... --attempt ... --repo ...
```

`gate-run` executes each configured command separately with:

- `cwd` equal to the target repository;
- `/bin/sh` through `shell=True`;
- a per-command timeout;
- stdout/stderr capture;
- continuation after failure.

Section status is the last nonzero return code. A timeout uses code 124. Check cleanliness is determined by timeout status and count threshold, not check return code alone.

### Evidence and integrity

Full logs preserve commands, return codes, durations, timeouts, stdout, and stderr. Evidence JSON includes output tails and:

- AIWK/Python/platform identity;
- repo HEAD/status before and after;
- hashes of `workflow.yaml`, `aiwk.yaml`, resolved gate config, and log;
- an evidence hash.

The evidence hash avoids self-reference: it is SHA-256 over canonical JSON with `integrity.evidence_sha256` set to null. The final file then stores the computed hash.

Generated JS still independently recomputes gate cleanliness from return codes, check counts, configured thresholds, timeout flags, status, and evidence/log paths. It does not accept Python’s `gate_clean` boolean as sufficient proof.

## Commit boundary

Commit happens only after accepted gate/review routing.

### `mechanical_all`

The low-effort commit role stages all changes, commits with a rendered message, reports status before/after, and returns a commit hash. Generated routing halts if commit fails or leaves a non-empty status.

This mode assumes preflight and review have already rejected unrelated dirty files. It is intentionally not a smart staging algorithm.

### `mechanical_paths`

This legacy mode limits staging to agent-reported paths. It can miss intended files when prior roles report descriptions rather than actual paths.

### `none`

No commit agent runs. The structured result records a skipped commit, and clean-after enforcement is not imposed by the commit phase.

The separate `aiwk checkpoint` CLI is a direct utility that stages all target-repo changes. It is not invoked by the generated commit policy.

## External memory / Beads boundary

AIWK is Beads-blind by default. It does not require Beads, run `bd`, manage issues, or treat any external tracker as source of truth.

Legacy `beads.enabled: true` configs remain parseable but map to snapshot-only advisory memory. When explicit snapshot mode is enabled and an operator supplies text, generated prompts may include that text under an optional external-memory section. Agents are told that source, specs, gate evidence, and Git state override the snapshot and that they must not mutate external memory or run `bd` commands.

## Context and handoff boundary

`context-pack` is operator-driven. Generated JS points agents toward operator-supplied `handoffPath` but does not run context generation itself.

Generated non-gate/non-commit agents also write per-agent handoffs below:

```text
state/handoffs/<STEP>_<ROLE>_C<CYCLE>_<AGENT_ID>.md
```

The workflow tracks returned `handoff_path` values and injects them into downstream prompts. This is a prompt/runtime coordination mechanism, not a database: generated JS enforces that structured output contains a handoff path, but it does not independently verify file contents.

Context packs intentionally prefer summaries and pointers over full data:

- diff excerpts are opt-in and line-limited;
- gate logs remain separate files;
- optional external-memory snapshots are included only when supplied and explicitly enabled;
- source and committed specs override stale handoff text.

Discovery agents are optional. They centralize broad repository mapping before Developer so later agents can use targeted verification instead of repeated global sweeps.

Checkpoint/continuation support is prompt-level. Since generated JS cannot reliably observe provider-internal tool-call counts, long agents are instructed to write a handoff and return `status:"checkpoint"`; generated routing surfaces a structured `checkpoint_requested` halt for an operator to continue with fresh context.

## Safety model

AIWK relies on several explicit trust decisions:

- Workflow authors trust objective-gate shell commands.
- `mechanical_all` trusts that preflight/review excluded unrelated dirtiness.
- Agent outputs are structured but not cryptographically attested by the provider runtime.
- Evidence hashes detect accidental/after-the-fact changes; they are not signed identities.
- Generated prompts constrain roles but do not form an OS sandbox.

Use disposable repositories for runtime validation before applying new renderer behavior to valuable projects.

## Extension points

The current design keeps future work localized:

- add templates through `aiwk/templates.py`;
- add provider renderers under `aiwk/renderers/`;
- extend workflow dataclasses and validation in `workflow_spec.py`;
- extend deterministic operations as CLI modules rather than embedding shell execution in provider JS.
