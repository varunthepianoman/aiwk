#!/usr/bin/env bash
set -euo pipefail
AIWK_ROOT="${AIWK_ROOT:-$HOME/dev/aiwk}"
PY="${AIWK_PY:-$AIWK_ROOT/.venv/bin/python}"
CFG="${AIWK_RUNTIME_CFG:-$HOME/dev/.aiwk/aiwk_runtime_validation/aiwk.yaml}"
TARGET="${AIWK_RUNTIME_TARGET:-$HOME/dev/aiwk_runtime_validation_target}"
echo "=== 02: direct gate-run pass/fail QA ==="
if [[ ! -f "$CFG" ]]; then echo "ERROR: missing runtime validation config: $CFG" >&2; exit 1; fi
if [[ ! -d "$TARGET" ]]; then echo "ERROR: missing runtime validation target: $TARGET" >&2; exit 1; fi
cd "$AIWK_ROOT"
PASS_JSON="$(mktemp)"; FAIL_JSON="$(mktemp)"
echo "+ direct passing gate-run"
"$PY" -m aiwk gate-run --config "$CFG" --gate default --step RUNTIME_SS0 --attempt 901 --repo "$TARGET" | tee "$PASS_JSON"
"$PY" - "$PASS_JSON" <<'__PY__'
import json, sys
data=json.load(open(sys.argv[1]))
assert data.get('status')=='ok', data
assert data.get('gate_clean') is True, data
for k in ['setup_rc','build_rc','test_rc','result_rc','evidence_path','log_path']:
    assert k in data, (k,data)
print('PASS gate-run JSON ok')
print('evidence_path=', data['evidence_path'])
print('log_path=', data['log_path'])
__PY__
cd "$TARGET"
trap 'rm -f "$TARGET/forbidden_marker.txt"' EXIT
echo "FORBIDDEN_MARKER" > forbidden_marker.txt
echo "+ direct failing gate-run via FORBIDDEN_MARKER"
cd "$AIWK_ROOT"
"$PY" -m aiwk gate-run --config "$CFG" --gate default --step RUNTIME_SS0 --attempt 902 --repo "$TARGET" | tee "$FAIL_JSON"
"$PY" - "$FAIL_JSON" <<'__PY__'
import json, sys
data=json.load(open(sys.argv[1]))
assert data.get('status')=='ok', data
assert data.get('gate_clean') is False, data
checks=data.get('check_results') or []
assert checks, data
assert any(c.get('count',0) > c.get('max_count',0) for c in checks), data
print('FAIL gate-run correctly returned gate_clean=false')
print('evidence_path=', data['evidence_path'])
print('log_path=', data['log_path'])
__PY__
rm -f "$TARGET/forbidden_marker.txt"
trap - EXIT
cd "$TARGET"
echo "+ target status after cleanup"
git status --short || true
echo "=== 02 PASS ==="
