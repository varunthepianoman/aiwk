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
