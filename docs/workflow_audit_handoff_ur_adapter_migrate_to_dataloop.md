# Workflow Audit Handoff: `ur_adapter_migrate_to_dataloop`

**Prepared for:** Varun  
**Source artifact audited:** `/mnt/data/_current_workflow_log.zip`  
**Extracted log root:** `_current_workflow_log/`  
**Audit focus:** workflow correctness, final commit integrity, AIWK/handoff behavior, and token/cache-read explosion  
**Important limitation:** this audit used the uploaded agent logs and journal only. I did not inspect the live repository checkout. Any statement about the final code state is therefore based on logged agent reports, gate outputs, and commit-agent status summaries.

---

## 1. Executive summary

The workflow under audit is **`ur_adapter_migrate_to_dataloop`**, whose purpose was to migrate `ur_arci_adapter` away from the deprecated `HandshakeExecutor` / `DriverInterface` polling compatibility shim and onto the new `dataloop::GoalExecutor` + `dataloop::HandshakeStateMachine` data-loop-driven architecture.

The overall workflow appears to have reached a valid architectural endpoint according to the logged reviewers and objective gates:

- **SS0** created and hardened a scoping/source-text oracle.
- **SS1** migrated the live UR adapter handshake path to `GoalExecutor` + data-loop `HandshakeStateMachine` ticking.
- **SS2** cleaned up stale UR references, preserved the deprecated shim boundary, and passed package gates.
- The final SS2 reviewer accepted the state with objective gate success: `setup_rc=0 build_rc=0 test_rc=0 result_rc=0`, all grep checks clean, `53/53` UR tests passing, and `2310` total tests with `0` failures.

However, there is a serious **commit-integrity problem** at the end:

- The final SS2 commit agent created commit `e72de7e32`, but staged only **2 files**.
- The accepted SS2 worktree still had **5 additional accepted/related paths** modified or untracked afterward.
- Therefore, the commit likely does **not** represent the exact state that passed the final reviewer/gate.

This is separate from the question of whether the code was correct at the time of review. The logged evidence suggests the reviewed worktree was accepted; the problem is that the accepted state was not fully captured in git.

The AIWK/handoff mechanism also did **not** operate in the strong form you intended. Agents produced handoff text in journal results and sometimes Beads memories, and AIWK gate artifacts were created under `state/gates/`, but there was no evidence that agents wrote durable per-step AIWK handoff documents or passed concrete `handoff_path` values to later agents.

The enormous `cache_read_input_tokens` count is mostly explained by long-running Opus agents with large cached prefixes and many tool-call round trips. AIWK handoffs, as implemented in this run, did not materially reduce that because the handoffs were not used as compact durable inputs to fresh agents.

---

## 2. Uploaded log inventory

The zip contained:

| Item | Count / value |
|---|---:|
| Agent `.jsonl` logs | 42 |
| Agent `.meta.json` files | 42 |
| Journal file | 1 |
| Journal entries | 84 |
| `started` entries | 42 |
| `result` entries | 42 |
| Result entries with a `handoff` field | 30 |

Correction from the earlier quick read: the parsed journal shows **30**, not 32, result entries with a top-level `handoff` field.

---

## 3. Workflow intent and boundaries

The root prompts describe the project as:

```text
Project: ur_adapter_migrate_to_dataloop
Repository: /workspaces/t_robotics
AIWK project folder: /workspaces/.aiwk/ur_adapter_migrate_to_dataloop
Project spec path: /workspaces/.aiwk/ur_adapter_migrate_to_dataloop/spec/project.spec.md
Invariants path: /workspaces/.aiwk/ur_adapter_migrate_to_dataloop/spec/invariants.yaml
Gates path: /workspaces/.aiwk/ur_adapter_migrate_to_dataloop/spec/gates.yaml
State/handoff directory: /workspaces/.aiwk/ur_adapter_migrate_to_dataloop/state
```

The required flow was:

```text
ExecuteProcedure goal
→ GoalExecutor::execute
→ HandshakeStateMachine::set_request
→ UR data loop reads freshest dispatcher_state
→ sm.tick(dispatcher_state)
→ TickResult::request_to_write
→ existing control-plane rpc_id/reset write
→ goal thread wait_for_change
→ terminal state maps to existing action result
```

