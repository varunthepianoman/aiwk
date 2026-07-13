# Phase 00 — Baseline audit and implementation map

# Common context for all phases

You are editing the AIWK workflow tooling repo, not the robotics target repo.

Canonical paths Varun typically uses:
- AIWK repo: `/home/varunkamat/dev/aiwk`
- AIWK runtime/state root: `/home/varunkamat/dev/.aiwk`
- Example robotics repo/worktree: `/home/varunkamat/dev/t_robotics_abb_arci_v2_gofa`

Before changing code in any phase:
```bash
cd /home/varunkamat/dev/aiwk
pwd
git rev-parse --show-toplevel
git branch --show-current
git status --short --branch
sed -n '1,240p' README.md
```

Key audit findings motivating this work:
- Prior AIWK workflows had agent `handoff` strings in journal results, but no durable `state/handoffs/*.md` files and no concrete `handoff_path` passed to later agents.
- Later agents were launched with `Handoff path supplied by operator: (none)`, so they repeated broad repo discovery.
- Long Opus developer agents accumulated huge context and produced enormous `cache_read_input_tokens`, especially after many tool calls.
- A previous commit agent staged only explicit paths and left accepted files dirty. Varun now chooses commit policy Option A: review/gate must prove the tree is in-scope, then commit runs `git add -A`.

Global design target:
1. Durable handoff docs under `.aiwk/<project>/state/handoffs/`.
2. Structured outputs include `handoff_path` and machine-readable changed/dirty/test/gate metadata.
3. Downstream agents receive prior handoff paths and read them first.
4. Discovery agents are supported as first-class optional roles for broad repo discovery, producing a compact repo map handoff for Dev.
5. Context economy policy: handoff-first, targeted verification, bounded tool output, no broad rediscovery without stated cause, checkpoint long agents.
6. Mechanical commit Option A: `git status --short`, `git add -A`, `git commit -m "{step_id}: {step_title}"`, `git status --short`; fail if dirty afterward.

Phase execution rule:
- Work only on the phase described in this file.
- Run the phase's tests.
- If tests fail, make a reasonable fix and rerun.
- Stop only if tests still fail after you cannot make progress without design/operator input.
- Do not hand-edit generated workflow JS; update source/templates and rerender.


## Goal

Create a precise implementation map for adding durable handoffs, handoff propagation, Discovery agents, context-economy checkpoints, and mechanical-all commit hardening to AIWK.

This phase may add a small design note and test TODO scaffolding, but should avoid large behavior changes. The purpose is to prevent later phases from rediscovering the AIWK codebase repeatedly.

## Tasks

1. Inspect AIWK's current structure and identify:
   - workflow config/schema definitions;
   - renderer entry point(s), especially Claude Workflow JS generation;
   - role/agent prompt template construction;
   - StructuredOutput schema generation/validation;
   - journal/result handling;
   - gate evidence writing;
   - commit-agent implementation;
   - context-pack implementation;
   - existing tests and golden/snapshot tests.

2. Create or update a durable implementation note, preferably:
   - `docs/aiwk_handoff_context_economy_plan.md`
   If the repo has a different docs convention, follow it.

3. The note must include:
   - exact source files to modify in later phases;
   - exact tests to update/add;
   - current commit behavior;
   - current handoff behavior;
   - proposed new config/schema fields;
   - backward-compatibility strategy for existing AIWK projects;
   - known risks.

4. Add a small test fixture or documentation-only test if the project convention supports it, but do not force a large refactor in this phase.

## Required design decisions to record

- Durable handoff path shape:
  ```text
  <project_folder>/state/handoffs/<STEP>_<ROLE>_C<CYCLE>_<AGENT_ID>.md
  ```

- Non-gate/non-commit agents must return:
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

- Gate agents should return typed gate evidence paths.
- Commit agents may use a structured alternative, but do not need handoff docs.
- Commit policy Option A is the default target for `mechanical_all`.

## Testing

Run the fastest existing checks you discover, for example one of:
```bash
python -m pytest -q
pytest -q
uv run pytest -q
```

Also run any existing lint/typecheck commands documented in `README.md` or `pyproject.toml` if they are fast.

## Report back

Report:
- source files inspected;
- tests discovered;
- design note path;
- exact next phase files likely to change;
- test commands and results.
