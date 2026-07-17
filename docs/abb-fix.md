You are Codex repairing two existing AIWK workflow projects after the AIWK core fixes from Prompt 1 have landed.

Use the updated AIWK version produced by Prompt 1.

## Paths

AIWK source:

```text
/home/varunkamat/dev/aiwk
```

Use the configured virtual environment explicitly:

```text
/home/varunkamat/dev/aiwk/.venv/bin/python
/home/varunkamat/dev/aiwk/.venv/bin/aiwk
```

Transport workflow project:

```text
/home/varunkamat/dev/.aiwk/abb_arci_v2_gofa_transport
```

Motion workflow project:

```text
/home/varunkamat/dev/.aiwk/abb_arci_v2_gofa_motion
```

Robotics worktree, read-only for this task:

```text
/home/varunkamat/dev/t_robotics_abb_arci_v2_gofa
```

Expected robotics branch:

```text
varun/abb-arci-v2-gofa
```

## Task boundaries

Edit durable AIWK project sources under the two workflow-project directories.

Do not:

```text
- edit robotics source;
- edit AIWK source during this prompt;
- launch either workflow;
- create commits;
- run bd.
```

Regenerate wrappers and generated Claude Workflow JavaScript through AIWK. Do not hand-patch generated JavaScript.

## First action: make a complete backup

Before editing anything, create a complete timestamped backup of both workflow projects under:

```text
/home/varunkamat/dev/.aiwk/backups/abb_arci_v2_workflows_<UTC_TIMESTAMP>/
```

Do not overwrite any existing backup.

The backup must contain complete copies of both:

```text
abb_arci_v2_gofa_transport
abb_arci_v2_gofa_motion
```

Report the exact backup path.

## Binding ABB ARCI v2 decisions

These decisions are already made. Do not reopen them.

### Package decision

The new C++ `ament_cmake` package is:

```text
abb_arci_v2_adapter
```

Do not create:

```text
abb_arci_v2_interfaces
```

Preserve existing ARCI interfaces where practical. If an interface change is genuinely required, the workflow must treat it as an explicit breaking change rather than silently creating a new interfaces package.

### Legacy ABB path

These remain legacy and outside the ARCI v2 implementation path:

```text
abb_arci_adapter_node.py
abb_driver.py
ActerisHandshake.mod
```

Do not add ARCI v2 functionality to the legacy Python adapter or legacy five-variable RAPID handshake.

### Runtime architecture

ARCI v2 is C++ only.

Required architecture:

```text
- Reuse dataloop::HandshakeStateMachine directly.
- Reuse dataloop::GoalExecutor directly.
- Place ABB-specific IO behind adapter interfaces.
- Do not fork or reimplement the generic algorithms.
- Do not add a Python binding or Python re-expression.
```

The ABB implementation uses the dual-socket architecture.

Control socket:

```text
- Dedicated persistent socket.
- rpc_id travels adapter → robot.
- dispatcher_state travels robot → adapter.
- Owns reset acknowledgement.
- Owns heartbeat, runtime-error, and not-ready behavior.
```

Data socket:

```text
- ABB/controller side is the TCP client.
- Adapter is the TCP server.
- Owns INIT/INIT_ACK and the ARCI v2 data-plane packets.
```

RWS/PERS subscriptions and `set_symbol` writes are not the steady-state ARCI v2 runtime control path. RWS is restricted to lifecycle, setup, diagnostics, or legacy operation.

### Data-plane contract

The current Data Plane Specification is authoritative.

The frame header is exactly 12 bytes, consisting of three signed int32 fields in big-endian order:

```text
magic
packet_type
payload_length
```

Required details:

```text
magic = 0x41524349
payload_length is measured in bytes
payload_length must be a multiple of 4
read exactly the 12-byte header first
then read exactly payload_length bytes
use fixed local maximum-payload limits
do not negotiate the maximum in INIT/INIT_ACK
complete INIT/INIT_ACK before data exchange
strictly serialize request/response or ACK-requiring operations
discard previous session state on reconnect
require a fresh INIT/INIT_ACK after reconnect
```

Use the flattened packet catalog. Do not add a separate VENDOR envelope.

This includes packet types such as:

```text
RPC_ARGS = 0x10
MOVE_SEQ = 0x11
MOTION_PROFILE_READ_REQ = 0x12
MOTION_PROFILE_READ_RSP = 0x0001_0012
BLENDING_PROFILE_READ_REQ = 0x13
BLENDING_PROFILE_READ_RSP = 0x0001_0013
TOOL_READ_REQ = 0x14
TOOL_READ_RSP = 0x0001_0014
TOOL_WRITE = 0x15
TOOL_GET_ACTIVE_REQ = 0x16
TOOL_GET_ACTIVE_RSP = 0x0001_0016
FRAME_READ_REQ = 0x17
FRAME_READ_RSP = 0x0001_0017
FRAME_WRITE = 0x18
FRAME_GET_ACTIVE_REQ = 0x19
FRAME_GET_ACTIVE_RSP = 0x0001_0019
```

