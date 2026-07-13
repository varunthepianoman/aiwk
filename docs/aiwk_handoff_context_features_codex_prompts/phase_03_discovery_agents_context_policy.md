# Phase 03 — First-class Discovery agents and context-economy prompt policy

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

Add optional first-class Discovery agents for broad repo discovery, so Dev agents can start from a compact repo map instead of rediscovering the repository from scratch.

Discovery agents are intended for complex steps and should run after Scope and before Dev when enabled.

Target sequence when discovery is enabled:
```text
Scope → Discovery → Dev → Red Team → Gate → Review → Commit
```

Default sequence may remain unchanged for simple steps:
```text
Scope → Dev → Red Team → Gate → Review → Commit
```

## Tasks

1. Add config/schema support for Discovery agents.

   Use the repo's existing style. Reasonable shapes include one of:
   ```yaml
   discovery:
     enabled: true
     model: opus
     effort: high
   ```
   or per-step:
   ```yaml
   steps:
     - id: SS1
       discovery:
         enabled: true
   ```

   Preserve backward compatibility: workflows without discovery config render as before.

2. Add a Discovery role prompt template.

   Discovery agent responsibilities:
   - read supplied handoffs first;
   - perform broad but bounded repo/source discovery;
   - identify exact files/symbols/tests likely relevant to the step;
   - produce a compact repo map handoff;
   - avoid editing production code unless explicitly allowed by the phase;
   - write durable handoff under `state/handoffs`;
   - tell Dev what NOT to rediscover.

3. Add context-economy prompt policy to all non-commit roles:
   ```text
   Context economy rule:
   - Read supplied handoff(s) first.
   - Do not redo broad repository discovery already summarized there.
   - Use targeted reads of named files/symbols for grounding before edits/review.
   - Broad grep/find/read sweeps are allowed only if the handoff is missing, stale, contradicted, or insufficient; state the reason.
   - Batch shell discovery when possible.
   - Redirect long test/build output to logs and print summaries/tails.
   ```

4. Dev prompt must explicitly say:
   - Discovery did the broad map if a Discovery handoff exists;
   - Dev should target named files/symbols and avoid global rediscovery by default;
   - Dev may verify source locally before edits.

5. Red Team/Review prompts must:
   - start from diff, dev handoff, gate evidence;
   - use targeted verification;
   - only rediscover broadly when necessary.

6. Update docs/examples to explain when to enable Discovery:
   - large migration/refactor;
   - unfamiliar package boundary;
   - many possible files;
   - expensive broad grep/read would otherwise be repeated by several agents.

## Testing

Add/update tests that verify:
- workflow without discovery renders old sequence.
- workflow with discovery renders Scope → Discovery → Dev.
- Discovery prompt includes durable handoff requirement and context-economy policy.
- Dev prompt receives Discovery handoff path and says not to redo broad discovery.
- rendered JS syntax-checks.

Run:
```bash
python -m pytest -q
```

Render a sample with discovery enabled. Syntax-check generated JS:
```bash
node --check <generated_workflow>.js
```

## Report back

Report:
- config shape implemented;
- default/backward compatibility behavior;
- generated role sequence with discovery enabled;
- tests and results.
