# AIWK Claude Runtime Validation

Goal: prove that the mature AIWK-generated Claude Workflow JS is accepted by the actual Claude Workflow runtime, not just by `node --check` and pytest.

This validation uses a disposable toy repo so the workflow can safely run Scope, Dev, Red Team, Review, and Commit phases without touching production code.

## 1. Copy and run the setup script

Save `aiwk_runtime_validation_setup.sh` locally, then run:

```bash
bash aiwk_runtime_validation_setup.sh
```

The script creates:

```text
~/dev/aiwk_runtime_validation_target        # disposable target git repo
~/dev/.aiwk/aiwk_runtime_validation         # disposable AIWK project
~/dev/.aiwk/aiwk_runtime_validation/generated/aiwk_runtime_validation.claude_workflow.js
```

It also renders the workflow, runs `aiwk preflight`, writes a handoff file, and runs `node --check` if Node is available.

## 2. Run the Claude Workflow runtime request

Use the exact JSON printed by the setup script. It will look like:

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

Do not run this against a production workflow first. The validation should consume only the disposable target repo.

## 3. Expected Claude result

Pass criteria:

```text
- Generated JS starts in Claude Workflow runtime without API/signature errors.
- onlyStep=RUNTIME_SS0 is respected.
- Scope, Dev, Red Team, Review, and Commit phases execute or cleanly halt with structured JSON.
- Dev creates runtime_marker.txt in the disposable target repo.
- Review accepts or explains a real issue.
- Commit phase commits only target-repo files, or cleanly reports why it could not.
```

## 4. Local verification after Claude completes

Run:

```bash
cd ~/dev/aiwk_runtime_validation_target

git log --oneline -5
git status --short
cat runtime_marker.txt

python - <<'PY'
from pathlib import Path
p = Path('runtime_marker.txt')
assert p.read_text(encoding='utf-8') == 'AIWK_RUNTIME_VALIDATED\n'
print('marker content ok')
PY
```

Optional if pytest is available:

```bash
python -m pytest -q tests/test_runtime_marker.py
```

Also confirm production repos were not edited:

```bash
git -C ~/dev/t_robotics status --short
git -C ~/dev/aiwk status --short
```

`~/dev/aiwk` may show your intentional AIWK source changes. `~/dev/t_robotics` should not show new changes caused by this validation.

## 5. Failure interpretation

If it fails immediately with JS/runtime errors, the renderer still has a Claude runtime compatibility bug.

If it starts but `agentOptions(...)` or schema passing fails, the generated call signature is wrong.

If it runs phases but does not respect `onlyStep`, the workflow selection logic is wrong.

If it reaches commit but leaves files uncommitted, inspect whether the commit prompt/script discipline is too strict or whether the agent refused to run shell commands.

If it edits production repos, stop and fix the generated context/prompt boundaries before running any real workflow.

## 6. Cleanup

```bash
rm -rf ~/dev/aiwk_runtime_validation_target ~/dev/.aiwk/aiwk_runtime_validation
```