Transport SS0.5 through SS3 must not implement the later production stores/catalogs/tool/frame/motion-management scope.

The motion workflow remains a constrained minimal demonstration:

```text
- positive MoveJ coverage;
- positive MoveL coverage;
- one-block MoveSequence;
- three-block MoveSequence.
```

It is not a broad production motion stack.

## Required workflow-project repairs

### 1. Repair all YAML

The transport project currently has known invalid YAML near:

```text
workflow.yaml:266
workflow.yaml:286
spec/invariants.yaml:11
```

The failures were caused by unquoted plain scalars containing `: ` and produced an error comparable to:

```text
mapping values are not allowed here
```

Parse every YAML file in both workflow projects, not only those three locations.

Repair invalid strings using valid quoting or block scalars without changing their intended semantics.

Do not hand-edit generated JavaScript.

### 2. Make external snapshots truly optional

With Beads disabled:

```text
- wrappers and coordinator must not pass --beads-snapshot-file unless the operator supplied a real existing file;
- no fake empty snapshot may be created;
- preflight, context-pack generation, rendering, and launch preparation must work without a snapshot;
- generated prompts must not tell agents to run bd.
```

Use the behavior implemented by Prompt 1.

### 3. Refresh all generated wrappers and runbooks

Regenerate project wrappers using the updated AIWK source.

Ensure:

```text
- wrappers use the pinned AIWK virtual-environment interpreter;
- context_pack.sh forwards all supported context-pack options;
- optional snapshot arguments are forwarded only when supplied;
- coordinator and runbook examples match the current launch behavior;
- stale Beads wording is removed;
- stale explicit-path-staging descriptions are removed when commit mode is mechanical_all.
```

Do not manually patch generated JavaScript.

### 4. Transport must resume at SS0.5

The default transport launch/resume point must be:

```json
{
  "stage": "build",
  "fromStep": "SS0_5_RECONCILE_DUAL_SOCKET_AND_DATA_PLANE_SPEC",
  "onlyStep": null
}
```

Do not default to `fromStep: null` or restart from the original SS0.

The intended sequence after SS0.5 is:

```text
1. SS0_5_RECONCILE_DUAL_SOCKET_AND_DATA_PLANE_SPEC
2. SS1_ARCI_V2_HANDSHAKE_VERTICAL_SLICE
3. SS2 data-socket framing/session
4. SS3 scalar argument/return ordering
```

SS1 owns the control socket and reuse of the generic handshake/GoalExecutor architecture.

SS2 owns the data socket and canonical frame/session contract.

SS3 owns scalar bool/int/float arguments and returns, including return-before-terminal ordering.

### 5. Scope `colcon test-result` to tested packages

Do not use a global:

```bash
colcon test-result --verbose
```

that can fail because of stale or unrelated workspace results.

Objective gates must inspect results corresponding to the packages actually built and tested by that gate.

Use the selected package/build/test result location so unrelated stale package failures cannot contaminate the result.

Use the binding package name:

```text
abb_arci_v2_adapter
```

and the relevant shared packages where needed.

Do not substitute legacy-only ABB package names.

### 6. Strengthen positive motion gates

The motion workflow’s objective gates must positively verify the required behavior rather than merely checking for the absence of forbidden patterns.

Add checks that verify:

```text
- MoveJ support is present;
- MoveL support is present;
- one-block MoveSequence coverage exists;
- three-block MoveSequence coverage exists;
- expected packet, handler, or step symbols are present;
- the minimal motion demonstration is actually exercised.
```

Preserve the narrow project scope. Do not expand this into production stores/catalogs or a broad motion stack.

### 7. Preserve durable handoff and Discovery behavior

Use the updated AIWK behavior from Prompt 1.

Requirements:

```text
- every substantive agent receives a unique handoff_path;
- Discovery/Scope reads prior handoffs first when they exist;
- Discovery records findings in its own durable handoff;
- later agents receive prior handoff paths, exact changed paths, and gate evidence;
- agents use targeted context rather than repeating broad repository discovery;
- checkpoint continuation is provided by AIWK’s real continuation mechanism;
- do not create a local fake checkpoint mechanism in these projects;
- do not reintroduce Beads as the step-to-step handoff mechanism.
```

### 8. Keep transport and motion boundaries separate

Transport owns:

