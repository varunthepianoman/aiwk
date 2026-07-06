# AIWK Documentation

The current user-facing documentation is organized by intent:

- [User guide](user-guide.md) — install AIWK, initialize a project, operate a workflow, resume work, and troubleshoot failures.
- [Workflow reference](workflow-reference.md) — supported `aiwk.yaml` and `workflow.yaml` fields with validation rules.
- [Architecture](architecture.md) — how durable inputs become a generated workflow, how routing works, and where trust boundaries sit.
- [Claude runtime validation](../testing_infra/aiwk_claude_runtime_validation_instructions.md) — recreate and run an isolated end-to-end runtime smoke test.

The remaining files in this directory are historical implementation prompts and QA bundles. They are useful development records, but they are not authoritative usage documentation. For current behavior, use the files listed above and the CLI `--help` output.

