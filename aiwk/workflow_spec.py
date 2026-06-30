"""Provider-neutral workflow specification and a small YAML subset reader."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

SUPPORTED_PHASES = {"scope", "dev", "redteam", "review", "commit"}


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    title: str
    model: str
    effort: str
    phases: list[str]
    prompt: dict[str, str]


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


def _scalar(text: str) -> Any:
    text = text.strip()
    if text in {"[]", "{}"}:
        return [] if text == "[]" else {}
    if text in {"true", "false"}:
        return text == "true"
    if text in {"null", "~"}:
        return None
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
                if ":" in item:
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
            if not isinstance(phases, list) or not phases:
                raise ValueError(f"Step '{step_id}' must define phases")
            if not isinstance(prompts, dict):
                raise ValueError(f"Step '{step_id}' prompt must be a mapping")
            for phase in phases:
                if phase not in SUPPORTED_PHASES:
                    raise ValueError(f"Unknown phase '{phase}' in step '{step_id}'")
                if phase != "commit" and (not isinstance(prompts.get(phase), str) or not prompts[phase].strip()):
                    raise ValueError(f"Missing prompt for phase '{phase}' in step '{step_id}'")
            steps.append(WorkflowStep(
                id=step_id,
                title=str(step_raw.get("title", "")),
                model=str(step_raw.get("model", "sonnet")),
                effort=str(step_raw.get("effort", "medium")),
                phases=[str(phase) for phase in phases],
                prompt={str(k): str(v) for k, v in prompts.items()},
            ))
        stages[str(stage_name)] = WorkflowStage(str(stage_raw.get("description", "")), steps)
    return WorkflowSpec(project, str(raw.get("description", "")), default_stage, stages)


def starter_workflow(project: str) -> str:
    return f"""project: {project}
description: TODO
default_stage: build

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

