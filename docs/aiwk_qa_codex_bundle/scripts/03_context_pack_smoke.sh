#!/usr/bin/env bash
set -euo pipefail
AIWK_ROOT="${AIWK_ROOT:-$HOME/dev/aiwk}"
PY="${AIWK_PY:-$AIWK_ROOT/.venv/bin/python}"
CFG="${AIWK_RUNTIME_CFG:-$HOME/dev/.aiwk/aiwk_runtime_validation/aiwk.yaml}"
PROJECT_DIR="$(dirname "$CFG")"
echo "=== 03: context-pack smoke ==="
if [[ ! -f "$CFG" ]]; then echo "ERROR: missing runtime validation config: $CFG" >&2; exit 1; fi
cd "$AIWK_ROOT"
"$PY" -m aiwk context-pack --config "$CFG" --phase RUNTIME_SS0_DEV --step RUNTIME_SS0 --include-diff --max-diff-lines 80
CTX="$PROJECT_DIR/state/RUNTIME_SS0_DEV_context.json"; HANDOFF="$PROJECT_DIR/state/RUNTIME_SS0_DEV_handoff.md"
test -f "$CTX"; test -f "$HANDOFF"
echo "+ context JSON preview"
"$PY" -m json.tool "$CTX" | sed -n '1,220p'
echo "+ handoff preview"
sed -n '1,220p' "$HANDOFF"
"$PY" - "$CTX" <<'__PY__'
import json, sys
data=json.load(open(sys.argv[1]))
required=['project','phase','repo','branch','head','status_short','changed_files','diff_stat','next_agent_instructions']
missing=[k for k in required if k not in data]
assert not missing, (missing, data.keys())
print('context fields ok')
__PY__
echo "=== 03 PASS ==="
