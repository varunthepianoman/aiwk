# Phase 02 — Handoff propagation between agents

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

Make prior durable handoff paths flow into downstream agent prompts automatically.

This phase solves the audited issue where prompts said:
```text
Handoff path supplied by operator:
(none)
```
even after previous agents had produced handoff-like content.

## Tasks

1. Modify the workflow renderer/orchestrator so it tracks handoff outputs from prior agents within a step and across step phases.

2. Downstream prompts must include a section like:
   ```text
   Prior handoff paths:
   - <absolute path 1>
   - <absolute path 2>

   Read these first. Do not repeat broad repository discovery already summarized there unless the handoff is missing, stale, contradicted by source, or insufficient for the local task.
   ```

3. Replace `(none)` with actual prior paths when available.

4. Prompt policy:
   - Agents must read prior handoff paths before broad repo discovery.
   - Agents may do targeted source verification of files/symbols named in handoffs.
   - Broad grep/read sweeps require a stated reason.
   - If a handoff is contradicted by source/gates, source/gates win and the agent must explain the contradiction.

5. Gate agents:
   - include typed `evidence_path` and `log_path` in StructuredOutput;
   - reviewers and fix/dev agents receive latest gate evidence path(s) explicitly.

6. Reviewer prompts:
   - receive latest dev handoff, red-team handoff, and gate evidence path(s);
   - review from current diff + handoffs + gate evidence rather than rediscovering the whole repo.

7. Keep this phase focused on propagation. Discovery-agent support comes in Phase 03; checkpoint continuation comes in Phase 04.

## Testing

Add/update tests that simulate:
- Scope returns `handoff_path`; Dev prompt includes it.
- Dev returns `handoff_path`; Red Team/Review prompts include it.
- Gate returns `evidence_path`; Review prompt includes it.
- No prior handoff exists; prompt explicitly says none without crashing.
- Multiple prior handoffs are preserved in deterministic order.

Run:
```bash
python -m pytest -q
```

Render a sample workflow and inspect the generated prompt text or JS to confirm:
- no stale `(none)` when prior handoffs exist;
- `Prior handoff paths:` appears in downstream roles.

Syntax-check generated JS if applicable:
```bash
node --check <generated_workflow>.js
```

## Report back

Report:
- how handoff paths are stored/tracked;
- which prompts now receive prior paths;
- tests added/updated;
- render/syntax-check results.
