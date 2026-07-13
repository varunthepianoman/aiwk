# Phase 05 — Mechanical commit Option A and dirty-tree protections

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

Make `mechanical_all` commit behavior match Varun's preferred Option A:

```bash
git status --short
git add -A
git commit -m "{step_id}: {step_title}"
git status --short
```

The commit agent should be small/low-effort and mechanical. Intelligence belongs in gates/review before commit.

## Tasks

1. Inspect current commit modes. Preserve existing public config names where possible:
   - `none`
   - `mechanical_all`
   - any existing `mechanical_paths` or explicit-path mode, if already supported.

2. For `mechanical_all`, ensure rendered commit behavior:
   - runs `git status --short` before commit;
   - runs `git add -A`;
   - commits with configured message template, default:
     ```text
     {step_id}: {step_title}
     ```
   - records commit hash with `git rev-parse HEAD`;
   - runs `git status --short` after commit;
   - fails if the final status is not clean;
   - reports `clean_after: true/false`.

3. Commit agent prompt:
   - use low-effort/Sonnet if workflow model config supports it;
   - do not infer file paths;
   - do not rewrite commit messages creatively;
   - do not selectively stage;
   - do not commit if review/gate failed;
   - fail loudly if dirty after commit.

4. Review/gate prompt protections:
   - reviewers must reject unrelated dirty files before commit;
   - gate/review must confirm that `git add -A` is safe because the tree contains only accepted in-scope changes;
   - if unrelated dirty files exist, stop before commit.

5. Keep optional `accepted_paths_to_commit` metadata as review information if useful, but `mechanical_all` must not depend on explicit path lists.

6. Add docs explaining why:
   - previous explicit-path commit staging left accepted files uncommitted;
   - mechanical_all is safe only because review/gate enforce scope first.

## Testing

Add/update tests verifying rendered commit script/prompt contains:
- `git status --short`;
- `git add -A`;
- `git commit -m`;
- post-commit `git status --short`;
- dirty-after failure.

Add a unit test or fixture simulating commit output if the repo has runtime tests.

Run:
```bash
python -m pytest -q
```

Render a sample workflow with `commit.mode: mechanical_all` and inspect/snapshot the commit section.

Syntax-check generated JS:
```bash
node --check <generated_workflow>.js
```

## Report back

Report:
- final `mechanical_all` semantics;
- commit message template;
- dirty-tree failure behavior;
- tests and results.
