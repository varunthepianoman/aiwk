#!/usr/bin/env bash
set -euo pipefail

AIWK_ROOT="${AIWK_ROOT:-$HOME/dev/aiwk}"
AIWK_PY="${AIWK_PY:-$AIWK_ROOT/.venv/bin/python}"
AIWK_PROJECT_ROOT="${AIWK_PROJECT_ROOT:-$HOME/dev/.aiwk}"
TARGET_REPO="${TARGET_REPO:-$HOME/dev/aiwk_runtime_validation_target}"
PROJECT="${PROJECT:-aiwk_runtime_validation}"
PROJECT_DIR="$AIWK_PROJECT_ROOT/$PROJECT"
GENERATED_JS="$PROJECT_DIR/generated/$PROJECT.claude_workflow.js"

if [[ ! -x "$AIWK_PY" ]]; then
  echo "ERROR: AIWK Python not executable: $AIWK_PY" >&2
  echo "Set AIWK_ROOT or AIWK_PY, then rerun." >&2
  exit 1
fi

if [[ -e "$TARGET_REPO" || -e "$PROJECT_DIR" ]]; then
  echo "ERROR: validation target already exists." >&2
  echo "Remove these if you want a clean rerun:" >&2
  echo "  rm -rf '$TARGET_REPO' '$PROJECT_DIR'" >&2
  exit 1
fi

mkdir -p "$TARGET_REPO" "$AIWK_PROJECT_ROOT"

cd "$TARGET_REPO"
git init
git config user.email "aiwk-runtime-smoke@example.com"
git config user.name "AIWK Runtime Smoke"

cat > README.md <<'README'
# AIWK Runtime Validation Target

Disposable toy repository used to validate generated Claude Workflow runtime compatibility.
README

mkdir -p tests
cat > tests/test_runtime_marker.py <<'PYTEST'
from pathlib import Path
import unittest


class RuntimeMarkerTests(unittest.TestCase):
    def test_runtime_marker_file(self):
        marker = Path(__file__).resolve().parents[1] / "runtime_marker.txt"
        self.assertEqual(marker.read_text(encoding="utf-8"), "AIWK_RUNTIME_VALIDATED\n")
PYTEST

cat >> .git/info/exclude <<'IGNORE'
__pycache__/
*.pyc
IGNORE

git add README.md tests/test_runtime_marker.py
git commit -m "init runtime validation target"

"$AIWK_PY" -m aiwk init \
  --project "$PROJECT" \
  --repo "$TARGET_REPO" \
  --workflow-folder "$AIWK_PROJECT_ROOT"

cat > "$PROJECT_DIR/workflow.yaml" <<YAML
project: aiwk_runtime_validation
description: Disposable AIWK Claude runtime validation workflow. It is intentionally tiny and isolated from production repos.
default_stage: build

commit:
  mode: mechanical_all
  message_template: "{step_id}: {step_title}"
  agent:
    model: sonnet
    effort: low

objective_gates:
  default:
    enabled: true
    timeout_seconds: 30
    setup:
      timeout_seconds: 10
      commands:
        - $AIWK_PY --version
    build:
      timeout_seconds: 10
      commands:
        - $AIWK_PY -m py_compile tests/test_runtime_marker.py
    test:
      timeout_seconds: 20
      commands:
        - $AIWK_PY -m unittest discover -s tests -p "test_*.py"
    result:
      timeout_seconds: 10
      commands:
        - "true"
    checks:
      - name: no_forbidden_marker
        command: 'grep -R "FORBIDDEN_MARKER" .'
        max_count: 0
        timeout_seconds: 10

stages:
  build:
    description: Validate generated Claude workflow runtime compatibility on an isolated toy repo.
    steps:
      - id: RUNTIME_SS0
        title: Runtime validation marker file
        model: sonnet
        effort: medium
        objective_gate: default
        phases:
          - scope
          - dev
          - redteam
          - review
          - commit
        prompt:
          scope: Write or update a tiny black-box pytest test under tests/ that validates runtime_marker.txt contains the exact string AIWK_RUNTIME_VALIDATED followed by a newline. Do not edit implementation files in this phase.
          dev: Create runtime_marker.txt at the repo root containing exactly AIWK_RUNTIME_VALIDATED followed by a newline. Run the targeted pytest if available.
          redteam: Inspect the implementation and test. Try to find a minimal adversarial failure for the marker-file requirement. Do not patch implementation.
          review: Verify the repo has runtime_marker.txt with exactly AIWK_RUNTIME_VALIDATED, the targeted pytest passes if pytest is available, and no unrelated files were changed.
