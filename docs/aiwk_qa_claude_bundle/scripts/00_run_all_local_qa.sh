#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "=== AIWK local QA bundle ==="
echo "Script dir: $SCRIPT_DIR"
echo
bash "$SCRIPT_DIR/01_local_unit_render_syntax.sh"
echo
bash "$SCRIPT_DIR/02_gate_run_pass_and_fail.sh"
echo
bash "$SCRIPT_DIR/03_context_pack_smoke.sh"
echo
bash "$SCRIPT_DIR/04_template_smoke.sh"
echo
bash "$SCRIPT_DIR/05_runtime_validation_prepare_request.sh"
echo
echo "=== LOCAL QA COMPLETE ==="
echo "No Claude runtime workflows were launched by this wrapper."
echo "Next: run the printed Claude runtime request manually if local QA passed."