The explicit non-goals were important and were generally enforced by the workflow:

- no `DataPlaneTcpServer` / socket lifecycle work;
- no `DataPlaneTcpSession::transfer_parameters` / socket RPC_ARGS transfer;
- no RPC 910/911/912 echo wiring;
- no `RPC_RETURN`;
- no params-valid bits, payload registers, register fallback, or echo-register authoritative observables;
- no live URSim destructive execution;
- no branch restacking/rebasing.

---

## 4. Stage-by-stage findings

### 4.1 SS0 — scoping oracle

SS0 created a black-box/source-text oracle for the migration contract without production migration.

Observed sequence:

1. Initial SS0 oracle written and registered in `ur_arci_adapter/CMakeLists.txt`.
2. Red Team cycle 1 found adversarial issues in the oracle.
3. Dev hardened the oracle and converted red-team cases into green regression guards.
4. Red Team cycle 2 found over-fit pinning problems: false-REDs and false-GREENs relative to the intended architecture.
5. Dev cycle 3 resolved this by **removing/re-scoping several semantic source-text pins** rather than hardening them further. The key properties were moved to SS1 behavioral acceptance.
6. Red Team cycle 3 accepted the rescoped SS0 oracle.
7. An early objective gate attempt failed due to environment/tooling (`No module named aiwk`) rather than repo code.
8. A reviewer initially withheld acceptance due to dirty `.devcontainer/Dockerfile` risk and missing valid gate output.
9. A dev pass reverted/excluded the dirty Dockerfile issue and a later gate passed.
10. SS0 was committed cleanly as `becee3143`.

Key SS0 conclusion: the workflow correctly avoided overfitting SS0 into a brittle semantic source-text oracle. The binding operator decision to move five semantic migration-contract properties into SS1 behavioral tests appears to have been followed.

### 4.2 SS1 — live UR adapter migration

SS1 performed the actual migration of the live UR adapter execution path.

Observed sequence:

1. A behavioral acceptance suite was written to verify the five properties moved out of SS0:
   - `ExecuteProcedure` delegates to `GoalExecutor::execute`;
   - adapter owns the data-loop `HandshakeStateMachine`;
   - data loop ticks it with freshest `dispatcher_state`;
   - `TickResult::request_to_write` commits exactly once through existing write path;
   - `dataloop::ExecutionResult` maps to `ReturnCode` correctly.
2. Main developer agent migrated production code off the deprecated shim and onto the `GoalExecutor` / `HandshakeStateMachine` path.
3. Red team accepted the migration as faithful and gate-green.
4. Reviewer attempt 2 found that behavioral tests were too close to a reimplementation/copy rather than driving the real migrated seam.
5. Dev extracted/shared a minimal seam in `dispatcher_data_loop_step.hpp` so tests and production used the same tick+commit logic without hot-loop allocation/indirection.
6. Subsequent gates and reviewers accepted the SS1 architecture.
7. A later gate failed again due to the stale `aiwk` environment (`No module named aiwk`), with a binding operator note that this was an environment fault. A verification agent confirmed the reviewed SS1 migration was still intact.
8. Final SS1 gate passed.
9. The first SS1 commit agent skipped because the task referenced test names rather than explicit file paths.
10. The next SS1 commit agent committed `a435ae9da`, but left `dispatcher_data_loop_step.hpp` untracked because it was not in the explicit stage list.

Key SS1 conclusion: the architecture was eventually accepted, but the commit process already showed the same class of brittleness that caused the final SS2 commit issue: the safe-commit agent stages only explicit filesystem paths and may mis-handle accepted changes if the handoff/task describes test names, concepts, or bullets instead of complete paths.

### 4.3 SS2 — cleanup, shim boundary, package gate

SS2 cleaned up stale UR references while preserving the deprecated shim boundary and non-goal boundaries.

Observed sequence:

1. SS2 scoping artifact/spec was written with 7 tests.
2. Cleanup dev made the SS2 oracle pass 7/7 and removed live UR consumers of deprecated shim pieces.
3. Red Team cycle 1 found two oracle defects.
4. Dev hardened the SS2 cleanup oracle.
5. Red Team cycle 2 found two more defects:
   - `F-TRANSFERTOKEN` around weak transfer token guarding;
   - `G-FILELIST` around incomplete file enumeration / test registration weakness.
