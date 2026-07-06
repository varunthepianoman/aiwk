# Pass 6 Prompt: Handoff and Context Quality

You are working in the existing AIWK repository at:

```text
~/dev/aiwk
```

This is **Pass 6: Handoff and Context Quality**.

## Context

AIWK now has:

```text
Pass 1.0 — durable substrate ✅
Pass 2.0 — workflow.yaml + Claude workflow renderer ✅
Pass 2.5/2.6 — mature runtime-compatible renderer ✅
Pass 3.0/3.1 — objective gates and evidence/logs ✅
Pass 4.0/4.1 — commit simplification and clean-status enforcement ✅
Pass 5 — Beads integration ✅
```

AIWK currently has `context-pack`, but generated workflows still rely too much on prompt context and agent transcript memory. The goal of this pass is to make cold-starts and resumes much stronger.

## Goal

Improve AIWK handoff/context artifacts so agents can resume from durable state rather than transcript memory.

Add a richer `context-pack` / handoff mechanism that produces:

```text
- compact summary markdown
- structured context JSON
- changed files
- diff stat
- targeted diff excerpts
- objective gate evidence links
- latest commit/head/branch
- preflight status
- recent generated workflow result pointers if available
- Beads snapshot if supplied/configured
- next-agent instructions
```

Do this without huge prompt bloat.

## Important constraints

- Edit AIWK source under `~/dev/aiwk`.
- Do not edit `~/dev/t_robotics` source.
- Do not hand-patch generated JS except by regenerating from AIWK.
- Preserve runtime-compatible generated JS.
- Preserve objective gate behavior.
- Preserve commit behavior.
- Preserve Beads behavior.
- Do not implement templates.
- Do not implement token accounting.

## CLI/API changes

Extend existing:

```bash
aiwk context-pack --config <aiwk.yaml> --phase <PHASE>
```

Add optional arguments:

```bash
--step <STEP_ID>
--include-diff
--max-diff-lines <N>
--gate-evidence <path>
--beads-snapshot-file <path>
```

Keep backward compatibility: existing `context-pack` calls must continue to work.

Suggested output files:

```text
<project_folder>/state/<PHASE>_handoff.md
<project_folder>/state/<PHASE>_context.json
```

Possibly also:

```text
<project_folder>/state/handoffs/<timestamp>_<PHASE>_handoff.md
<project_folder>/state/handoffs/<timestamp>_<PHASE>_context.json
```

If adding timestamped copies is too much, keep the existing path behavior and add better content.

## Context JSON shape

Include at least:

```json
{
  "project": "...",
  "phase": "...",
  "step": "...",
  "repo": "...",
  "branch": "...",
  "head": "...",
  "status_short": "...",
  "dirty_relevant": true,
  "dirty_relevant_files": [],
  "changed_files": [],
  "diff_stat": "...",
  "diff_excerpt": "...",
  "preflight": {
    "status": "...",
    "log_path": "..."
  },
  "objective_gate": {
    "evidence_path": "...",
    "log_path": "...",
    "gate_clean": true,
    "summary": "..."
  },
  "beads": {
    "snapshot": "...",
    "notes": "..."
  },
  "next_agent_instructions": "...",
  "log_path": "..."
}
```

## Handoff markdown

Make the handoff useful to a cold-start agent.

Suggested sections:

```markdown
# AIWK Handoff: <phase>

## Current state
- Project:
- Repo:
- Branch:
- HEAD:
- Dirty relevant:
- Changed files:

## What changed
<diff stat>

## Key evidence
- Preflight log:
- Objective gate evidence:
- Objective gate log:
- Beads snapshot:

## Known failures / blockers

## Decisions / invariants to preserve

## Next-agent instructions
```

Do not include huge full diffs by default. Use `--include-diff` and `--max-diff-lines`.

## Renderer integration

Generated workflows should mention handoff path more usefully:

```text
If handoffPath is supplied, read it before editing.
Treat it as durable operator-provided context.
If it conflicts with source/specs, source/specs win.
```

If `context-pack` output paths are known, generated prompts can mention:

```text
AIWK context-pack files are under <project_folder>/state/
```

Do not try to make workflow JS run `context-pack`; the runtime cannot run shell directly. Keep it operator-driven or gate-agent driven for now.

## Tests to add/update

### 1. Context-pack backward compatibility

Existing tests still pass.

### 2. Rich context JSON

Create a temp repo, modify files, run `context-pack`, assert JSON includes:

```text
changed_files
diff_stat
head
branch
status_short
next_agent_instructions
```

### 3. Diff excerpt limit

With `--include-diff --max-diff-lines 5`, assert excerpt is capped.

### 4. Gate evidence inclusion

Create a fake evidence JSON path, run `context-pack --gate-evidence`, assert handoff and context JSON include the path and summary.

### 5. Beads snapshot file

Run with `--beads-snapshot-file`, assert included.

### 6. Renderer tests

Generated JS contains improved handoff guidance:

```text
If handoffPath is supplied, read it before editing
source/specs win
AIWK context-pack
```

### 7. Runtime compatibility tests

Generated JS must still:

```text
include meta.name
not include export default
not include process.env
not include permissionMode
not include env:
preserve objective gate wiring
preserve commit behavior
preserve Beads behavior
```

## Commands to run

Run tests:

```bash
cd ~/dev/aiwk
~/dev/aiwk/.venv/bin/python -m pytest -q
```

Run a direct context-pack smoke test on runtime validation:

```bash
~/dev/aiwk/.venv/bin/python -m aiwk context-pack \
  --config ~/dev/.aiwk/aiwk_runtime_validation/aiwk.yaml \
  --phase RUNTIME_SS0_DEV \
  --step RUNTIME_SS0 \
  --include-diff \
  --max-diff-lines 80
```

Regenerate all workflows:

```bash
for cfg in ~/dev/.aiwk/*/aiwk.yaml; do
  ~/dev/aiwk/.venv/bin/aiwk render claude-workflow --config "$cfg"
done
```

Syntax check:

```bash
for js in ~/dev/.aiwk/*/generated/*.js; do
  echo "== $js =="
  node --check "$js"
done
```

## Stop rules

Stop and report if:

- Context-pack changes require a large state-management rewrite.
- Diff extraction becomes fragile.
- Generated prompts become too large.
- Runtime-compatible JS constraints are violated.
- Tests fail after 2–3 serious attempts.

## Final report format

Report exactly:

```text
AIWK source files changed:
Tests added/changed:
Context-pack behavior changes:
Workflow.yaml/config changes:
Generated workflow files updated:
Commands run:
Test results:
Context-pack smoke result:
Node syntax results:
Runtime validation request to run next:
Remaining limitations:
Recommended next pass:
```
