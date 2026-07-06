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

beads:
  enabled: false
  project_hint: my-refactor
  require_before_edit: false
  allow_create_issue: false
  allow_remember: false
  status_filter: open,in_progress,blocked,deferred,closed
  before_edit_commands: []
  remember_guidance: []

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

### `beads`

Optional Beads prompt/context configuration. Missing config means disabled.

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

## Beads reference

```yaml
beads:
  enabled: true
  project_hint: service-refactor
  require_before_edit: true
  allow_create_issue: true
  allow_remember: true
  status_filter: open,in_progress,blocked,deferred,closed
  before_edit_commands:
    - bd prime || true
    - bd list --status open,in_progress,blocked,deferred,closed || true
  remember_guidance:
    - Use bd remember for durable architecture decisions.
```

All flags are booleans. `project_hint` and `status_filter` are strings. Command and guidance fields are lists of strings. This configuration changes generated prompt guidance; AIWK does not execute `bd` or automatically create/close issues.

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
        phases: [unsupported-inline-form]
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