YAML

cat > "$PROJECT_DIR/spec/project.spec.md" <<'SPEC'
# AIWK Runtime Validation Spec

This is a disposable runtime smoke project. The target repo is isolated from production code.

Required behavior:

- The generated Claude Workflow JS must be accepted by the Claude Workflow runtime.
- `onlyStep=RUNTIME_SS0` must select exactly the runtime validation step.
- Agents must be able to execute Scope, Dev, Red Team, Review, and Commit phases.
- The Dev phase should create `runtime_marker.txt` at the target repo root.
- The marker file must contain exactly `AIWK_RUNTIME_VALIDATED` followed by one newline.
- No production repositories should be edited.
SPEC

cat > "$PROJECT_DIR/spec/invariants.yaml" <<'YAML'
invariants:
  - id: disposable-target-only
    description: Only the disposable target repo may be changed by the workflow run.
  - id: exact-marker-content
    description: runtime_marker.txt must contain exactly AIWK_RUNTIME_VALIDATED followed by one newline.
  - id: no-production-edits
    description: Do not edit ~/dev/t_robotics or ~/dev/aiwk source during this runtime validation.
  - id: narrow-scope
    description: Do not add broad framework features or alter AIWK itself during this runtime validation.
YAML

cat > "$PROJECT_DIR/spec/gates.yaml" <<'YAML'
gates:
  - id: generated-js-runs
    description: Claude Workflow runtime accepts the generated JS and starts the selected step.
  - id: marker-created
    description: runtime_marker.txt exists at the target repo root.
  - id: marker-content-exact
    description: runtime_marker.txt content is exactly AIWK_RUNTIME_VALIDATED plus newline.
  - id: targeted-test-passes
    description: tests/test_runtime_marker.py passes if pytest is available in the environment.
  - id: clean-or-intentional-status
    description: git status is clean after the commit phase, or any remaining files are explicitly explained.
YAML

"$AIWK_PY" -m aiwk render claude-workflow --config "$PROJECT_DIR/aiwk.yaml"

"$AIWK_PY" -m aiwk preflight --config "$PROJECT_DIR/aiwk.yaml" | tee "$PROJECT_DIR/state/runtime_preflight.json" >/dev/null
"$AIWK_PY" -m aiwk context-pack --config "$PROJECT_DIR/aiwk.yaml" --phase RUNTIME_SS0_PRESTART | tee "$PROJECT_DIR/state/runtime_context_pack_result.json" >/dev/null

cat > "$PROJECT_DIR/state/runtime_operator_handoff.md" <<EOF2
# Runtime Validation Operator Handoff

This is a disposable AIWK runtime validation run.

Target repo:
$TARGET_REPO

AIWK project folder:
$PROJECT_DIR

Generated workflow:
$GENERATED_JS

Task:
Run only step RUNTIME_SS0. The workflow should create runtime_marker.txt in the target repo with exactly:

AIWK_RUNTIME_VALIDATED

Do not edit production repos. Do not edit ~/dev/t_robotics or ~/dev/aiwk source.
EOF2

if command -v node >/dev/null 2>&1; then
  node --check "$GENERATED_JS"
else
  echo "WARN: node not found; skipping node --check" >&2
fi

cat <<EOF3

READY: AIWK Claude runtime validation project created.

Generated workflow:
  $GENERATED_JS

Target repo:
  $TARGET_REPO

Use this Claude Workflow request:

{
  "scriptPath": "$GENERATED_JS",
  "args": {
    "stage": "build",
    "onlyStep": "RUNTIME_SS0",
    "preflightSummary": "Use $PROJECT_DIR/state/runtime_preflight.json. This is a disposable runtime validation; do not run broad repo discovery unless needed.",
    "handoffPath": "$PROJECT_DIR/state/runtime_operator_handoff.md",
    "beadsSnapshot": "Runtime validation only. No Beads required. Target repo is disposable at $TARGET_REPO."
  }
}

After the workflow completes, run:

cd "$TARGET_REPO"
git log --oneline -5
git status --short
cat runtime_marker.txt
python - <<'PY'
from pathlib import Path
p = Path('runtime_marker.txt')
assert p.read_text(encoding='utf-8') == 'AIWK_RUNTIME_VALIDATED\\n'
print('marker content ok')
PY

Cleanup, when done:
  rm -rf "$TARGET_REPO" "$PROJECT_DIR"
EOF3
