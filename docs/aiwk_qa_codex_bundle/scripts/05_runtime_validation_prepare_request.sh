#!/usr/bin/env bash
set -euo pipefail
AIWK_ROOT="${AIWK_ROOT:-$HOME/dev/aiwk}"
SETUP="${AIWK_RUNTIME_SETUP:-$AIWK_ROOT/testing_infra/aiwk_runtime_validation_setup.sh}"
PROJECT_DIR="${AIWK_RUNTIME_PROJECT:-$HOME/dev/.aiwk/aiwk_runtime_validation}"
TARGET="${AIWK_RUNTIME_TARGET:-$HOME/dev/aiwk_runtime_validation_target}"
SCRIPT="$PROJECT_DIR/generated/aiwk_runtime_validation.claude_workflow.js"
echo "=== 05: prepare disposable runtime validation and print Claude request ==="
if [[ -f "$SETUP" ]]; then echo "+ running setup: $SETUP"; bash "$SETUP"; else echo "WARNING: setup script not found: $SETUP"; echo "Assuming existing runtime validation project/target are present."; fi
if [[ ! -f "$SCRIPT" ]]; then echo "ERROR: generated runtime validation workflow not found: $SCRIPT" >&2; exit 1; fi
cat <<EOF

=== Claude Workflow runtime request ===
{
  "scriptPath": "$SCRIPT",
  "args": {
    "stage": "build",
    "onlyStep": "RUNTIME_SS0",
    "preflightSummary": "Use $PROJECT_DIR/state/runtime_preflight.json. This is a disposable runtime validation; do not run broad repo discovery unless needed.",
    "handoffPath": "$PROJECT_DIR/state/runtime_operator_handoff.md",
    "beadsSnapshot": "Runtime validation only. No Beads required. Target repo is disposable at $TARGET."
  }
}
EOF
echo
echo "This script did not launch Claude runtime. Paste the JSON above into the Workflow tool manually."
echo "After it completes, run: bash scripts/06_post_runtime_verify.sh"
echo "=== 05 PASS ==="
