#!/usr/bin/env bash
set -euo pipefail
AIWK_ROOT="${AIWK_ROOT:-$HOME/dev/aiwk}"
PY="${AIWK_PY:-$AIWK_ROOT/.venv/bin/python}"
find_node_checker() {
  if [[ -n "${AIWK_NODE:-}" ]]; then echo "$AIWK_NODE"; return 0; fi
  if command -v node >/dev/null 2>&1; then command -v node; return 0; fi
  if command -v nodejs >/dev/null 2>&1; then command -v nodejs; return 0; fi
  if [[ -x /usr/share/code/code ]]; then echo "/usr/share/code/code"; return 0; fi
  return 1
}
echo "=== 04: template smoke ==="
cd "$AIWK_ROOT"
"$PY" -m aiwk templates list
TMP="$(mktemp -d)"; echo "TMP=$TMP"
for template in generic ros2_refactor bugfix_redteam; do
  echo "== template $template =="
  mkdir -p "$TMP/repo_$template"
  cd "$TMP/repo_$template"
  git init
  git config user.email "test@example.com"
  git config user.name "Test User"
  echo hello > README.md
  git add README.md
  git commit -m init
  cd "$AIWK_ROOT"
  "$PY" -m aiwk init --project "demo_$template" --repo "$TMP/repo_$template" --workflow-folder "$TMP/.aiwk" --template "$template"
  "$PY" -m aiwk render claude-workflow --config "$TMP/.aiwk/demo_$template/aiwk.yaml"
  test -f "$TMP/.aiwk/demo_$template/workflow.yaml"
  test -f "$TMP/.aiwk/demo_$template/generated/demo_$template.claude_workflow.js"
  grep -E "objective_gates|commit:|mode:|stages:|steps:" "$TMP/.aiwk/demo_$template/workflow.yaml" | head -40 || true
done
if NODE_CHECKER="$(find_node_checker)"; then
  set +e; "$NODE_CHECKER" --check /dev/null >/tmp/aiwk_node_check_probe_templates.out 2>&1; probe_rc=$?; set -e
  if [[ "$probe_rc" -eq 0 ]]; then
    for js in "$TMP"/.aiwk/*/generated/*.js; do echo "== node check $js =="; "$NODE_CHECKER" --check "$js"; done
  else
    echo "WARNING: $NODE_CHECKER does not support --check; skipping template JS syntax checks."
  fi
else
  echo "WARNING: no node checker found; skipping template JS syntax checks."
fi
echo "=== 04 PASS ==="