6. Dev fixed both cycle-2 findings.
7. Red Team cycle 3 passed.
8. First SS2 objective gate failed with `result_rc=1` and `gate_clean=false` due to a scope-clean issue: a banned `transfer_parameters(` token appeared in a production header comment, plus a package/test issue.
9. Reviewer rejected because the objective gate was red.
10. Dev fixed both blockers:
    - reworded the WOU-seam doc comment in `dispatcher_data_loop_step.hpp` to remove the banned token;
    - filed tracking bead `t_robotics-465` for a pre-existing flaky `test_signal_publisher.DeactivateStopsHeartbeat` race so the package exception applied.
11. Second SS2 gate passed cleanly.
12. Final SS2 reviewer accepted.

Final reviewer acceptance included:

```text
setup_rc=0 build_rc=0 test_rc=0 result_rc=0
all four grep checks count=0
53/53 UR tests pass
2310 total tests 0 failures
```

Key SS2 conclusion: the logged gate/reviewer path supports acceptance of the worktree at review time, but the final commit did not capture the full accepted state.

---

## 5. Final commit-integrity issue

The final commit agent reported:

```text
commit_hash: e72de7e32
clean_after: false
```

It staged and committed only:

```text
ur_arci_adapter/include/ur_arci_adapter/dispatcher_data_loop_step.hpp
ur_arci_adapter/test/test_ur_dispatcher_dataloop_migration_ss2_cleanup_spec.cpp
```

It left the working tree dirty afterward:

```text
M CMakeLists.txt
M data_plane_tcp_session.hpp
M test_ur_dispatcher_dataloop_migration_behavior.cpp
?? test_ur_dispatcher_dataloop_migration_ss2_cleanup_redteam.cpp
?? test_ur_dispatcher_dataloop_migration_ss2_cleanup_redteam_c2.cpp
```

The commit agent explanation was that the task's other bullets referenced test case names and narrative verification activities, not filesystem paths to stage. Therefore it obeyed its explicit-paths-only rule and left those files pending.

This is the single most important workflow correctness finding.

### Why this matters

The final reviewer accepted a worktree that included more than the two committed files. If `CMakeLists.txt` registered the new SS2 tests, leaving it uncommitted can make the final commit fail to reproduce the same test surface. Similarly, leaving red-team test files untracked means future checkouts may lack regression guards that were part of the accepted validation state.

### Immediate repair approach

Do not rerun the whole workflow. Inspect and either commit or intentionally revert the leftover accepted paths.

Suggested verification:

```bash
git status --short

git diff -- \
  t_robotics/t_core/ros/universal_robots/ur_arci_adapter/CMakeLists.txt \
  t_robotics/t_core/ros/universal_robots/ur_arci_adapter/include/ur_arci_adapter/data_plane/data_plane_tcp_session.hpp \
  t_robotics/t_core/ros/universal_robots/ur_arci_adapter/test/test_ur_dispatcher_dataloop_migration_behavior.cpp \
  t_robotics/t_core/ros/universal_robots/ur_arci_adapter/test/test_ur_dispatcher_dataloop_migration_ss2_cleanup_redteam.cpp \
  t_robotics/t_core/ros/universal_robots/ur_arci_adapter/test/test_ur_dispatcher_dataloop_migration_ss2_cleanup_redteam_c2.cpp
```

If the diffs match the accepted SS2 handoff/reviewer state, commit them explicitly:

```bash
git add \
  t_robotics/t_core/ros/universal_robots/ur_arci_adapter/CMakeLists.txt \
  t_robotics/t_core/ros/universal_robots/ur_arci_adapter/include/ur_arci_adapter/data_plane/data_plane_tcp_session.hpp \
  t_robotics/t_core/ros/universal_robots/ur_arci_adapter/test/test_ur_dispatcher_dataloop_migration_behavior.cpp \
  t_robotics/t_core/ros/universal_robots/ur_arci_adapter/test/test_ur_dispatcher_dataloop_migration_ss2_cleanup_redteam.cpp \
  t_robotics/t_core/ros/universal_robots/ur_arci_adapter/test/test_ur_dispatcher_dataloop_migration_ss2_cleanup_redteam_c2.cpp

git commit -m "UR_MIGRATE_SS2: Commit accepted cleanup registration and red-team guards"
```

