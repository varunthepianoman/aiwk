# Phase 04 — Checkpoint / continuation support for long-running agents

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

Reduce within-agent context bloat by supporting explicit checkpoints and fresh continuation agents.

The audit showed that durable handoffs help between agents, but not inside one long agent. A long Dev agent with many tool calls keeps accumulating transcript, and every post-tool model turn reuses a huge cached prefix. This phase adds workflow-level support and prompt policy for stopping, writing a handoff, and continuing with a fresh agent.

## Tasks

1. Add config/schema support for context checkpoints.

   Reasonable config shape:
   ```yaml
   context_economy:
     max_tool_calls_before_checkpoint: 30
     checkpoint_after_major_test_milestone: true
     require_handoff_before_checkpoint: true
   ```

   Keep defaults backward-compatible. If actual tool-call counting is not feasible in generated Claude Workflow JS, implement prompt-level soft enforcement now and document the limitation.

2. Add StructuredOutput status support for checkpointing, e.g.:
   ```json
   {
     "status": "checkpoint",
     "handoff_path": "...",
     "reason": "tool_call_budget | major_test_milestone | context_large | operator_requested",
     "remaining_work": ["..."],
     "continue_role": "dev",
     "continue_step": "SS1"
   }
   ```

3. Modify orchestrator/renderer behavior where feasible:
   - if an agent returns `status: checkpoint`, do not treat the step as failed;
   - launch or instruct operator to launch a fresh continuation agent for the same role/step with the checkpoint handoff path;
   - cap continuation attempts with an existing retry/cycle mechanism or a new safe limit.

4. Prompt policy for Dev/Discovery roles:
   - after 25–35 tool calls, or after one major compile/test milestone, write a durable handoff and stop/checkpoint;
   - do not keep doing broad discovery + implementation + debugging in one giant session;
   - long command output must be redirected to log files, with only summaries/tails returned.

5. Add generated instructions for bounded tool output:
   ```bash
   <long command> > /tmp/<step>_<name>.log 2>&1
   rc=$?
   echo "rc=$rc"
   tail -80 /tmp/<step>_<name>.log
   ```

6. Preserve quality:
   - checkpointing should not allow agents to skip tests or handoffs;
   - continuation agents must read checkpoint handoff first and targeted files second.

## Testing

Add/update tests for:
- config parsing defaults;
- prompts include checkpoint rules;
- StructuredOutput schema accepts `status: checkpoint`;
- rendered workflow handles or at least surfaces checkpoint status correctly;
- generated continuation instructions include handoff path.

Run:
```bash
python -m pytest -q
```

Render discovery-enabled and discovery-disabled sample workflows. Syntax-check generated JS:
```bash
node --check <generated_workflow>.js
```

## Report back

Report:
- whether checkpointing is hard-orchestrated or prompt-level only;
- config fields added;
- continuation behavior;
- tests and results;
- any limitations needing later runtime work.
