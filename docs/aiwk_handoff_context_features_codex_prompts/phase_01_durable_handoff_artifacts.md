# Phase 01 — Durable handoff artifacts and StructuredOutput schema

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

Implement durable per-agent handoff documents and add `handoff_path` plus handoff metadata to non-gate/non-commit StructuredOutput.

This phase solves the core audited problem: result handoff strings existed, but no durable `state/handoffs/*.md` files or concrete `handoff_path` values were created.

## Tasks

1. Add a reusable handoff path/rendering mechanism:
   - directory: `<project_folder>/state/handoffs/`
   - filename: `<STEP>_<ROLE>_C<CYCLE>_<AGENT_ID>.md`
   - sanitize path components safely.
   - ensure directory creation is included in rendered workflow/runtime.

2. Add a standard markdown handoff template with these sections:
   ```markdown
   # Handoff: <STEP> <ROLE> cycle <N>

   ## Verdict
   - status:
   - short verdict:

   ## Scope
   - allowed scope executed:
   - explicitly avoided non-goals:

   ## Files changed / inspected
   ### Changed
   - <path> — <why>

   ### Inspected but not changed
   - <path> — <why>

   ## Tests / gates run
   - command:
   - rc:
   - result:
   - evidence path:

   ## Findings closed
   - <finding id/name> — <resolution>

   ## Remaining findings / risks
   - <severity> <description> <recommended next action>

   ## Exact accepted paths / dirty tree
   - changed paths:
   - known dirty paths:
   - must be clean after commit:

   ## Next agent instructions
   - read this first;
   - do not rediscover:
   - focus on:
   - rerun only if:
   ```

3. Update non-gate/non-commit role prompts so each agent must:
   - write the handoff markdown file before returning;
   - include `handoff_path` in StructuredOutput;
   - include `files_changed`, `files_inspected`, `tests_run`, `gate_evidence_paths`, `known_dirty_paths`, `next_agent_should_read`;
   - fail/return incomplete if it cannot write the handoff.

4. Preserve backward compatibility:
   - existing workflows without the new fields should still render where possible;
   - generated prompts can require the new fields for new renderer output.

5. Do not implement handoff propagation between agents yet; Phase 02 will do that. This phase only makes agents produce durable handoff files and schema fields.

## Testing

Add or update unit/golden tests that verify:
- rendered prompts mention `state/handoffs`;
- rendered StructuredOutput schemas include `handoff_path`;
- gate/commit roles are exempt or have their structured alternative;
- legacy simple workflows still render.

Run:
```bash
python -m pytest -q
```
or the repo's documented equivalent.

Render at least one small sample workflow if the repo has fixtures/examples. Syntax-check any generated Claude Workflow JS if applicable:
```bash
node --check <generated_workflow>.js
```

## Report back

Report:
- files changed;
- schema fields added;
- handoff path format;
- tests added/updated;
- test results.