Then rerun the SS2 gate from a clean tree or at least rerun the package build/test and grep checks that the SS2 gate enforced.

---

## 6. AIWK / handoff findings

The operator asked whether this had already been solved by having each agent create AIWK handoff docs.

Answer: **partially, but not in the strong durable-handoff form needed to reduce context and runtime.**

### 6.1 What did happen

Agents did create handoff-like content:

- 30 of 42 journal result entries contained a `handoff` field.
- Some agents wrote Beads memories; grep found `bd remember` occurrences across multiple logs.
- Objective gate agents wrote AIWK gate evidence paths such as:

```text
/workspaces/.aiwk/ur_adapter_migrate_to_dataloop/state/gates/UR_MIGRATE_SS*_...
/workspaces/.aiwk/ur_adapter_migrate_to_dataloop/logs/gates/UR_MIGRATE_SS*_...
```

This means the workflow had handoff text and durable gate evidence.

### 6.2 What did not happen

I found no evidence that agents wrote durable per-step markdown handoff documents into an AIWK handoff directory.

Key searches from the logs:

| Search / signal | Finding |
|---|---:|
| `handoff_path` | 0 occurrences |
| `/state/handoffs` | 0 occurrences |
| `Write` / `Edit` tool calls to `.aiwk` paths | 0 |
| `Write` / `Edit` tool calls to `.aiwk/.../state` | 0 |
| Root prompts saying `Handoff path supplied by operator:` | 34 occurrences |
| Root prompts with value `(none)` after that header | 34 occurrences |

The root prompts did include:

```text
State/handoff directory: /workspaces/.aiwk/ur_adapter_migrate_to_dataloop/state
...
Handoff path supplied by operator:
(none)
If handoffPath is supplied, read it before editing.
```

That means agents knew a state/handoff directory existed, but they were not given a concrete durable handoff path to read, and they did not appear to write one themselves.

### 6.3 Consequence

The practical handoff channel was mostly:

```text
journal.jsonl result.handoff
Beads memories
AIWK state/gates JSON and log evidence
```

It was not:

```text
/workspaces/.aiwk/<project>/state/handoffs/<step>_<role>_<cycle>.md
StructuredOutput.handoff_path = <absolute path>
next agent receives exact handoff_path and reads it first
next prompt avoids re-inlining all prior context
```

So the handoff system helped with human traceability and some agent-to-agent summaries, but it did not force compact durable context transfer.

---

## 7. Token and cache-read findings

### 7.1 Raw usage from logs

Summing all logged assistant usage entries naively:

| Metric | Raw log sum |
|---|---:|
| `input_tokens` | 531,929 |
| `cache_creation_input_tokens` | 10,311,784 |
| `cache_read_input_tokens` | 182,423,776 |
| `output_tokens` | 986,619 |

Because the Claude logs contain repeated records for the same message IDs / streaming-style events, these raw totals likely overstate some billable/model-side totals. However, they are still useful as a measure of how much cached context was being reread across the workflow.

A conservative de-duplication by `(agent_id, message_id)` still showed:

| Metric | Conservative de-duped value |
|---|---:|
| `input_tokens` | 152,094 |
| `cache_creation_input_tokens` | 3,963,258 |
| `cache_read_input_tokens` | 78,088,343 |

The de-duped output-token figure is not very trustworthy because some repeated message IDs contain partial/streamed content records, but the cache-read conclusion is robust: **cache reads were enormous even under conservative de-duplication.**

### 7.2 Tool and model activity

| Signal | Value |
|---|---:|
| Bash tool uses | 700 |
| Read tool uses | 189 |
| Edit tool uses | 88 |
| StructuredOutput tool uses | 47 |
| Write tool uses | 12 |
| Dominant Opus agents | 38 / 42 |
| Dominant Sonnet agents | 4 / 42 |

The Sonnet agents were the safe-commit agents. Almost every meaningful dev/review/red-team agent used Opus.

