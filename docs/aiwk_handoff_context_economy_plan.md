# AIWK handoff/context-economy implementation map

This note records the implementation map for durable per-agent handoffs, handoff propagation, Discovery agents, checkpoint guidance, and mechanical-all commit hardening.

The direct audit input for these choices is:

- `docs/workflow_audit_handoff_ur_adapter_migrate_to_dataloop.md`

That audit examined the `ur_adapter_migrate_to_dataloop` workflow and found three core failure modes:

1. accepted worktree state was not fully captured by explicit-path commit staging;
2. agent handoffs existed mostly as journal strings, not durable `state/handoffs/*.md` files passed by path;
3. long Opus agents accumulated huge cached prefixes and drove very large `cache_read_input_tokens`.

## Source files

- `aiwk/workflow_spec.py`: provider-neutral schema, YAML-subset parsing, validation, `DiscoveryConfig`, and `ContextEconomyConfig`.
- `aiwk/renderers/claude_workflow.py`: Claude Workflow JS generation, role prompts, structured-output schemas, retry loops, gate/review routing, handoff propagation, checkpoint surfacing, and commit-agent prompts.
- `aiwk/cli.py`: project scaffolding, including `state/handoffs/`.
- `aiwk/render.py`: render-time directory preparation for existing projects.
- `aiwk/context_pack.py`: operator-created context packs; separate from per-agent handoffs.
- `aiwk/gate_runner.py`: deterministic objective gate evidence/log writing.
- `aiwk/checkpoint.py`: standalone mechanical checkpoint commit utility; separate from generated workflow commit policy.

## Tests

- `tests/test_workflow_spec.py`: schema parsing/validation for objective gates, commit, Beads, Discovery, and context economy.
- `tests/test_render_claude_workflow.py`: generated JS markers, runtime compatibility constraints, mature routing, objective gate enforcement, handoff propagation, Discovery, checkpoint policy, and commit prompt semantics.
- `tests/test_paths.py`: generated project folder structure, including `state/handoffs/`.
- Existing command/config/gate/template/coordinator tests remain relevant regression coverage.

## Durable handoff shape

Generated non-gate/non-commit agents are instructed to write:

```text
<project_folder>/state/handoffs/<STEP>_<ROLE>_C<CYCLE>_<AGENT_ID>.md
```

Path components are sanitized in generated JS with a conservative `[A-Za-z0-9_.-]` allowlist.

## Non-gate/non-commit structured output

Generated schemas require:

```json
{
  "handoff_path": "...",
  "files_changed": [],
  "files_inspected": [],
  "tests_run": [],
  "gate_evidence_paths": [],
  "known_dirty_paths": [],
  "next_agent_should_read": []
}
```

Gate agents return typed `evidence_path` and `log_path`. Commit agents return `COMMIT_SCHEMA` and do not write handoff docs.

## Current commit behavior

`mechanical_all` is Option A:

```bash
git status --short
git add -A
git commit -m "{step_id}: {step_title}"
git status --short
```

The commit role is intentionally mechanical and low-effort. Review/gate must prove that `git add -A` is safe before commit. Generated routing fails if the final status is dirty.

The audit suggested machine-checkable accepted paths as one possible repair. AIWK currently follows Varun's later Option A decision instead: move intelligence into preflight/review/gate, require them to reject unrelated dirtiness, then let commit mechanically stage all changes and fail if dirty afterward. This avoids the specific audit failure where narrative/test-name bullets did not map cleanly to all accepted files.

## Current handoff behavior

- Operator handoff comes in through runtime `handoffPath`.
- Each Scope/Discovery/Dev/Red Team/Review output must include `handoff_path`.
- The generated workflow stores prior handoff paths in deterministic order and injects them into downstream prompts.
- Gate evidence/log paths are tracked separately and injected into review/fix prompts.
- Handoffs are treated as durable guidance; committed source, specs, and objective gate evidence win on contradiction.

## New config fields

```yaml
discovery:
  enabled: true
  model: opus
  effort: high

context_economy:
  max_tool_calls_before_checkpoint: 30
  checkpoint_after_major_test_milestone: true
  require_handoff_before_checkpoint: true
```

Steps may override Discovery:

```yaml
steps:
  - id: SS1
    discovery:
      enabled: true
      model: opus
      effort: high
```

An explicit `discovery` phase also enables Discovery for that step.

## Backward compatibility

- Workflows without `discovery` or `context_economy` parse and render with defaults.
- Discovery is disabled by default.
- Existing objective gate, commit, Beads, `onlyStep`, `fromStep`, `preflightSummary`, `handoffPath`, and `beadsSnapshot` behavior is preserved.
- Existing projects missing `state/handoffs/` are repaired by render-time directory creation; generated prompts also instruct agents to create it.

## Checkpoint limitation

Generated JS cannot reliably count model-internal tool calls. Checkpointing is prompt-level plus structured surfacing: long agents are told to write a handoff and return `status: "checkpoint"`, and the workflow returns a structured `checkpoint_requested` halt for the operator to continue with a fresh agent using that handoff.

## Audit traceability

| Audit finding | Current AIWK response | Status |
| --- | --- | --- |
| No durable per-agent handoff files were written. | Generated non-gate/non-commit prompts require a concrete `state/handoffs/<STEP>_<ROLE>_C<CYCLE>_<AGENT_ID>.md` file and `handoff_path` in structured output. | Implemented. |
| Later agents saw `Handoff path supplied by operator: (none)`. | Generated workflow tracks prior `handoff_path` values and injects `Prior handoff paths:` into downstream prompts. | Implemented. |
| Gate evidence existed but was not always passed as typed downstream input. | Generated workflow tracks `evidence_path`/`log_path` and includes latest gate evidence paths in review/fix prompts. | Implemented. |
| Explicit-path commit staging missed accepted files. | `mechanical_all` now uses `git add -A` only after review/gate acceptance and requires clean final status. | Implemented as Option A, not audit's exact-path alternative. |
| Long developer agents caused huge cache reads. | Context-economy prompts require handoff-first work, bounded output, and checkpoint status after large tool/test milestones. | Prompt-level implemented; hard tool-call counting remains unsupported. |
| Full specs were re-inlined repeatedly. | Current renderer still embeds durable spec/invariant/gate contents in generated JS and prompts agents to read durable paths. | Not fully solved; future pass can move to path + excerpt/minimized context mode. |

## Risks

- Provider runtimes must honor the JSON schemas and allow agents to write files under the AIWK project folder.
- Handoff existence is requested and `handoff_path` is enforced structurally, but generated JS does not verify filesystem contents.
- Broad Discovery still costs tokens; enable it for large/ambiguous work, not every tiny task.
- `mechanical_all` is safe only in isolated worktrees with strong preflight/review discipline.
