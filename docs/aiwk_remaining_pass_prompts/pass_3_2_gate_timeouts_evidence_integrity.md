# Pass 3.2 Prompt: Gate Runner Timeouts and Evidence Integrity Metadata

You are working in the existing AIWK repository at:

```text
~/dev/aiwk
```

This is **Pass 3.2: Gate Runner Timeouts + Evidence Integrity Metadata**.

This pass is intentionally scheduled after Pass 4.0/4.1. It is hardening, not a prerequisite for commit policy work.

## Context

AIWK now has:

```text
Pass 1.0 — durable substrate ✅
Pass 2.0 — workflow.yaml + Claude workflow renderer ✅
Pass 2.5/2.6 — mature runtime-compatible Claude workflow renderer ✅
Pass 3.0 — Objective Gate DSL + enforced reviewer/gate separation ✅
Pass 3.1 — Objective Gate Evidence / Provenance ✅
Pass 4.0/4.1 — commit simplification and final clean-status enforcement ✅
```

Current objective gate behavior:

```text
- generated workflows ask the Objective Gate agent to run one deterministic `aiwk gate-run` command
- gate-run executes setup/build/test/result/check commands
- gate-run writes evidence JSON
- gate-run writes full logs
- generated workflow recomputes gate cleanliness from rc/count fields
```

Known remaining limitations:

```text
- no command timeouts
- evidence lacks strong integrity metadata/digests
- long ROS gates can hang
- audit trails could be stronger
```

## Goal

Add command timeout support and evidence integrity metadata to `aiwk gate-run`, without changing the core objective-gate architecture.

## Important constraints

- Edit AIWK source under `~/dev/aiwk`.
- Do not edit `~/dev/t_robotics` source.
- Do not hand-patch generated JS except by regenerating from AIWK.
- Do not implement Beads integration.
- Do not implement templates.
- Do not implement token accounting.
- Do not implement provider abstraction.
- Do not redesign objective gates.
- Preserve runtime-compatible generated JS:
  - `meta.name` present
  - no `export default`
  - no `process.env`
  - no `permissionMode`
  - no `env:`
  - Node syntax valid
- Preserve backward compatibility for objective gates without timeout fields.

## Feature 1: timeout support

Add timeout support to objective gate config.

Suggested `workflow.yaml` shape:

```yaml
objective_gates:
  default:
    enabled: true
    timeout_seconds: 120
    setup:
      timeout_seconds: 30
      commands:
        - python --version
    build:
      timeout_seconds: 60
      commands:
        - python -m py_compile tests/test_runtime_marker.py
    test:
      timeout_seconds: 60
      commands:
        - python -m unittest discover -s tests -p "test_*.py"
    result:
      timeout_seconds: 30
      commands:
        - true
    checks:
      - name: no_forbidden_marker
        command: "grep -R \"FORBIDDEN_MARKER\" ."
        max_count: 0
        timeout_seconds: 20
        counting_instructions: "Count matching output lines. If grep exits 1 because there are no matches, count 0."
```

Backward compatibility:

```text
- Existing gates without timeout_seconds must still work.
- Section timeout overrides gate-level timeout.
- Check timeout overrides gate-level timeout.
- If no timeout is supplied, use safe default, e.g. 300 seconds.
- Validate timeout_seconds if present:
  - integer or float > 0
  - fail clearly on invalid values
```

Timeout semantics:

```text
- Timeout is per command, not per whole section.
- Use Python subprocess timeout from stdlib.
- If a command times out:
  - mark timed_out: true
  - rc = 124
  - include timeout_seconds
  - include detail/tail saying it timed out
  - continue to later commands/sections according to existing “do not stop on first failure” behavior
- If any build/test/result command times out, gate_clean false.
- setup timeout is reported but setup_rc remains non-enforced by default.
```

## Feature 2: command-level evidence

Enhance evidence JSON with section command evidence.

Add something like:

```json
{
  "sections": {
    "setup": [
      {
        "command": "python --version",
        "rc": 0,
        "timed_out": false,
        "timeout_seconds": 30,
        "started_at": "...",
        "ended_at": "...",
        "duration_seconds": 0.12,
        "stdout_tail": "...",
        "stderr_tail": "..."
      }
    ],
    "build": [],
    "test": [],
    "result": []
  }
}
```

For checks, include:

```json
{
  "name": "no_forbidden_marker",
  "command": "...",
  "rc": 1,
  "count": 0,
  "max_count": 0,
  "timed_out": false,
  "timeout_seconds": 20,
  "duration_seconds": 0.04,
  "detail": "..."
}
```

Keep existing top-level fields for compatibility:

```text
setup_rc
build_rc
test_rc
result_rc
check_results
gate_clean
evidence_path
log_path
raw_tail
```

## Feature 3: evidence integrity metadata

Add integrity metadata to evidence JSON.

Include at least:

```json
{
  "integrity": {
    "evidence_schema_version": 1,
    "created_at": "...",
    "aiwk_version": "...",
    "python_executable": "...",
    "python_version": "...",
    "platform": "...",
    "repo_head_before": "...",
    "repo_status_before": "...",
    "repo_head_after": "...",
    "repo_status_after": "...",
    "workflow_spec_path": "...",
    "workflow_spec_sha256": "...",
    "aiwk_config_path": "...",
    "aiwk_config_sha256": "...",
    "gate_config_sha256": "...",
    "log_sha256": "...",
    "evidence_sha256": "..."
  }
}
```

