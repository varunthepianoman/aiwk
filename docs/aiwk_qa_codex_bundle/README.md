# AIWK QA Codex Bundle

This bundle contains a Codex prompt and shell scripts for testing AIWK locally without launching expensive Claude runtime workflows.

## Files

```text
codex_prompt_run_aiwk_qa.md
scripts/00_run_all_local_qa.sh
scripts/01_local_unit_render_syntax.sh
scripts/02_gate_run_pass_and_fail.sh
scripts/03_context_pack_smoke.sh
scripts/04_template_smoke.sh
scripts/05_runtime_validation_prepare_request.sh
scripts/06_post_runtime_verify.sh
```

## Recommended use

1. Extract this zip.
2. Give `codex_prompt_run_aiwk_qa.md` to Codex.
3. Ask Codex to run:

```bash
bash scripts/00_run_all_local_qa.sh
```

4. If local QA passes, manually run the printed Claude Workflow runtime request.
5. After the runtime canary finishes, ask Codex to run:

```bash
bash scripts/06_post_runtime_verify.sh
```

## Environment variables

```bash
AIWK_ROOT=~/dev/aiwk
AIWK_PROJECTS_ROOT=~/dev/.aiwk
AIWK_PY=~/dev/aiwk/.venv/bin/python
AIWK_RUNTIME_CFG=~/dev/.aiwk/aiwk_runtime_validation/aiwk.yaml
AIWK_RUNTIME_TARGET=~/dev/aiwk_runtime_validation_target
AIWK_NODE=/path/to/node
```