### 7.3 Root prompt size

Root prompt sizes across 42 agents:

| Statistic | Characters |
|---|---:|
| Average | ~9,783 |
| Median | ~10,674 |
| 90th percentile | ~15,529 |
| Max | 16,903 |
| Min | 864 |

This is not catastrophic by itself, but the same large spec/invariants/gates/project context was repeatedly included in agent launches. Since many agents then performed many tool calls, each follow-up model turn reread a large and growing cached prefix.

### 7.4 Worst offending agent

The main SS1 developer agent was the largest cache-read source:

```text
agent: ae51f97072f2c9bc9
role: SS1 main developer migration
assistant/model entries: 290
recorded tool uses: 137
raw cache_read_input_tokens: 48,784,036
conservative de-duped cache_read_input_tokens: 23,073,117
```

Near the end of that agent, individual model turns were reading cached prefixes over ~220k tokens:

```text
max observed per-message cache_read_input_tokens ≈ 227,993
```

This explains the huge total. Once a single agent has accumulated a very large conversation/tool history, every small subsequent tool-result/model-response cycle can reread a massive cached prefix.

---

## 8. Why AIWK handoffs did not solve the cache problem

The key distinction:

- Handoff docs help **between agents**.
- They do not help **inside one very long agent** unless the workflow intentionally checkpoints and starts a fresh continuation agent.

In this run, both problems remained:

1. **Between-agent handoffs were not strongly materialized.**  
   Later agents got full inline project context and `(none)` for `handoffPath`, rather than compact durable handoff files.

2. **Inside-agent context kept growing.**  
   Long dev agents performed many `Read → Bash → Edit → Bash → Read → think` loops in one session. Every turn reused the cached prefix, so `cache_read_input_tokens` ballooned.

So the AIWK setup created some durable gate evidence and journal handoff text, but it did not enforce the context-economy pattern needed to reduce runtime/token churn.

---

## 9. Recommended workflow-generator changes

### 9.1 Make durable handoff docs mandatory

Every non-gate agent should write a compact handoff file before returning `StructuredOutput`.

Recommended path shape:

```text
/workspaces/.aiwk/<project>/state/handoffs/<STEP>_<ROLE>_<CYCLE>_<AGENT_ID>.md
```

Example:

```text
/workspaces/.aiwk/ur_adapter_migrate_to_dataloop/state/handoffs/UR_MIGRATE_SS1_DEV_C2_ae51f97072f2c9bc9.md
```

Required `StructuredOutput` fields:

```json
{
  "status": "done",
  "handoff_path": "/workspaces/.aiwk/.../state/handoffs/UR_MIGRATE_SS1_DEV_C2_ae51f97072f2c9bc9.md",
  "files_changed": ["..."],
  "accepted_paths": ["..."],
  "tests_run": ["..."],
  "known_dirty_paths": ["..."],
  "next_agent_should_read": ["handoff_path", "gate_evidence_path"]
}
```

Hard rule: if an agent returns without `handoff_path`, the orchestrator should treat the step as incomplete unless the role is a pure gate/commit action with a structured alternative.

### 9.2 Stop passing `(none)` handoff paths when prior handoffs exist

Current behavior seen in logs:

```text
Handoff path supplied by operator:
(none)
```

Desired behavior:

```text
Prior handoff paths:
- /workspaces/.aiwk/<project>/state/handoffs/UR_MIGRATE_SS1_DEV_C2_...
- /workspaces/.aiwk/<project>/state/handoffs/UR_MIGRATE_SS1_REVIEW_C2_...

Read these first. Do not rediscover prior context unless they contradict source/gates.
```

### 9.3 Do not inline full project spec into every prompt

Instead of re-inlining the entire spec/invariants/gates into every agent prompt, use a smaller launch prompt:

```text
Project: <name>
Role/task: <specific step>
Spec paths: <paths>
Read only the relevant sections named below.
Prior handoff paths: <paths>
Gate evidence paths: <paths>
Allowed edit paths: <paths or package root>
Forbidden scope: <short bullet list>
```

For reviewers and red-team agents, include the final dev handoff and exact diff/changed paths rather than the entire upstream narrative.

### 9.4 Cap long-running developer agents

