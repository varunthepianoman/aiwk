# Phase 06 — End-to-end integration, docs, examples, and migration guidance

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

Integrate the new handoff/context/discovery/checkpoint/commit features into a coherent AIWK user workflow and update docs/examples so Varun can use them on ABB ARCI v2 workflows.

## Tasks

1. Update README/docs with:
   - durable handoff behavior;
   - `handoff_path` and `state/handoffs`;
   - handoff-first / targeted verification / no broad rediscovery policy;
   - Discovery agents and when to enable them;
   - checkpoint/continuation behavior and limitations;
   - bounded tool-output/logging policy;
   - mechanical_all Option A commit behavior;
   - launch examples using `handoffPath`.

2. Add or update example workflow config(s):
   - simple workflow without Discovery;
   - complex workflow with Discovery enabled;
   - context economy config;
   - mechanical_all commit config.

3. Add migration notes for existing `.aiwk` projects:
   - old workflows still render;
   - how to enable Discovery;
   - how to add context economy fields;
   - how to interpret `handoff_path`;
   - how to launch a continuation with handoff path.

4. Add end-to-end render tests:
   - a workflow with Discovery enabled;
   - a workflow without Discovery;
   - a workflow using `mechanical_all`;
   - a workflow with checkpoint output schema.
   Confirm generated JS syntax-checks if JS is generated during tests.

5. Add a final smoke command sequence for operators:
   ```bash
   CFG=/home/varunkamat/dev/.aiwk/<project>/aiwk.yaml
   /home/varunkamat/dev/aiwk/.venv/bin/aiwk preflight --config "$CFG"
   /home/varunkamat/dev/aiwk/.venv/bin/aiwk render claude-workflow --config "$CFG"
   node --check /home/varunkamat/dev/.aiwk/<project>/generated/<project>.claude_workflow.js
   ```

6. Do not modify robotics project files. This phase is AIWK docs/examples/tests only unless AIWK tests require temporary fixtures.

## Final testing

Run the broadest reasonable local suite:
```bash
python -m pytest -q
```

Run any documented lint/type checks that are reasonably fast.

Run render smoke tests for at least one example/scratch AIWK project.

Run `node --check` on generated Claude Workflow JS from a sample.

Check git:
```bash
git status --short --branch
```

## Report back

Report:
- docs/examples updated;
- end-to-end tests added;
- full test results;
- any known limitations;
- exact recommended config snippet for enabling Discovery + context economy + mechanical_all.
