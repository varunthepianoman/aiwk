# Pass 5 Prompt: Beads Integration

You are working in the existing AIWK repository at:

```text
~/dev/aiwk
```

This is **Pass 5: Beads Integration**.

## Context

AIWK now has:

```text
Pass 1.0 — durable substrate ✅
Pass 2.0 — workflow.yaml + Claude workflow renderer ✅
Pass 2.5/2.6 — mature runtime-compatible Claude workflow renderer ✅
Pass 3.0 — Objective Gate DSL ✅
Pass 3.1 — gate-run evidence/logs ✅
Pass 4.0/4.1 — commit simplification and final clean-status enforcement ✅
Pass 3.2 — timeout/evidence integrity hardening ✅ or deferred
```

Current generated workflows preserve `beadsSnapshot`, but Beads integration is still mostly prompt text.

The goal of this pass is to make Beads a configurable, durable workflow affordance without over-automating it.

## Goal

Add first-class Beads configuration and generated workflow support.

AIWK should support:

```text
- optional Beads enablement in workflow.yaml
- generated Beads discipline block
- operator-supplied beadsSnapshot
- optional fallback Beads commands
- Beads summary in context
- Beads update guidance for Scope/Dev/Red/Review/Commit
```

Do **not** yet implement a full Beads API wrapper or automatic issue lifecycle management unless already trivial.

## Important constraints

- Edit AIWK source under `~/dev/aiwk`.
- Do not edit `~/dev/t_robotics` source.
- Do not hand-patch generated JS except by regenerating from AIWK.
- Do not make Beads required for all workflows.
- Workflows without Beads config must render and run as before.
- Preserve runtime-compatible generated JS:
  - `meta.name` present
  - no `export default`
  - no `process.env`
  - no `permissionMode`
  - no `env:`
  - Node syntax valid
- Preserve objective gate and commit behavior.
- Do not implement project templates in this pass.
- Do not implement token accounting.

## Workflow config shape

Add optional top-level Beads config:

```yaml
beads:
  enabled: true
  project_hint: "handoff-refactor"
  require_before_edit: true
  allow_create_issue: true
  allow_remember: true
  status_filter: "open,in_progress,blocked,deferred,closed"
  before_edit_commands:
    - "bd prime || true"
    - "bd list --status open,in_progress,blocked,deferred,closed || true"
  remember_guidance:
    - "Use bd remember for durable architecture decisions."
    - "Do not use ad-hoc markdown task lists as durable state."
```

Backward compatibility:

```text
- Missing beads config means disabled.
- Existing beadsSnapshot arg remains supported regardless of config.
- If beads.enabled is false or missing, generated workflows should not demand bd commands.
```

## Parser/validation requirements

Add parsing and validation:

- `beads.enabled`: boolean, default false.
- `status_filter`: string if provided.
- `before_edit_commands`: list of strings if provided.
- `project_hint`: string optional.
- `require_before_edit`: boolean optional.
- `allow_create_issue`: boolean optional.
- `allow_remember`: boolean optional.
- Invalid types fail clearly.

## Generated JS requirements

Generated workflow should include:

```text
BEADS_CONFIG
getActiveBeadsContext()
withBeadsContext(...)
```

If Beads enabled:

- Include an `ACTIVE BEADS PROJECT LEDGER SNAPSHOT` section.
- Include operator-supplied `beadsSnapshot` if present.
- Include fallback guidance if no snapshot supplied.
- Include `LIVE BEADS DISCIPLINE` block before editing phases.

Suggested prompt block:

```text
=== ACTIVE BEADS PROJECT LEDGER SNAPSHOT ===
The workflow runtime cannot assume transcript memory.
Use this snapshot to avoid duplicating completed work, respect known decisions, and understand blockers.
If this ledger conflicts with committed source/specs, committed source/specs and this workflow's explicit scope win.

<beadsSnapshot or fallback>

=== LIVE BEADS DISCIPLINE ===
Before modifying code, run:
  bd prime || true
  bd list --status open,in_progress,blocked,deferred,closed || true

If a relevant issue exists, update it.
If no relevant issue exists and Beads is active, create one only if the workflow config allows it.
Use bd remember for durable project decisions or sharp debugging findings if allowed.
Do not use ad-hoc markdown task lists as durable trackers.
```

If Beads disabled:

- Keep `beadsSnapshot` available as optional operator context.
- Do not require bd commands.

## Role-specific Beads behavior

Generated prompts should include lightweight guidance:

### Scope Writer

```text
If Beads is enabled, note which issue/spec this scoping work corresponds to.
Do not create noisy issues for every small test unless configured.
```

### Developer

```text
If Beads is enabled, update relevant issue state and write durable decisions with bd remember when useful.
```

### Red Team

```text
If Beads is enabled, record meaningful new defects as Beads issues only if they are durable blockers, not transient local test failures.
```

### Reviewer

```text
If Beads is enabled, verify meaningful blockers are reflected in Beads or in the workflow result.
```

### Commit

```text
If Beads is enabled, mention any remaining blockers after commit.
```

Keep this concise. Do not bloat every prompt.

## Tests to add/update

### 1. Parser tests

- Beads config parses.
- Missing Beads config defaults to disabled.
- Invalid `before_edit_commands` type fails clearly.
- Invalid `enabled` type fails clearly.

### 2. Renderer tests

With Beads enabled, generated JS contains:

```text
BEADS_CONFIG
ACTIVE BEADS PROJECT LEDGER SNAPSHOT
LIVE BEADS DISCIPLINE
bd prime
bd list --status
bd remember
beadsSnapshot
```

With Beads disabled, generated JS:

```text
still accepts beadsSnapshot
does not require bd prime
does not include LIVE BEADS DISCIPLINE
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
preserve commit behavior
preserve mature markers
```

### 4. Generated workflow smoke

Render all `.aiwk` projects and syntax check.

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

If `node` is not on PATH but VS Code bundled Node is available, use that and report path.

## Stop rules

Stop and report if:

- Beads integration starts requiring a full Beads command wrapper.
- Runtime-compatible JS constraints are violated.
- Prompt size grows dramatically.
- Existing workflows without Beads break.
- Tests fail after 2–3 serious attempts.

## Final report format

Report exactly:

```text
AIWK source files changed:
Tests added/changed:
Beads config behavior:
Workflow.yaml/config changes:
Generated workflow files updated:
Commands run:
Test results:
Node syntax results:
Runtime validation request to run next:
Remaining limitations:
Recommended next pass:
```

Do not claim Claude runtime success. The user will run runtime validation if needed.
