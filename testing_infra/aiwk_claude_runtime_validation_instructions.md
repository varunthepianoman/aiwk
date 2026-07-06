# Claude Workflow Runtime Validation

This procedure validates AIWK’s generated JavaScript against the actual Claude Workflow runtime using an isolated toy repository. It is the final integration check beyond Python tests and `node --check`.

It exercises:

- generated-script runtime compatibility;
- `onlyStep` selection;
- Scope, Developer, Red Team, Objective Gate, Reviewer, and Commit routing;
- deterministic `gate-run` evidence;
- mechanical-all commit behavior;
- final clean-tree enforcement.

It must not be pointed at a production repository.

## 1. Prerequisites

Install AIWK in its virtual environment:

```bash
cd ~/dev/aiwk
.venv/bin/python -m pip install -e .
.venv/bin/aiwk --help
```

The setup script refuses to overwrite an existing target or AIWK project. If an earlier disposable validation exists, inspect anything you want to retain and remove it explicitly:

```bash
rm -rf ~/dev/aiwk_runtime_validation_target
rm -rf ~/dev/.aiwk/aiwk_runtime_validation
```
These paths are disposable validation state; do not substitute production paths.

## 2. Create a clean validation project

```bash
cd ~/dev/aiwk
bash testing_infra/aiwk_runtime_validation_setup.sh
```

The script creates:

```text
~/dev/aiwk_runtime_validation_target
~/dev/.aiwk/aiwk_runtime_validation
~/dev/.aiwk/aiwk_runtime_validation/generated/aiwk_runtime_validation.claude_workflow.js
```

The target repository begins with a committed README and unittest. Python caches are excluded locally. The workflow project contains:

- a deterministic objective gate with per-section timeouts;
- a forbidden-marker count check;
- `mechanical_all` commit policy;
- a project spec and invariants limiting all edits to the disposable target;
- preflight and operator handoff artifacts.

The setup script renders the workflow and prints the exact runtime request. If `node` is on `PATH`, it also checks JavaScript syntax.

## 3. Inspect before launch

```bash
TARGET=~/dev/aiwk_runtime_validation_target
PROJECT=~/dev/.aiwk/aiwk_runtime_validation

git -C "$TARGET" status --short
cat "$PROJECT/state/runtime_preflight.json"
node --check "$PROJECT/generated/aiwk_runtime_validation.claude_workflow.js"
```

The target status should be empty. If Node is unavailable, skip only the syntax command; do not change the generated artifact manually.

## 4. Run the Claude Workflow request

Submit this shape to the Claude Workflow runtime:

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

AIWK does not launch this request itself.

## 5. Expected workflow behavior

The run should:

1. Select only `RUNTIME_SS0`.
2. Scope a black-box marker-file test without implementation work.
3. Create `runtime_marker.txt` containing exactly `AIWK_RUNTIME_VALIDATED\n`.
4. Allow Red Team to add a durable adversarial test if useful.
5. Run one generated `aiwk gate-run` command.
6. Produce JSON evidence and a full gate log.
7. Require both clean objective evidence and reviewer acceptance.
8. Mechanically stage all accepted target changes and commit them.
9. Require an empty post-commit `git status --short`.
10. Return `reason: "all_steps_accepted"` with a per-step gate, review, and commit result.

A structured halt is a valid diagnostic outcome but not a passing runtime validation. Inspect `halted_at`, `reason`, and the relevant role result.

## 6. Verify after the run

```bash
TARGET=~/dev/aiwk_runtime_validation_target
PROJECT=~/dev/.aiwk/aiwk_runtime_validation

git -C "$TARGET" status --short
git -C "$TARGET" log --oneline -5
cat "$TARGET/runtime_marker.txt"

find "$PROJECT/state/gates" -type f -name '*.json' -print | sort
find "$PROJECT/logs/gates" -type f -name '*.log' -print | sort
```

Pass criteria:

- target status is empty;
- a new `RUNTIME_SS0` commit exists;
- marker content is exact;
- gate evidence reports `gate_clean:true`;
- `build_rc`, `test_rc`, and `result_rc` are zero;
- evidence and log SHA-256 values are present;
- workflow result reason is `all_steps_accepted`.

Verify marker bytes with the AIWK environment:

```bash
~/dev/aiwk/.venv/bin/python - <<'PY'
from pathlib import Path
p = Path.home() / "dev/aiwk_runtime_validation_target/runtime_marker.txt"
assert p.read_bytes() == b"AIWK_RUNTIME_VALIDATED\n"
print("marker bytes: ok")
PY
```

## 7. Interpreting failures

| Failure | Likely area |
| --- | --- |
| Script rejected before agents run | Generated JS/runtime compatibility. |
| `unknown_onlyStep` | Runtime argument or workflow step mismatch. |
| Scope/Dev/Red structured halt | Role prompt, implementation, or test issue. |
| `objective_gate_failed_after_retries` | Inspect latest evidence JSON and full log. |
| `review_rejected_after_retries` | Architecture/scope/reviewer findings remained unresolved. |
| `commit_failed` | Git identity, commit command, or agent reporting failure. |
| `commit_left_dirty_tree` | Commit result reports residual changes; inspect `status_after`. |
| Gate command timeout (`rc:124`) | Command or configured timeout is unsuitable. |

The reviewer cannot override a red objective gate. The workflow also recomputes cleanliness instead of trusting the runner’s `gate_clean` field alone.

## 8. Production-repository check

After validation, confirm no production repository was touched:

```bash
git -C ~/dev/t_robotics status --short
git -C ~/dev/aiwk status --short
```

The AIWK repository will show intentional source/documentation changes. Compare production status with its known baseline rather than assuming it was clean beforehand.

## 9. Cleanup

```bash
rm -rf ~/dev/aiwk_runtime_validation_target
rm -rf ~/dev/.aiwk/aiwk_runtime_validation
```
