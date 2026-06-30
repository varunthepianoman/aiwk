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