Introduce a hard checkpoint rule:

```text
If an agent exceeds 25-35 tool calls, or after one major compile/test success, it must write a handoff and stop.
The orchestrator launches a fresh continuation agent with only the handoff, current gate evidence, and exact file list.
```

This directly targets the largest cache problem: single agents whose cached prefix grows past 100k-200k tokens.

### 9.5 Make commit handoffs path-based and machine-checkable

The final commit issue happened because the safe-commit agent was asked to stage explicit paths, but the upstream handoff/task contained bullets/test names/narrative that did not map cleanly to files.

Every accepted reviewer output should include:

```json
{
  "accepted": true,
  "accepted_paths_to_commit": [
    "t_robotics/t_core/ros/universal_robots/ur_arci_adapter/CMakeLists.txt",
    "..."
  ],
  "must_be_clean_except": []
}
```

Then the commit agent should:

1. run `git status --short`;
2. stage exactly `accepted_paths_to_commit`;
3. commit;
4. run `git status --short` again;
5. fail if any path touched by the accepted step remains dirty unless listed in `must_be_clean_except`.

This would have caught both the SS1 skipped/incomplete staging behavior and the final SS2 incomplete commit.

### 9.6 Treat AIWK gate evidence as typed input

Gate outputs already had durable evidence paths under `state/gates/`. Later agents should receive these paths explicitly and read the JSON summary rather than rerunning broad discovery.

Recommended `StructuredOutput` from gate agents:

```json
{
  "status": "ok",
  "gate": "ur_migration_packages",
  "setup_rc": 0,
  "build_rc": 0,
  "test_rc": 0,
  "result_rc": 0,
  "gate_clean": true,
  "evidence_path": "/workspaces/.aiwk/.../state/gates/...json",
  "log_path": "/workspaces/.aiwk/.../logs/gates/...log"
}
```

Review prompts should include the exact latest `evidence_path` and `log_path`.

---

## 10. Suggested durable handoff document template for future agents

Use this as the mandatory file each agent writes:

```markdown
# Handoff: <STEP> <ROLE> cycle <N>

## Verdict
- status: <done | failures_found | accepted | rejected | gate_ok | gate_red>
- short verdict: <one paragraph>

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

## Exact accepted paths to commit
- <path>

## Dirty tree expectations
- must be clean after commit: yes/no
- allowed dirty paths: []

## Next agent instructions
- read this first;
- do not rediscover X;
- focus on Y;
- rerun only Z if stale or contradicted.
```

---

## 11. Bottom-line answer to the AIWK question

You did solve part of the handoff problem: agents produced handoff summaries and the workflow had AIWK state/gate artifacts.

But you did **not** solve it in the form that would significantly reduce cache/read churn:

- no durable `state/handoffs/*.md` files were written;
- no `handoff_path` fields appeared in outputs;
- later agents were still launched with `Handoff path supplied by operator: (none)`;
- full spec/invariants/gates were re-inlined repeatedly;
- long Opus developer agents continued for many tool calls instead of checkpointing into fresh agents.

That is why `cache_read_input_tokens` reached huge values. The system was caching and rereading large, growing conversation prefixes over and over, especially inside long developer agents. Handoff docs only reduce that if they are compact, durable, passed by path, read first, and used to start fresh agents before context becomes enormous.

---

## 12. Priority action list

1. **Repair final SS2 commit integrity** by explicitly resolving the five leftover dirty paths and rerunning the relevant gate from a clean tree.
2. **Patch the commit agent contract** so reviewer outputs must include `accepted_paths_to_commit`, and commit agents fail if accepted-step paths remain dirty.
3. **Add mandatory AIWK durable handoff docs** under `state/handoffs/` with `StructuredOutput.handoff_path`.
4. **Launch downstream agents with concrete handoff paths**, not `(none)`.
5. **Cap long dev agents** around 25-35 tool calls or after a major compile/test milestone, then continue with a fresh agent and compact handoff.
6. **Stop re-inlining full specs into every agent prompt** where a path + narrow excerpt + handoff is sufficient.
7. **Use gate evidence JSON as typed input** to reviewers and fix agents.

If those changes are made, the next workflow should be both more reproducible and materially cheaper/faster in cache-read terms.