```text
- SS0.5 architecture/spec reconciliation;
- control socket;
- generic HandshakeStateMachine/GoalExecutor integration;
- INIT/INIT_ACK;
- data-plane framing/session;
- scalar arguments and return ordering through SS3.
```

Transport must not implement:

```text
- production stores or catalogs;
- production tool/frame/speed/zone management;
- motion execution.
```

Motion owns:

```text
- later tool/frame/speed/zone store or catalog usage required by motion;
- minimal MoveSequence support;
- positive MoveJ and MoveL demonstrations;
- one-block and three-block motion cases.
```

Motion must not redesign:

```text
- the handshake;
- control-plane behavior;
- data-plane framing/session;
- package decisions;
- interface decisions.
```

## Validation

### YAML validation

Parse every YAML file in both workflow projects using the configured AIWK Python environment and PyYAML or the AIWK project parser.

Report every file parsed and whether it passed.

### AIWK preflight

Run:

```bash
/home/varunkamat/dev/aiwk/.venv/bin/aiwk preflight \
  --config /home/varunkamat/dev/.aiwk/abb_arci_v2_gofa_transport/aiwk.yaml
```

and:

```bash
/home/varunkamat/dev/aiwk/.venv/bin/aiwk preflight \
  --config /home/varunkamat/dev/.aiwk/abb_arci_v2_gofa_motion/aiwk.yaml
```

### Regeneration

Render both projects through AIWK:

```bash
/home/varunkamat/dev/aiwk/.venv/bin/aiwk render claude-workflow \
  --config /home/varunkamat/dev/.aiwk/abb_arci_v2_gofa_transport/aiwk.yaml
```

```bash
/home/varunkamat/dev/aiwk/.venv/bin/aiwk render claude-workflow \
  --config /home/varunkamat/dev/.aiwk/abb_arci_v2_gofa_motion/aiwk.yaml
```

Regenerate wrappers and coordinator artifacts through their owning AIWK commands or generators.

Do not hand-edit generated JavaScript.

### JavaScript syntax

Run `node --check` on both generated workflow JavaScript files.

### Semantic inspection

Inspect the generated projects and confirm the presence or correctness of:

```text
handoff_path
fresh checkpoint continuation
fromStep
onlyStep
optional external-memory behavior
mechanical_all wording and behavior
abb_arci_v2_adapter
absence of abb_arci_v2_interfaces
legacy ABB exclusions
12-byte data-plane contract
canonical 0x41524349 magic
flattened packet catalog
package-scoped test-result behavior
positive MoveJ/MoveL gates
one-block and three-block motion gates
```

## Exact launch payloads to report, but not execute

Report this transport payload with fresh generated paths substituted where appropriate:

```json
{
  "stage": "build",
  "fromStep": "SS0_5_RECONCILE_DUAL_SOCKET_AND_DATA_PLANE_SPEC",
  "onlyStep": null,
  "preflightSummary": "<fresh preflight JSON>",
  "handoffPath": "<fresh coordinator prestart handoff>"
}
```

Report this motion payload:

```json
{
  "stage": "build",
  "fromStep": null,
  "onlyStep": null,
  "preflightSummary": "<fresh preflight JSON>",
  "handoffPath": "<fresh coordinator prestart handoff>"
}
```

Do not include a snapshot field unless an external-memory snapshot was explicitly supplied and exists.

Do not execute either payload.

## Prohibited actions

Do not:

```text
- edit the robotics worktree;
- implement or run ABB workflow tasks;
- run live-controller or RobotStudio tests;
- run broad robotics builds;
- hand-edit rendered JavaScript;
- use Beads or run bd;
- add automatic broad untracked-file policing;
- create abb_arci_v2_interfaces;
- reopen package or interface decisions;
- make a new branch-strategy decision;
- commit;
- launch either workflow.
- Lose any data in the regeneration process - there should be no data in old AIWK projects that isn't correctly ported over.
```

## Final report

Report exactly:

```text
Backup path:
Transport durable files changed:
Motion durable files changed:
Invalid YAML repaired:
Package-name changes:
Existing-interface policy:
Dual-socket architecture checks:
Data-plane-spec checks:
Optional-snapshot behavior:
Generated wrappers refreshed:
Handoff propagation verified:
Checkpoint continuation verified:
Transport default resume point:
Transport exact launch payload:
Motion exact launch payload:
Package-scoped test-result changes:
Transport gate improvements:
Motion positive-gate improvements:
Commands run:
YAML validation:
Preflight results:
Render results:
Node syntax-check results:
Files regenerated:
Target robotics files modified: must be none
Commits created: must be none
Workflows launched: must be none
Remaining limitations or manual QA:
```