Implementation notes:

```text
- Use Python stdlib only.
- Use hashlib.sha256.
- Use subprocess to read git state:
  - git rev-parse HEAD
  - git status --short
- If repo is not a git repo, do not crash.
- Record null/empty values plus explanatory notes.
```

Evidence hash rule:

```text
Avoid self-referential hashing:
1. Build evidence object with evidence_sha256 absent or null.
2. Compute canonical JSON hash over evidence object without evidence_sha256.
3. Write final evidence with evidence_sha256 populated.
4. Document what is hashed.
```

`log_sha256` should hash full log file bytes.

`gate_config_sha256` can hash canonical JSON serialization of resolved gate config.

`workflow_spec_sha256` and `aiwk_config_sha256` should hash file bytes.

## Feature 4: compact stdout remains compact

`aiwk gate-run` stdout should remain compact enough for Claude Workflow.

Include:

```text
status
gate
step
attempt
setup_rc/build_rc/test_rc/result_rc
check_results
gate_clean
evidence_path
log_path
raw_tail
integrity summary:
  evidence_sha256
  log_sha256
  repo_head_before
  repo_head_after
```

Do not print full section logs to stdout.

## Feature 5: renderer prompt update

Update generated Objective Gate prompt so it tells the gate agent:

```text
Run exactly the one `aiwk gate-run` command.
Return the compact JSON it prints.
Do not summarize instead of returning fields.
If the command times out internally, return the JSON with timed_out/rc fields.
If `aiwk gate-run` itself fails before producing JSON, return the visible error.
```

Update `GATE_SCHEMA` to allow/include:

```text
integrity
sections if returned
timed_out fields in check_results
evidence_sha256/log_sha256 if present
```

Do not over-constrain schema so valid evidence is rejected by the workflow runtime.

## Tests to add/update

### 1. Passing evidence test

- Run a temp objective gate with quick passing commands.
- Assert `gate_clean` true.
- Assert `evidence_path`/`log_path` exist.
- Assert `integrity` exists.
- Assert `log_sha256` exists.
- Assert `evidence_sha256` exists.
- Assert repo head/status fields are present.
- Assert command-level sections exist with `duration_seconds`.

### 2. Failing command evidence test

- Build command exits 7.
- `gate-run` process exits 0 if evidence was captured.
- stdout JSON has `build_rc: 7`.
- `gate_clean` false.
- evidence JSON records command rc 7.

### 3. Timeout test

- Use a command that sleeps longer than timeout.
- Use small reliable timeout:
  - `timeout_seconds: 0.2`
  - command: `python -c "import time; time.sleep(2)"`
- Assert rc 124.
- Assert `timed_out` true.
- Assert `gate_clean` false for build/test/result timeout.

### 4. Check timeout/count test

- Add a check with timeout_seconds.
- Assert check result includes `timed_out` and `timeout_seconds`.
- Add marker file test exceeding `max_count`; assert gate_clean false.

### 5. Invalid timeout config test

- `timeout_seconds: -1` or `"slow"`
- Parser/gate-run fails clearly.

### 6. Evidence hash test

- Load evidence JSON.
- Assert `evidence_sha256` is a 64-character lowercase hex string.
- If simple, recompute the documented hash.

### 7. Renderer tests

Generated JS should contain:

```text
evidence_path
log_path
gate_clean
integrity
evidence_sha256
log_sha256
timed_out
Run exactly this one AIWK command
```

Generated JS should still not contain:

```text
export default
process.env
permissionMode
env:
```

Mature marker regression tests still pass.

## Commands to run

Run tests:

```bash
cd ~/dev/aiwk
~/dev/aiwk/.venv/bin/python -m pytest -q
```

Run direct gate-run on runtime validation:

```bash
~/dev/aiwk/.venv/bin/python -m aiwk gate-run \
  --config ~/dev/.aiwk/aiwk_runtime_validation/aiwk.yaml \
  --gate default \
  --step RUNTIME_SS0 \
  --attempt 1 \
  --repo ~/dev/aiwk_runtime_validation_target
```

Regenerate all workflows:

```bash
for cfg in ~/dev/.aiwk/*/aiwk.yaml; do
  ~/dev/aiwk/.venv/bin/aiwk render claude-workflow --config "$cfg"
done
```

Syntax check all generated workflows:

```bash
for js in ~/dev/.aiwk/*/generated/*.js; do
  echo "== $js =="
  node --check "$js"
done
```

If `node` is not on PATH but VS Code bundled Node is available, use that and report the path.

## Stop rules

Stop and report if:

- Timeout config requires a large parser rewrite.
- Evidence hashing becomes self-referential or fragile.
- Runtime-compatible JS constraints are violated.
- Objective gate behavior breaks.
- Tests fail after 2–3 serious fix attempts.

## Final report format

Report exactly:

```text
AIWK source files changed:
Tests added/changed:
CLI behavior changes:
Workflow.yaml/config changes:
Generated workflow files updated:
Commands run:
Test results:
Gate-run direct result:
Evidence/log paths produced:
Integrity metadata produced:
Timeout behavior verified:
Node syntax results:
Runtime validation request to run next:
Remaining limitations:
Recommended next pass:
```

Do not claim Claude runtime success. The user will run runtime validation.
