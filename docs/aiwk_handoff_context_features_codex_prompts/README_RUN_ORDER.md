# AIWK handoff/context-economy Codex prompt bundle

Run these prompts in order, one phase at a time, against the AIWK repo:

1. `phase_00_baseline_audit_and_map.md`
2. `phase_01_durable_handoff_artifacts.md`
3. `phase_02_handoff_propagation.md`
4. `phase_03_discovery_agents_context_policy.md`
5. `phase_04_checkpoint_continuation.md`
6. `phase_05_mechanical_commit_option_a.md`
7. `phase_06_integration_docs_examples.md`

Each file contains one paste-ready Codex prompt.

Operating rule:
- Give Codex one phase prompt.
- Let it work, test, fix, and report.
- Continue to the next phase only after tests pass or after you accept a documented limitation.
- Stop if tests fail and Codex cannot fix without design/operator input.

Intent:
- Durable handoffs under `.aiwk/<project>/state/handoffs/`.
- Concrete `handoff_path` in StructuredOutput and downstream prompts.
- Optional Discovery agents before Dev.
- Context economy / no broad rediscovery by default.
- Checkpoint/continuation support for long agents.
- Mechanical commit Option A: review/gate proves tree safe, then `git add -A`.
