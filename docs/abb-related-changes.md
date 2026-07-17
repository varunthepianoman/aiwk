You are Codex working on the AIWK tool itself.

## Workspace

AIWK source:

```text
/home/varunkamat/dev/aiwk
```

AIWK virtual environment:

```text
/home/varunkamat/dev/aiwk/.venv
```

Use these only as read-only references while diagnosing the defects:

```text
/home/varunkamat/dev/.aiwk/abb_arci_v2_gofa_transport
/home/varunkamat/dev/.aiwk/abb_arci_v2_gofa_motion
/home/varunkamat/dev/t_robotics_abb_arci_v2_gofa
```

Use the configured virtual environment explicitly:

```bash
/home/varunkamat/dev/aiwk/.venv/bin/python
/home/varunkamat/dev/aiwk/.venv/bin/aiwk
```

Do not use system Python. Do not use `--break-system-packages`.

## Task

Fix the reusable AIWK renderer/runtime defects exposed by the ABB ARCI v2 workflow audit.

This prompt is about AIWK itself. Do not repair the ABB workflow projects yet, do not edit robotics source, do not run `bd`, and do not launch any generated workflow.

Add focused regression coverage for:

- true no-Beads-by-default behavior;
- optional external-memory snapshots;
- durable per-agent handoffs;
- targeted context propagation;
- actual checkpoint continuation;
- corrected Reviewer wording and semantics;
- generated wrapper/coordinator behavior.

## Required behavior

### 1. No-Beads-by-default must be real

When:

```yaml
beads:
  enabled: false
```

AIWK must not require:

- Beads;
- the `bd` executable;
- a Beads database;
- a Beads snapshot;
- a snapshot file;

to render a workflow, run preflight, build a context pack, or launch a generated workflow.

An optional external-memory snapshot may still be supported, but only when explicitly supplied by the operator and when the supplied file exists.

Required behavior:

```text
- Omit --beads-snapshot-file when no snapshot was supplied.
- Never create or fake an empty snapshot file.
- Never tell generated agents to run bd while Beads is disabled.
- Do not make an external-memory snapshot mandatory.
- Backward-compatible field names may remain, but default behavior must be Beads-blind.
```

### 2. Durable per-agent handoffs

Every substantive agent invocation must receive its own unique handoff path.

This includes:

```text
Scope / Discovery
Developer
Developer continuation
Developer repair after Red Team
Red Team
Developer repair after Reviewer rejection
Reviewer
```

The handoff path must be unique across:

```text
- step ID;
- role;
- Developer/Red-Team cycle or Reviewer attempt;
- continuation number;
- the individual agent/invocation.
```

Use a path shape comparable to:

```text
<project>/state/handoffs/<step>_<role>_<cycle-or-attempt>_<unique-suffix>.md
```

Do not reuse one generic handoff path for multiple agents or cycles.

A missing, empty, nonexistent, or out-of-project handoff path from a substantive role must make that invocation incomplete and must prevent dependent roles from advancing.

Each handoff document must contain at least:

```text
Summary
Role and step
Files inspected
Files changed
Important symbols or line ranges
Commands and tests run
Gate evidence consulted
Known limitations
Remaining work
Recommended next reads
Paths accepted or intentionally untouched
```

Structured role outputs must include at least:

```text
handoff_path
files_changed
files_inspected
tests_run
known_dirty_paths
next_agent_should_read
```

Include additional structured fields where useful, such as:

```text
gate_evidence_paths
recommended_next_reads
large_files_fully_read
remaining_findings
continuation_required
```

### 3. Targeted context propagation

Later agents must receive compact, targeted context rather than being asked to rediscover the repository.

Pass forward:

```text
- prior handoff paths;
- exact changed paths;
- objective-gate evidence paths;
- compact Git/test summaries;
- allowed edit paths;
- forbidden scope;
- concrete findings that must be repaired or verified.
```

Rules:

```text
- Later roles read prior handoffs first.
- Do not re-inline the whole project specification into every role prompt.
- Do not pass the full upstream narrative when paths, findings, and evidence suffice.
- Red Team receives the final Developer handoff plus exact changed paths.
- Reviewer receives the final Developer/repair handoff, exact changed paths, and fresh objective-gate evidence.
- Reviewer remains independent, but does not blindly rediscover the entire repository.
```

### 4. Real checkpoint continuation

Checkpoint support must cause a real fresh-agent continuation.

When a role reports that a checkpoint or continuation is required:

