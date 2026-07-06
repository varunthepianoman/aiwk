"""Small built-in starter templates; generated files remain user-editable."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectTemplate:
    workflow: str
    project_spec: str
    invariants: str
    gates: str


def _header(project: str, description: str, gate_commands: dict[str, list[str]]) -> str:
    sections = []
    for name in ("setup", "build", "test", "result"):
        commands = gate_commands.get(name, ['"true"'])
        sections.append(f"    {name}:\n      commands:\n" + "\n".join(f"        - {cmd}" for cmd in commands))
    return f'''project: {project}
description: {description}
default_stage: build

commit:
  mode: mechanical_all
  message_template: "{{step_id}}: {{step_title}}"
  agent:
    model: sonnet
    effort: low

objective_gates:
  default:
    enabled: true
    description: Deterministic template checks; edit these commands before serious use.
{chr(10).join(sections)}

'''


def _step(step_id: str, title: str, scope: str, dev: str, redteam: str, review: str) -> str:
    return f'''      - id: {step_id}
        title: {title}
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
          scope: {scope}
          dev: {dev}
          redteam: {redteam}
          review: {review}
'''


def _generic(project: str) -> ProjectTemplate:
    workflow = _header(project, "General software workflow.", {}) + '''stages:
  build:
    description: Scope, implement, challenge, review, and commit a focused change.
    steps:
''' + _step(
        "GENERIC_SS0", "Focused software change",
        "Write black-box tests or checks that define the requested behavior.",
        "Implement only the scoped behavior and pass deterministic tests.",
        "Write adversarial white-box checks and probe failure boundaries.",
        "Review scope, invariants, objective gate evidence, and code quality.",
    )
    return ProjectTemplate(workflow, f"# Project Spec: {project}\n\n## Goal\n\nTODO\n\n## Source of Truth\n\nTODO\n\n## Non-goals\n\nTODO\n\n## Workflow Notes\n\nEdit template placeholders before running.\n", "invariants: []\n", "gates: []\n")


def _ros2_refactor(project: str) -> ProjectTemplate:
    commands = {
        "setup": ["source /opt/ros/jazzy/setup.bash || true", "source install/setup.bash || true"],
        "build": ["colcon build --packages-select TODO_PACKAGE --continue-on-error"],
        "test": ["colcon test --packages-select TODO_PACKAGE --event-handlers console_direct+ --ctest-args -L gtest --timeout 60"],
        "result": ["colcon test-result --verbose"],
    }
    workflow = _header(project, "Generic ROS 2 C++ refactor workflow.", commands) + '''template_options:
  ros_distro: jazzy
  packages:
    - TODO_PACKAGE

stages:
  build:
    description: Deterministic ROS 2 refactor with package-boundary discipline.
    steps:
''' + "".join([
        _step("ROS2_REFAC_SS0", "Scoping and specification tests", "Pin current behavior with deterministic package tests; do not use a live robot or simulator.", "Implement only test/spec scaffolding required for the refactor.", "Challenge assumptions and package-boundary coverage.", "Require deterministic tests and a narrow refactor boundary."),
        _step("ROS2_REFAC_SS1", "Core refactor", "Specify the new core contract before implementation.", "Implement the core refactor within TODO_PACKAGE boundaries.", "Probe lifecycle, failure, and stale-interface cases.", "Reject broad unrelated refactors and require clean colcon evidence."),
        _step("ROS2_REFAC_SS2", "Seam cleanup", "Pin removal of stale seams and compatibility leftovers.", "Remove only obsolete seams justified by the accepted core refactor.", "Search for hidden stale paths and missing integration checks.", "Verify package boundaries and deterministic results."),
    ])
    invariants = """invariants:
  - no live robot or simulator by default
  - deterministic tests first
  - respect package boundaries
  - no broad unrelated refactors
"""
    return ProjectTemplate(workflow, f"# Project Spec: {project}\n\n## Goal\n\nRefactor TODO_PACKAGE safely.\n\n## Source of Truth\n\nTODO\n\n## Non-goals\n\nLive robot/simulator work.\n\n## Workflow Notes\n\nReplace template placeholders first.\n", invariants, "gates: []\n")


def _bugfix_redteam(project: str) -> ProjectTemplate:
    workflow = _header(project, "Bugfix with adversarial regression testing.", {}) + '''stages:
  build:
    description: Reproduce, fix, and adversarially validate a bug.
    steps:
''' + "".join([
        _step("BUGFIX_SS0", "Reproduce and pin the bug", "Reproduce before fixing; write a regression test that fails first when practical.", "Add only the reproduction/test artifact; do not hide the bug.", "Try alternate reproduction paths and boundary inputs.", "Verify the regression test genuinely pins the reported bug."),
        _step("BUGFIX_SS1", "Implement and validate the fix", "Clarify the narrow accepted behavior and non-goals.", "Implement the smallest fix that passes the regression test.", "Try alternate reproduction paths and adversarial variants.", "Reject symptom masking, scope creep, and fragile fixes."),
    ])
    return ProjectTemplate(workflow, f"# Project Spec: {project}\n\n## Goal\n\nReproduce and fix TODO bug.\n\n## Source of Truth\n\nTODO\n\n## Non-goals\n\nUnrelated refactors.\n\n## Workflow Notes\n\nReproduce before fix.\n", "invariants:\n  - preserve unrelated behavior\n  - regression test first when practical\n", "gates: []\n")


TEMPLATE_NAMES = ("generic", "ros2_refactor", "bugfix_redteam")


def get_template(name: str, project: str) -> ProjectTemplate:
    factories = {"generic": _generic, "ros2_refactor": _ros2_refactor, "bugfix_redteam": _bugfix_redteam}
    try:
        return factories[name](project)
    except KeyError:
        raise ValueError(f"Unknown template '{name}'. Available: {', '.join(TEMPLATE_NAMES)}") from None
