# AIWK Workflow Reference

This reference describes the configuration currently accepted by AIWK’s dependency-free parser. It is not a general YAML specification.

## `aiwk.yaml`

`aiwk init` creates the project locator/configuration file:

```yaml
project: "my_refactor"
repo: "/home/me/dev/my_repo"
workflow_folder: "/home/me/dev/.aiwk"
project_folder: "/home/me/dev/.aiwk/my_refactor"
relevant_paths:
  - "src/"
  - "tests/"
ignored_scratch_dirs:
  - "z_random/"
test_commands: {}
```

Fields:

| Field | Meaning |
| --- | --- |
| `project` | Stable project identifier used in paths and generated metadata. |
| `repo` | Target repository where Git and gate commands run. |
| `workflow_folder` | Parent directory containing AIWK projects. |
| `project_folder` | Derived `<workflow_folder>/<project>` path. |
| `relevant_paths` | Optional prefixes used to classify preflight dirtiness. Empty means all changed files are relevant. |
| `ignored_scratch_dirs` | Reserved project configuration; currently not automatically applied. |
| `test_commands` | Reserved command mapping; objective gates are the current executable-check mechanism. |

Runtime state and logs are anchored to the directory containing the `aiwk.yaml` passed on the command line, even if a stored project path is relative.

## Complete `workflow.yaml` example

```yaml
project: my_refactor
description: Refactor a service without changing its public protocol.
default_stage: build

commit:
  mode: mechanical_all
  message_template: "{step_id}: {step_title}"
  agent:
    model: sonnet
    effort: low

external_memory:
  mode: disabled
  label: operator-notes
  include_in_context_pack: false
  include_in_agent_prompts: false

discovery:
  enabled: false
  model: opus
  effort: high

context_economy:
  max_tool_calls_before_checkpoint: 30
  checkpoint_after_major_test_milestone: true
  require_handoff_before_checkpoint: true

objective_gates:
  default:
    enabled: true
    description: Deterministic checks.
    timeout_seconds: 300
    setup:
      timeout_seconds: 30
      commands:
        - python --version
    build:
      timeout_seconds: 120
      commands:
        - python -m py_compile src/service.py
    test:
      commands:
        - python -m unittest discover -s tests
    result:
      commands:
        - "true"
    checks:
      - name: no_debug_marker
        command: 'grep -R "DEBUG_ONLY" src tests'
        max_count: 0
        timeout_seconds: 20
        counting_instructions: Count non-empty matching output lines.

stages:
  build:
    description: Implement the refactor in bounded substeps.
    steps:
      - id: REFACTOR_SS0
        title: Pin current behavior
        model: sonnet
        effort: medium
        objective_gate: default
        phases:
          - scope
          - dev
          - redteam
          - review
          - commit
        prompt:
          scope: Write black-box contract tests only.
          dev: Add the scoped tests and minimum supporting fixtures.
          redteam: Challenge the tests with white-box edge cases.
          review: Verify scope, invariants, and deterministic evidence.
```

## Top-level fields

### `project`

Required non-empty string. It normally matches `aiwk.yaml.project` and becomes `meta.name`/project metadata in the generated workflow.

### `description`

Optional scalar converted to a string and included in generated metadata.

### `default_stage`

Required string naming a key under `stages`.

### `objective_gates`

Optional mapping of gate name to gate configuration. Omitting it preserves workflows that rely only on agent/reviewer behavior.

### `commit`

Optional top-level commit policy. Workflows that omit it use legacy `mechanical_paths`; all built-in templates emit an explicit `mechanical_all` policy.

### `external_memory`

Optional snapshot-only advisory memory. Missing config means disabled.

### `beads`

Deprecated backward-compatibility mapping. `beads.enabled: false` is disabled. `beads.enabled: true` parses safely and maps to `external_memory.mode: snapshot`, but generated workflows do not emit live `bd` command guidance.

### `discovery`

Optional Discovery-agent default. Missing config means disabled. A step may override it, and an explicit `discovery` phase also enables Discovery for that step.

### `context_economy`

Optional prompt/checkpoint policy. Missing config uses safe defaults. Generated JS surfaces checkpoint requests but does not hard-count provider tool calls.

### `stages`

Required non-empty mapping. Each stage contains a description and a `steps` list.

Unknown top-level fields are currently ignored. Templates use this for human-editable metadata such as `template_options`; do not assume unknown fields affect execution.

## Objective gate reference

```yaml
objective_gates:
  fast:
    enabled: true
    description: Fast local checks.
    timeout_seconds: 300
```

Gate fields:

| Field | Type/default | Meaning |
| --- | --- | --- |
| `enabled` | boolean, `true` | Disabled gates are serialized but skipped by generated routing. |
| `description` | string, empty | Human-readable description. |
| `timeout_seconds` | positive number, `300` | Default timeout for each command. |
| `setup` | section | Environment/preparation commands; return code is reported but not enforced. |
| `build` | section | Build commands; nonzero or timeout makes gate red. |
| `test` | section | Test commands; nonzero or timeout makes gate red. |
| `result` | section | Result aggregation commands; nonzero or timeout makes gate red. |
| `checks` | list | Named output-count thresholds. |

Each section supports:

```yaml
build:
  timeout_seconds: 90
  commands:
    - make all
    - make lint
```

The section timeout overrides the gate timeout and applies independently to every command. Commands execute in order but in separate `/bin/sh` processes rooted at the target repository. The section return code is the last nonzero command code, or zero when all commands pass.

Checks support:

```yaml
checks:
  - name: no_forbidden_import
    command: 'grep -R "from legacy" src'
    max_count: 0
    timeout_seconds: 20
    counting_instructions: Count non-empty matching stdout lines.
```