1. Validate the returned handoff.
2. Persist checkpoint state.
3. Reinvoke the same logical role for the same step in a fresh agent.
4. Pass the checkpoint handoff and remaining-work summary first.
5. Preserve the current Developer/Red-Team cycle or Reviewer attempt.
6. Assign the continuation invocation a new unique handoff path.
7. Continue until the role is done, blocked, or reaches a finite continuation limit.

A checkpointed Developer must not:

```text
- advance directly to Red Team;
- advance to Reviewer;
- consume a new Developer/Red-Team repair cycle merely because it checkpointed.
```

If the continuation limit is exceeded, halt explicitly with:

```text
checkpoint_continuation_limit_exceeded
```

Do not claim checkpoint support merely because generated prompts tell an agent to write a checkpoint. The orchestrator must actually launch the continuation agent.

### 5. Correct stale Reviewer wording and semantics

Audit generated Reviewer prompts.

They must describe review of:

```text
- the current repository diff;
- durable upstream handoffs;
- exact changed paths;
- fresh objective-gate evidence.
```

Remove stale assumptions such as:

```text
- the Reviewer always reviews an “uncommitted Developer diff”;
- the Reviewer should broadly rediscover the entire repository;
- Commit always performs explicit-path staging.
```

For:

```yaml
commit:
  mode: mechanical_all
```

the actual commit behavior is:

```bash
git status --short
git add -A
git commit -m "<commit_message>"
git status --short
git rev-parse HEAD
```

Generated wording must match that behavior.

The Reviewer must produce concrete findings and must write its own unique durable handoff.

Do not add broad automatic untracked-file policing. The user explicitly does not want a new whole-tree policy that rejects unrelated untracked files by default.

### 6. Wrapper and coordinator generation

Generated wrappers must use the configured AIWK interpreter from the project’s virtual environment rather than an arbitrary system Python.

In particular:

```text
scripts/context_pack.sh
```

must do more than accept only a phase. It must forward the supported context-pack options, including optional external-memory/snapshot arguments when they were actually supplied.

Coordinator behavior:

```text
- Omit --beads-snapshot-file if no snapshot exists.
- Include an optional snapshot only when explicitly supplied and present.
- Do not manufacture an empty snapshot.
- Use the configured AIWK executable/interpreter.
```

Fix the generator/source of truth and regenerate disposable fixtures as needed. Do not hand-patch generated JavaScript.

## Tests

Add or update regression tests covering at least:

1. Rendering with `beads.enabled: false`.
2. Context-pack generation without a snapshot.
3. Context-pack generation with an explicitly supplied snapshot.
4. Coordinator omission of `--beads-snapshot-file` when absent.
5. No generated `bd` instruction when Beads is disabled.
6. Unique handoff paths across roles, cycles, Reviewer attempts, Developer-fix invocations, and checkpoint continuations.
7. Missing-handoff rejection for substantive roles.
8. Handoff propagation to Developer, Red Team, Developer-fix, and Reviewer.
9. A checkpoint causing a continuation-agent invocation.
10. Continuation-limit exhaustion halting clearly.
11. Reviewer prompts using corrected current-state wording.
12. Generated wrappers using the configured AIWK interpreter.
13. Rendered workflow JavaScript passing `node --check`.

Also run:

```bash
cd /home/varunkamat/dev/aiwk
/home/varunkamat/dev/aiwk/.venv/bin/python -m pytest -q
```

Run a disposable rendered-runtime smoke test if the repository has one or if one can be added safely.

Do not launch either production ABB workflow.

## Scope restrictions

Do not:

```text
- edit /home/varunkamat/dev/t_robotics_abb_arci_v2_gofa;
- implement ABB robotics functionality;
- repair ABB domain specifications;
- edit the two production ABB workflow projects during this prompt;
- launch generated workflows;
- run bd;
- introduce automatic whole-tree untracked-file policing;
- redesign AIWK beyond the defects required here;
- hand-edit generated JavaScript;
- claim checkpoint support merely because prompts mention checkpointing.
```

Preserve existing objective-gate behavior, commit-policy behavior, runtime compatibility, and backward compatibility unless a change is directly required by the defects above.

## Final report

Report exactly:

```text
AIWK commit inspected:
AIWK files changed:
Checkpoint root cause:
Checkpoint continuation implementation:
Continuation limit behavior:
Checkpoint validation behavior:
Handoff path uniqueness changes:
Reviewer wording change:
Context-pack wrapper ownership/result:
Optional snapshot ownership/result:
Tests added or changed:
Commands run:
Pytest result:
Rendered runtime smoke result:
Node syntax result:
Backward compatibility:
Known limitations:
Changes intentionally not made:
```