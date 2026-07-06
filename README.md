# aiwk

`aiwk` is a small Python CLI for creating and maintaining durable, per-project AI coding workflow scaffolding. Pass 1 covers specs, invariants, gates, preflight checks, context handoffs, and checkpoint commits without introducing an orchestration framework.

It uses the Python standard library and requires Python 3.10 or newer.

## Install

```bash
python -m pip install -e .
```

## Initialize a project

```bash
aiwk init --project p3s_socket_e2e --repo /workspaces/t_robotics --workflow-folder ai_workflows
```

The workflow root is configurable. This example creates `ai_workflows/p3s_socket_e2e/`; it does not modify the target repository.

## Commands

```bash
aiwk preflight --config ai_workflows/p3s_socket_e2e/aiwk.yaml
aiwk context-pack --config ai_workflows/p3s_socket_e2e/aiwk.yaml --phase PHASE_1
aiwk checkpoint --config ai_workflows/p3s_socket_e2e/aiwk.yaml --step STEP_1
```

Each command prints compact JSON. Detailed git output is written beneath the project's `logs/` directory. The generated shell wrappers offer the same operations; context and checkpoint wrappers accept the phase or step as their first argument.

Generated wrappers pin the Python interpreter used to run `aiwk init`. Initialize from the intended virtual environment so later wrapper calls do not depend on shell activation or a system `python` alias.

Claude/Codex integration and workflow generation are intentionally out of scope for Pass 1.

## Pass 2: Rendering a Claude Workflow

1. Initialize a project.
2. Edit the generated `workflow.yaml`.
3. Render it:

   ```bash
   aiwk render claude-workflow --config ai_workflows/p3s_socket_e2e/aiwk.yaml
   ```

4. Use `generated/p3s_socket_e2e.claude_workflow.js` with Claude Workflow.

To select different paths, pass `--workflow-spec path/to/workflow.yaml` and `--out path/to/workflow.js`.

The Claude Workflow JavaScript is a generated execution artifact. The durable source of truth is `workflow.yaml` together with `spec/project.spec.md`, `spec/invariants.yaml`, and `spec/gates.yaml`. Future passes may add richer gate and invariant injection and other render targets.

Pass 2 only renders JavaScript; it does not run Claude or invoke external agents. Codex rendering, Beads automation, token accounting, and complex orchestration remain out of scope.

To stay dependency-free, `workflow.yaml` supports the straightforward mappings, lists, and scalar values used by the generated starter file. Advanced YAML features such as anchors, tags, multiline scalars, and inline collections are not supported in Pass 2.

The current Claude renderer uses bounded Scope → Developer → Red Team → Reviewer → Commit control flow. Red Team failures return to Developer for up to two cycles, rejected reviews receive one Developer fix pass, and commit prompts require explicit-path staging only after accepted review. Durable project specs, invariants, and gates are embedded into the generated execution artifact at render time.

### Objective gates

Pass 3 supports optional named `objective_gates` in `workflow.yaml`. A step selects one with `objective_gate: <name>`. Gates contain `setup`, `build`, `test`, and `result` command lists plus optional named output-count checks. The generated workflow runs the selected gate before review and requires both a clean gate and reviewer acceptance before commit. Workflows that omit objective gates retain the previous behavior.

```yaml
objective_gates:
  default:
    enabled: true
    build:
      commands:
        - python -m py_compile example.py
    test:
      commands:
        - python -m unittest
    result:
      commands:
        - "true"
    checks:
      - name: no_forbidden_marker
        command: 'grep -R "FORBIDDEN_MARKER" .'
        max_count: 0
```

Run a gate directly to capture durable evidence:

```bash
aiwk gate-run \
  --config ai_workflows/demo/aiwk.yaml \
  --gate default \
  --step DEMO_SS0 \
  --attempt 1
```

`gate-run` executes each configured shell snippet in order from the target repository, writes full logs under `logs/gates/`, writes hashed JSON evidence under `state/gates/`, and prints compact JSON. A captured command failure still exits successfully with `gate_clean:false`; invalid configuration or runner failures exit nonzero. Commands use the platform `/bin/sh` through Python’s `shell=True`. Per-command timeouts default to 300 seconds and can be overridden at gate, section, or check level.

## Templates

- `generic`
- `ros2_refactor`
- `bugfix_redteam`

List them with `aiwk templates list`, or initialize one directly:

```bash
aiwk init \
  --project my_refactor \
  --repo ~/dev/my_repo \
  --workflow-folder ~/dev/.aiwk \
  --template ros2_refactor
```

Template output is starter material. Replace commands, package names, boundaries, and TODO sections before serious runs.