Required check fields are `name` and `command`. `max_count` defaults to zero. The default count is the number of non-empty stdout lines. A grep-like no-match (`rc:1`, empty stdout) produces count zero. A timed-out check is never clean.

Every step reference must name a defined gate:

```yaml
objective_gate: fast
```

Unknown references fail validation.

## Commit policy reference

```yaml
commit:
  mode: mechanical_all
  message_template: "{project} {step_id}: {step_title}"
  agent:
    model: sonnet
    effort: low
```

Fields:

| Field | Rules |
| --- | --- |
| `mode` | One of `none`, `mechanical_all`, or `mechanical_paths`. |
| `message_template` | String supporting `{step_id}`, `{step_title}`, `{project}`, and `{stage}`. |
| `agent.model` | Non-empty string. |
| `agent.effort` | Non-empty string passed to the workflow runtime. |

A step may override some or all policy fields:

```yaml
steps:
  - id: DOCS_SS0
    commit:
      mode: none
```

Unspecified override fields inherit from the top-level policy.

## External memory and legacy Beads reference

AIWK is Beads-blind by default. It does not require Beads or any external memory service.

Preferred explicit snapshot-only config:

```yaml
external_memory:
  mode: snapshot
  label: operator-notes
  include_in_context_pack: true
  include_in_agent_prompts: true
```

Fields:

| Field | Rules |
| --- | --- |
| `mode` | `disabled` or `snapshot`. |
| `label` | Non-empty string for the advisory snapshot label. |
| `include_in_context_pack` | Boolean. Currently context-pack includes a supplied snapshot only when the operator passes `--beads-snapshot-file`; this field documents intent for workflow projects. |
| `include_in_agent_prompts` | Boolean. When true with `mode: snapshot`, generated prompts include a neutral optional snapshot section if runtime `beadsSnapshot` text is supplied. |

Legacy config is accepted:

```yaml
beads:
  enabled: true
  project_hint: service-refactor
```

All legacy flags are still validated for old files, but live Beads guidance is not emitted. `beads.enabled: true` means snapshot-only advisory compatibility. Generated workflows must not tell agents to run `bd` commands or mutate Beads state.

## Discovery and context economy reference

Top-level Discovery defaults:

```yaml
discovery:
  enabled: true
  model: opus
  effort: high
```

Per-step override:

```yaml
steps:
  - id: BIG_SS1
    discovery:
      enabled: true
      model: opus
      effort: high
```

When enabled, the generated sequence is Scope → Discovery → Dev. Discovery is meant for large migrations, unfamiliar package boundaries, or ambiguous work where multiple later agents would otherwise repeat broad repository search. It writes a compact repo-map handoff under `state/handoffs/` and tells Developer which files/symbols/tests to target and what not to rediscover.

Context economy:

```yaml
context_economy:
  max_tool_calls_before_checkpoint: 30
  checkpoint_after_major_test_milestone: true
  require_handoff_before_checkpoint: true
```

Fields:

| Field | Type/default | Meaning |
| --- | --- | --- |
| `max_tool_calls_before_checkpoint` | positive integer, `30` | Soft prompt budget for long agents. |
| `checkpoint_after_major_test_milestone` | boolean, `true` | Tell long agents to stop after major compile/test milestones instead of growing one transcript. |
| `require_handoff_before_checkpoint` | boolean, `true` | Require a written `handoff_path` before returning `status: "checkpoint"`. |

Checkpointing is prompt-level in Pass 1 of this feature: the generated workflow cannot observe internal tool-call counts, but it does return a structured `checkpoint_requested` halt when an agent returns checkpoint status.

## Stage and step reference

```yaml
stages:
  build:
    description: Main implementation stage.
    steps:
      - id: BUILD_SS0
        title: Pin behavior
        model: sonnet
        effort: medium
        objective_gate: default
        phases:
          - scope
          - discovery
          - dev
          - redteam
          - review
          - commit
        prompt:
          scope: Write black-box tests/spec checks.
          discovery: Map likely files, symbols, tests, and boundaries.
          dev: Implement the scoped change.
          redteam: Write adversarial white-box tests.
          review: Review implementation against gates and invariants.
```

Use block-list syntax for phases; inline lists are unsupported:

```yaml
        phases:
          - scope
          - dev
          - redteam
          - review
          - commit
```

Supported phase names are exactly:

- `scope`
- `dev`
- `redteam`
- `review`
- `commit`

Each declared non-commit phase requires a non-empty string in `prompt`. Step IDs must be unique within a stage. `model` defaults to `sonnet`; `effort` defaults to `medium`.

The mature routing is designed around the standard five-phase order. Omitting phases is supported by the renderer, but unusual combinations should be tested carefully.

## YAML subset

Supported constructs:

- block mappings;
- block lists;
- strings, integers, floats, booleans, and null;
- quoted JSON-style double strings;
- simple single-quoted strings;
- `{}` and `[]` empty containers;
- comments on their own lines.

Not supported:

- anchors, aliases, or tags;
- multiline `|` or `>` scalars;
- inline lists/mappings with content;
- odd-number indentation or tabs;
- general YAML implicit typing;
- sophisticated escaping in single-quoted strings;
- reliable inline comments after values.

Use two-space indentation and quote shell snippets that resemble booleans, numbers, or YAML structure.

## Validation behavior

Rendering and `gate-run` load the workflow spec and fail clearly for:

- missing or empty stages;
- invalid default stage;
- duplicate step IDs within a stage;
- unknown phases;
- missing phase prompts;
- unknown objective gates;
- non-string commands;
- invalid or nonpositive timeouts;
- malformed checks;
- invalid commit modes or message variables;
- invalid Beads field types.
