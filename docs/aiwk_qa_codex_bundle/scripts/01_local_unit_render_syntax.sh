#!/usr/bin/env bash
set -euo pipefail
AIWK_ROOT="${AIWK_ROOT:-$HOME/dev/aiwk}"
AIWK_PROJECTS_ROOT="${AIWK_PROJECTS_ROOT:-$HOME/dev/.aiwk}"
PY="${AIWK_PY:-$AIWK_ROOT/.venv/bin/python}"
find_node_checker() {
  if [[ -n "${AIWK_NODE:-}" ]]; then echo "$AIWK_NODE"; return 0; fi
  if command -v node >/dev/null 2>&1; then command -v node; return 0; fi
  if command -v nodejs >/dev/null 2>&1; then command -v nodejs; return 0; fi
  if [[ -x /usr/share/code/code ]]; then echo "/usr/share/code/code"; return 0; fi
  return 1
}
echo "=== 01: unit tests, render all workflows, syntax/runtime marker checks ==="
cd "$AIWK_ROOT"
echo "+ $PY -m pytest -q"
"$PY" -m pytest -q
echo "+ render all workflows under $AIWK_PROJECTS_ROOT"
shopt -s nullglob
cfgs=("$AIWK_PROJECTS_ROOT"/*/aiwk.yaml)
if (( ${#cfgs[@]} == 0 )); then echo "ERROR: no aiwk.yaml files found under $AIWK_PROJECTS_ROOT" >&2; exit 1; fi
for cfg in "${cfgs[@]}"; do echo "== render $cfg =="; "$PY" -m aiwk render claude-workflow --config "$cfg"; done
echo "+ runtime-incompatible marker grep"
if grep -R -n -E "export default|process\.env|permissionMode|env:" "$AIWK_PROJECTS_ROOT"/*/generated/*.js; then
  echo "ERROR: runtime-incompatible marker found in generated JS" >&2; exit 1
fi
echo "OK: no known runtime-incompatible JS markers found"
echo "+ meta.name sanity"
grep -R -n -E "export const meta|name:" "$AIWK_PROJECTS_ROOT"/*/generated/*.js | head -80 || true
if NODE_CHECKER="$(find_node_checker)"; then
  echo "+ JS syntax check using: $NODE_CHECKER"
  set +e; "$NODE_CHECKER" --check /dev/null >/tmp/aiwk_node_check_probe.out 2>&1; probe_rc=$?; set -e
  if [[ "$probe_rc" -ne 0 ]]; then
    echo "WARNING: $NODE_CHECKER does not appear to support '--check'; skipping JS syntax checks."
    cat /tmp/aiwk_node_check_probe.out || true
  else
    for js in "$AIWK_PROJECTS_ROOT"/*/generated/*.js; do echo "== node check $js =="; "$NODE_CHECKER" --check "$js"; done
  fi
else
  echo "WARNING: no node/nodejs checker found; skipping JS syntax checks."
fi
echo "=== 01 PASS ==="
