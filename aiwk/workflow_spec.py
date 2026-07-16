"""Provider-neutral workflow specification and a small YAML subset reader."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any
from string import Formatter

SUPPORTED_PHASES = {"scope", "discovery", "dev", "redteam", "review", "commit"}
COMMIT_MODES = {"none", "mechanical_all", "mechanical_paths"}
COMMIT_TEMPLATE_FIELDS = {"step_id", "step_title", "project", "stage"}


@dataclass(frozen=True)
class CommitPolicy:
    mode: str = "mechanical_paths"
    message_template: str = "{step_id}: {step_title}"
    model: str = "sonnet"
    effort: str = "low"


@dataclass(frozen=True)
class BeadsConfig:
    enabled: bool = False
    legacy_prompt_guidance: bool = False
    project_hint: str = ""
    require_before_edit: bool = False
    allow_create_issue: bool = False
    allow_remember: bool = False
    status_filter: str = "open,in_progress,blocked,deferred,closed"
    before_edit_commands: list[str] = field(default_factory=list)
    remember_guidance: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExternalMemoryConfig:
    mode: str = "disabled"
    label: str = "external memory"
    include_in_context_pack: bool = False
    include_in_agent_prompts: bool = False


@dataclass(frozen=True)
class DiscoveryConfig:
    enabled: bool = False
    model: str = "opus"
    effort: str = "high"


@dataclass(frozen=True)
class ContextEconomyConfig:
    max_tool_calls_before_checkpoint: int = 30
    checkpoint_after_major_test_milestone: bool = True
    require_handoff_before_checkpoint: bool = True
    max_checkpoint_continuations: int = 1


@dataclass(frozen=True)
class ObjectiveGateCheck:
    name: str
    command: str
    max_count: int = 0
    counting_instructions: str = ""
    timeout_seconds: float = 300.0


@dataclass(frozen=True)
class ObjectiveGate:
    enabled: bool
    description: str
    setup_commands: list[str]
    build_commands: list[str]
    test_commands: list[str]
    result_commands: list[str]
    checks: list[ObjectiveGateCheck]
    timeout_seconds: float = 300.0
    setup_timeout_seconds: float = 300.0
    build_timeout_seconds: float = 300.0
    test_timeout_seconds: float = 300.0
    result_timeout_seconds: float = 300.0


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    title: str
    model: str
    effort: str
    phases: list[str]
    prompt: dict[str, str]
    objective_gate: str | None = None
    commit: CommitPolicy | None = None
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)


@dataclass(frozen=True)
class WorkflowStage:
    description: str
    steps: list[WorkflowStep]


@dataclass(frozen=True)
class WorkflowSpec:
    project: str
    description: str
    default_stage: str
    stages: dict[str, WorkflowStage]
    objective_gates: dict[str, ObjectiveGate] = field(default_factory=dict)
    commit: CommitPolicy = field(default_factory=CommitPolicy)
    beads: BeadsConfig = field(default_factory=BeadsConfig)
    external_memory: ExternalMemoryConfig = field(default_factory=ExternalMemoryConfig)
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    context_economy: ContextEconomyConfig = field(default_factory=ContextEconomyConfig)


def _scalar(text: str) -> Any:
    text = text.strip()
    if text in {"[]", "{}"}:
        return [] if text == "[]" else {}
    if text in {"true", "false"}:
        return text == "true"
    if text in {"null", "~"}:
        return None
    if text.lstrip("-").isdigit():
        return int(text)
    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", text):
        return float(text)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return json.loads(text) if text[0] == '"' else text[1:-1].replace("''", "'")
    return text


def load_yaml_subset(path: str | Path) -> dict[str, Any]:
    """Load mappings, lists, and scalars used by generated workflow specs."""
    tokens: list[tuple[int, str, int]] = []
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if "\t" in raw[:indent] or indent % 2:
            raise ValueError(f"Invalid indentation on line {number}")
        tokens.append((indent, raw.strip(), number))

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(tokens) or tokens[index][0] != indent:
            raise ValueError("Invalid or incomplete YAML block")
        is_list = tokens[index][1].startswith("- ")
        container: Any = [] if is_list else {}
        while index < len(tokens) and tokens[index][0] == indent:
            _, text, number = tokens[index]
            if text.startswith("- ") != is_list:
                raise ValueError(f"Mixed mapping and list on line {number}")
            if is_list:
                item = text[2:].strip()
                if not item:
                    if index + 1 >= len(tokens) or tokens[index + 1][0] <= indent:
                        raise ValueError(f"Empty list item on line {number}")
                    value, index = parse_block(index + 1, tokens[index + 1][0])
                    container.append(value)
                    continue
                if re.match(r"^[A-Za-z_][A-Za-z0-9_-]*:(?:\s|$)", item):
                    key, raw_value = item.split(":", 1)
                    value: dict[str, Any] = {key.strip(): _scalar(raw_value) if raw_value.strip() else {}}
                    index += 1
                    if index < len(tokens) and tokens[index][0] > indent:
                        extra, index = parse_block(index, tokens[index][0])
                        if not isinstance(extra, dict):
                            raise ValueError(f"Expected mapping after list item on line {number}")
                        value.update(extra)
                    container.append(value)
                    continue
                container.append(_scalar(item))
                index += 1
                continue
            if ":" not in text:
                raise ValueError(f"Expected key/value on line {number}")
            key, raw_value = text.split(":", 1)
            key = key.strip()
            index += 1
            if raw_value.strip():
                container[key] = _scalar(raw_value)
            elif index < len(tokens) and tokens[index][0] > indent:
                container[key], index = parse_block(index, tokens[index][0])
            else:
                container[key] = {}
        return container, index

    if not tokens:
        raise ValueError("Workflow spec is empty")
    result, final = parse_block(0, tokens[0][0])
    if final != len(tokens) or not isinstance(result, dict):
        raise ValueError("Workflow spec must be a top-level mapping")
    return result


def load_workflow_spec(path: str | Path) -> WorkflowSpec:
    raw = load_yaml_subset(path)
    if not isinstance(raw.get("stages"), dict) or not raw["stages"]:
        raise ValueError("Workflow spec must define a non-empty 'stages' mapping")
    project = raw.get("project")
    default_stage = raw.get("default_stage")
    if not isinstance(project, str) or not project:
        raise ValueError("Workflow spec must define 'project'")
    if not isinstance(default_stage, str) or default_stage not in raw["stages"]:
        raise ValueError("Workflow spec default_stage must name a defined stage")
    objective_gates = _load_objective_gates(raw.get("objective_gates", {}))
    commit_policy = _load_commit_policy(raw.get("commit"), CommitPolicy(), "top-level commit")
    beads = _load_beads(raw.get("beads"))
    external_memory = _load_external_memory(raw.get("external_memory"), beads)
    discovery = _load_discovery(raw.get("discovery"), DiscoveryConfig(), "top-level discovery")
    context_economy = _load_context_economy(raw.get("context_economy"))
    stages: dict[str, WorkflowStage] = {}
    for stage_name, stage_raw in raw["stages"].items():
        if not isinstance(stage_raw, dict) or not isinstance(stage_raw.get("steps"), list):
            raise ValueError(f"Stage '{stage_name}' must define a steps list")
        seen: set[str] = set()
        steps: list[WorkflowStep] = []
        for step_raw in stage_raw["steps"]:
            if not isinstance(step_raw, dict):
                raise ValueError(f"Stage '{stage_name}' contains an invalid step")
            step_id = step_raw.get("id")
            if not isinstance(step_id, str) or not step_id:
                raise ValueError(f"Stage '{stage_name}' contains a step without an id")
            if step_id in seen:
                raise ValueError(f"Duplicate step id '{step_id}' in stage '{stage_name}'")
            seen.add(step_id)
            phases = step_raw.get("phases")
            prompts = step_raw.get("prompt", {})
            objective_gate = step_raw.get("objective_gate")
            if objective_gate is not None and not isinstance(objective_gate, str):
                raise ValueError(f"Step '{step_id}' objective_gate must be a string")
            if objective_gate is not None and objective_gate not in objective_gates:
                raise ValueError(f"Step '{step_id}' references unknown objective_gate '{objective_gate}'")
            step_commit = _load_commit_policy(
                step_raw.get("commit"), commit_policy, f"Step '{step_id}' commit"
            ) if "commit" in step_raw else None
            step_discovery = _load_discovery(
                step_raw.get("discovery"), discovery, f"Step '{step_id}' discovery"
            ) if "discovery" in step_raw else discovery
            if not isinstance(phases, list) or not phases:
                raise ValueError(f"Step '{step_id}' must define phases")
            if not isinstance(prompts, dict):
                raise ValueError(f"Step '{step_id}' prompt must be a mapping")
            for phase in phases:
                if phase not in SUPPORTED_PHASES:
                    raise ValueError(f"Unknown phase '{phase}' in step '{step_id}'")
                if phase not in {"commit", "discovery"} and (not isinstance(prompts.get(phase), str) or not prompts[phase].strip()):
                    raise ValueError(f"Missing prompt for phase '{phase}' in step '{step_id}'")
            if "discovery" in phases and not step_discovery.enabled:
                step_discovery = DiscoveryConfig(enabled=True, model=step_discovery.model, effort=step_discovery.effort)
            if step_discovery.enabled:
                prompt_value = prompts.get("discovery")
                if prompt_value is not None and (not isinstance(prompt_value, str) or not prompt_value.strip()):
                    raise ValueError(f"Missing prompt for phase 'discovery' in step '{step_id}'")
            steps.append(WorkflowStep(
                id=step_id,
                title=str(step_raw.get("title", "")),
                model=str(step_raw.get("model", "sonnet")),
                effort=str(step_raw.get("effort", "medium")),
                phases=[str(phase) for phase in phases],
                prompt={str(k): str(v) for k, v in prompts.items()},
                objective_gate=objective_gate,
                commit=step_commit,
                discovery=step_discovery,
            ))
        stages[str(stage_name)] = WorkflowStage(str(stage_raw.get("description", "")), steps)
    return WorkflowSpec(
        project=project, description=str(raw.get("description", "")),
        default_stage=default_stage, stages=stages,
        objective_gates=objective_gates, commit=commit_policy, beads=beads,
        external_memory=external_memory,
        discovery=discovery, context_economy=context_economy,
    )


def _load_external_memory(raw: Any, beads: BeadsConfig) -> ExternalMemoryConfig:
    defaults = ExternalMemoryConfig()
    if raw is None:
        if beads.enabled:
            return ExternalMemoryConfig(
                mode="snapshot",
                label="beads",
                include_in_context_pack=True,
                include_in_agent_prompts=True,
            )
        return defaults
    if not isinstance(raw, dict):
        raise ValueError("external_memory must be a mapping")
    mode = raw.get("mode", defaults.mode)
    if not isinstance(mode, str) or mode not in {"disabled", "snapshot"}:
        raise ValueError("external_memory.mode must be one of: disabled, snapshot")
    label = raw.get("label", defaults.label)
    if not isinstance(label, str) or not label:
        raise ValueError("external_memory.label must be a string")
    include_context = raw.get("include_in_context_pack", defaults.include_in_context_pack)
    include_prompts = raw.get("include_in_agent_prompts", defaults.include_in_agent_prompts)
    if not isinstance(include_context, bool):
        raise ValueError("external_memory.include_in_context_pack must be a boolean")
    if not isinstance(include_prompts, bool):
        raise ValueError("external_memory.include_in_agent_prompts must be a boolean")
    return ExternalMemoryConfig(mode, label, include_context, include_prompts)


def _load_discovery(raw: Any, base: DiscoveryConfig, label: str) -> DiscoveryConfig:
    if raw is None:
        return base
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a mapping")
    enabled = raw.get("enabled", base.enabled)
    if not isinstance(enabled, bool):
        raise ValueError(f"{label}.enabled must be a boolean")
    model = raw.get("model", base.model)
    effort = raw.get("effort", base.effort)
    if not isinstance(model, str) or not model:
        raise ValueError(f"{label}.model must be a string")
    if not isinstance(effort, str) or not effort:
        raise ValueError(f"{label}.effort must be a string")
    return DiscoveryConfig(enabled, model, effort)


def _load_context_economy(raw: Any) -> ContextEconomyConfig:
    if raw is None:
        return ContextEconomyConfig()
    if not isinstance(raw, dict):
        raise ValueError("context_economy must be a mapping")
    defaults = ContextEconomyConfig()
    max_calls = raw.get("max_tool_calls_before_checkpoint", defaults.max_tool_calls_before_checkpoint)
    if isinstance(max_calls, bool) or not isinstance(max_calls, int) or max_calls <= 0:
        raise ValueError("context_economy.max_tool_calls_before_checkpoint must be a positive integer")
    checkpoint_after = raw.get(
        "checkpoint_after_major_test_milestone",
        defaults.checkpoint_after_major_test_milestone,
    )
    if not isinstance(checkpoint_after, bool):
        raise ValueError("context_economy.checkpoint_after_major_test_milestone must be a boolean")
    require_handoff = raw.get(
        "require_handoff_before_checkpoint",
        defaults.require_handoff_before_checkpoint,
    )
    if not isinstance(require_handoff, bool):
        raise ValueError("context_economy.require_handoff_before_checkpoint must be a boolean")
    max_continuations = raw.get(
        "max_checkpoint_continuations",
        defaults.max_checkpoint_continuations,
    )
    if isinstance(max_continuations, bool) or not isinstance(max_continuations, int) or max_continuations < 0:
        raise ValueError("context_economy.max_checkpoint_continuations must be a non-negative integer")
    return ContextEconomyConfig(max_calls, checkpoint_after, require_handoff, max_continuations)


def _load_beads(raw: Any) -> BeadsConfig:
    if raw is None:
        return BeadsConfig()
    if not isinstance(raw, dict):
        raise ValueError("beads must be a mapping")
    defaults = BeadsConfig()
    bool_fields = ("enabled", "legacy_prompt_guidance", "require_before_edit", "allow_create_issue", "allow_remember")
    values: dict[str, Any] = {}
    for name in bool_fields:
        value = raw.get(name, getattr(defaults, name))
        if not isinstance(value, bool):
            raise ValueError(f"beads.{name} must be a boolean")
        values[name] = value
    for name in ("project_hint", "status_filter"):
        value = raw.get(name, getattr(defaults, name))
        if not isinstance(value, str):
            raise ValueError(f"beads.{name} must be a string")
        values[name] = value
    for name in ("before_edit_commands", "remember_guidance"):
        value = raw.get(name, [])
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"beads.{name} must be a list of strings")
        values[name] = list(value)
    return BeadsConfig(**values)


def _load_commit_policy(raw: Any, base: CommitPolicy, label: str) -> CommitPolicy:
    if raw is None:
        return base
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a mapping")
    mode = raw.get("mode", base.mode)
    if not isinstance(mode, str) or mode not in COMMIT_MODES:
        raise ValueError(f"{label} mode must be one of: {', '.join(sorted(COMMIT_MODES))}")
    message = raw.get("message_template", base.message_template)
    if not isinstance(message, str):
        raise ValueError(f"{label} message_template must be a string")
    fields = {name for _, name, _, _ in Formatter().parse(message) if name}
    unknown = fields - COMMIT_TEMPLATE_FIELDS
    if unknown:
        raise ValueError(f"{label} message_template has unknown variable: {sorted(unknown)[0]}")
    agent = raw.get("agent", {})
    if not isinstance(agent, dict):
        raise ValueError(f"{label} agent must be a mapping")
    model = agent.get("model", base.model)
    effort = agent.get("effort", base.effort)
    if not isinstance(model, str) or not model:
        raise ValueError(f"{label} agent model must be a string")
    if not isinstance(effort, str) or not effort:
        raise ValueError(f"{label} agent effort must be a string")
    return CommitPolicy(mode, message, model, effort)


def _load_objective_gates(raw: Any) -> dict[str, ObjectiveGate]:
    if raw in ({}, None):
        return {}
    if not isinstance(raw, dict):
        raise ValueError("Workflow spec objective_gates must be a mapping")
    gates: dict[str, ObjectiveGate] = {}
    for gate_name, gate_raw in raw.items():
        if not isinstance(gate_raw, dict):
            raise ValueError(f"Objective gate '{gate_name}' must be a mapping")
        enabled = gate_raw.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"Objective gate '{gate_name}' enabled must be a boolean")
        description = gate_raw.get("description", "")
        if not isinstance(description, str):
            raise ValueError(f"Objective gate '{gate_name}' description must be a string")
        gate_timeout = _load_timeout(
            gate_raw.get("timeout_seconds", 300),
            f"Objective gate '{gate_name}' timeout_seconds",
        )

        sections: dict[str, list[str]] = {}
        section_timeouts: dict[str, float] = {}
        for section in ("setup", "build", "test", "result"):
            section_raw = gate_raw.get(section, {})
            if not isinstance(section_raw, dict):
                raise ValueError(f"Objective gate '{gate_name}' {section} must be a mapping")
            commands = section_raw.get("commands", [])
            if not isinstance(commands, list):
                raise ValueError(f"Objective gate '{gate_name}' {section} commands must be a list")
            for command in commands:
                if not isinstance(command, str):
                    raise ValueError(f"Objective gate '{gate_name}' {section} commands must be strings")
            sections[section] = list(commands)
            section_timeouts[section] = _load_timeout(
                section_raw.get("timeout_seconds", gate_timeout),
                f"Objective gate '{gate_name}' {section} timeout_seconds",
            )

        checks_raw = gate_raw.get("checks", [])
        if not isinstance(checks_raw, list):
            raise ValueError(f"Objective gate '{gate_name}' checks must be a list")
        checks: list[ObjectiveGateCheck] = []
        seen_checks: set[str] = set()
        for check_raw in checks_raw:
            if not isinstance(check_raw, dict):
                raise ValueError(f"Objective gate '{gate_name}' checks must be mappings")
            name = check_raw.get("name")
            command = check_raw.get("command")
            if not isinstance(name, str) or not name:
                raise ValueError(f"Objective gate '{gate_name}' check requires a string name")
            if name in seen_checks:
                raise ValueError(f"Objective gate '{gate_name}' has duplicate check '{name}'")
            seen_checks.add(name)
            if not isinstance(command, str) or not command:
                raise ValueError(f"Objective gate '{gate_name}' check '{name}' requires a string command")
            max_count = check_raw.get("max_count", 0)
            if not isinstance(max_count, int) or isinstance(max_count, bool):
                raise ValueError(f"Objective gate '{gate_name}' check '{name}' max_count must be an integer")
            instructions = check_raw.get("counting_instructions", "")
            if not isinstance(instructions, str):
                raise ValueError(f"Objective gate '{gate_name}' check '{name}' counting_instructions must be a string")
            timeout = _load_timeout(
                check_raw.get("timeout_seconds", gate_timeout),
                f"Objective gate '{gate_name}' check '{name}' timeout_seconds",
            )
            checks.append(ObjectiveGateCheck(name, command, max_count, instructions, timeout))
        gates[str(gate_name)] = ObjectiveGate(
            enabled=enabled,
            description=description,
            setup_commands=sections["setup"],
            build_commands=sections["build"],
            test_commands=sections["test"],
            result_commands=sections["result"],
            checks=checks,
            timeout_seconds=gate_timeout,
            setup_timeout_seconds=section_timeouts["setup"],
            build_timeout_seconds=section_timeouts["build"],
            test_timeout_seconds=section_timeouts["test"],
            result_timeout_seconds=section_timeouts["result"],
        )
    return gates


def _load_timeout(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{label} must be a positive number")
    return float(value)


def starter_workflow(project: str) -> str:
    return f"""project: {project}
description: TODO
default_stage: build

commit:
  mode: mechanical_all
  message_template: "{{step_id}}: {{step_title}}"
  agent:
    model: sonnet
    effort: low

stages:
  build:
    description: TODO
    steps:
      - id: DEMO_SS0
        title: TODO
        model: sonnet
        effort: medium
        phases:
          - scope
          - dev
          - redteam
          - review
          - commit
        prompt:
          scope: TODO write black-box tests/spec checks.
          dev: TODO implement the scoped change.
          redteam: TODO write adversarial white-box tests.
          review: TODO review implementation against gates/invariants.
"""
