# Codex Prompt: Run AIWK Local QA Without Burning Claude Runtime Tokens

You are working in the user's AIWK development environment.

Primary paths:

```text
~/dev/aiwk                         # AIWK source repo
~/dev/.aiwk                        # AIWK workflow project folders / generated workflows
~/dev/aiwk_runtime_validation_target # disposable runtime-validation target repo
```

Goal: Run the local AIWK QA suite for the fully implemented remaining passes, without launching expensive Claude Workflow runtime jobs unless explicitly asked.

This is a QA task, not an implementation task.

## Important constraints

- Do not edit `~/dev/t_robotics` source.
- Do not run any real robotics Claude Workflow.
- Do not launch Claude runtime workflows from this prompt.
- Do not modify AIWK source unless a test failure is obviously caused by a trivial local QA script issue and you explain it.
- Prefer running the attached shell scripts as-is.
- If a script fails, stop and report the exact command/output and your diagnosis.
- Do not keep thrashing indefinitely.
- Do not spend tokens reading large generated workflows unless a targeted grep/sed check fails.

## What to run

From the extracted bundle root, run:

```bash
bash scripts/00_run_all_local_qa.sh
```

That wrapper runs local checks only and prints the Claude runtime request. It does **not** launch a Claude runtime workflow.

After the user manually runs the Claude runtime canary, they may ask you to run:

```bash
bash scripts/06_post_runtime_verify.sh
```

## Expected local pass criteria

The local QA passes if:

```text
- pytest passes
- all ~/dev/.aiwk workflows render
- all generated JS files pass syntax check, or syntax check is skipped only because no Node-compatible checker is available
- generated workflows do not contain known runtime-incompatible markers:
  export default
  process.env
  permissionMode
  env:
- direct gate-run pass case returns gate_clean true
- direct gate-run fail case returns gate_clean false when FORBIDDEN_MARKER is present
- context-pack writes useful context JSON and handoff markdown
- templates list/init/render correctly for generic, ros2_refactor, and bugfix_redteam
- runtime validation setup prints a Claude Workflow request for RUNTIME_SS0
```

## Report format

When done, report exactly:

```text
Local QA summary:
Scripts run:
Passed:
Failed:
Skipped:
Evidence/log paths:
Runtime validation request:
Recommended next action:
```

Do not claim Claude runtime success unless the user separately ran the runtime workflow and provided its result.
