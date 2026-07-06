#!/usr/bin/env bash
set -euo pipefail
TARGET="${AIWK_RUNTIME_TARGET:-$HOME/dev/aiwk_runtime_validation_target}"
echo "=== 06: post-Claude-runtime verification ==="
if [[ ! -d "$TARGET/.git" ]]; then echo "ERROR: target is not a git repo: $TARGET" >&2; exit 1; fi
cd "$TARGET"
echo "+ git status --short"
STATUS="$(git status --short)"
printf '%s\n' "$STATUS"
if [[ -n "$STATUS" ]]; then echo "ERROR: expected clean git status after successful runtime validation." >&2; exit 1; fi
echo "+ git log --oneline -5"
git log --oneline -5
echo "+ runtime_marker.txt content"
cat runtime_marker.txt
python3 - <<'__PY__'
from pathlib import Path
p=Path('runtime_marker.txt')
assert p.read_text(encoding='utf-8') == 'AIWK_RUNTIME_VALIDATED\n'
print('marker content ok')
__PY__
echo "=== 06 PASS ==="
