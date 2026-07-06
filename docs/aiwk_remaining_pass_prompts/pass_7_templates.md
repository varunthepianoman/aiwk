# Pass 7 Prompt: Project Templates

You are working in the existing AIWK repository at:

```text
~/dev/aiwk
```

This is **Pass 7: Project Templates**.

## Context

AIWK now has:

```text
Pass 1.0 — durable substrate ✅
Pass 2.0 — workflow.yaml + Claude workflow renderer ✅
Pass 2.5/2.6 — mature runtime-compatible renderer ✅
Pass 3.0/3.1 — objective gates and evidence/logs ✅
Pass 4.0/4.1 — commit policy and final clean-status enforcement ✅
Pass 5 — Beads integration ✅
Pass 6 — handoff/context quality ✅
```

AIWK has enough primitives now to support reusable templates.

## Goal

Add project templates so new AIWK projects can be initialized with useful defaults.

Add support for:

```bash
aiwk init --project <name> --repo <path> --workflow-folder <path> --template <template_name>
```

Templates should generate:

```text
aiwk.yaml
workflow.yaml
spec/project.spec.md
spec/invariants.yaml
spec/gates.yaml
scripts/
state/
logs/
generated/
```

with template-specific workflow shape, objective gates, commit policy, Beads config, and starter specs.

## Templates to implement

Start with a small set:

```text
generic
ros2_refactor
bugfix_redteam
integration_harness
research_spike
```

If that is too much for one pass, implement:

```text
generic
ros2_refactor
bugfix_redteam
```

and document the others as future templates.

## Template: generic

Purpose:

```text
General software task with scope/dev/redteam/review/commit.
```

Defaults:

```yaml
default_stage: build
commit:
  mode: mechanical_all
objective_gates:
  default:
    enabled: true
    setup:
      commands:
        - true
    build:
      commands:
        - true
    test:
      commands:
        - true
    result:
      commands:
        - true
```

One starter step:

```text
GENERIC_SS0
```

## Template: ros2_refactor

Purpose:

```text
ROS 2 C++ package refactor with deterministic build/test gates.
```

Config should be generic enough to edit.

Add placeholders:

```yaml
template_options:
  ros_distro: jazzy
  packages:
    - TODO_PACKAGE
```

Objective gate should include placeholder commands:

```yaml
setup:
  commands:
    - source /opt/ros/jazzy/setup.bash || true
    - source install/setup.bash || true
build:
  commands:
    - colcon build --packages-select TODO_PACKAGE --continue-on-error
test:
  commands:
    - colcon test --packages-select TODO_PACKAGE --event-handlers console_direct+ --ctest-args -L gtest --timeout 60
result:
  commands:
    - colcon test-result --verbose
```

Do not hardcode `ur_arci_adapter` or any robotics-specific package names in AIWK core.

Starter steps:

```text
ROS2_REFAC_SS0 — scoping/spec tests
ROS2_REFAC_SS1 — core refactor
ROS2_REFAC_SS2 — seam cleanup
```

Starter invariants should mention:

```text
- no live robot/simulator by default
- deterministic tests first
- respect package boundaries
- no broad unrelated refactors
```

## Template: bugfix_redteam

Purpose:

```text
Bugfix workflow with adversarial regression tests.
```

Starter steps:

```text
BUGFIX_SS0 — reproduce/pin bug
BUGFIX_SS1 — implement fix
```

Objective gate:

```yaml
build/test/result commands default to true
```

Prompt should strongly emphasize:

```text
- reproduce before fix
- regression test must fail before implementation if practical
- Red Team tries alternate reproduction paths
```

## Template: integration_harness

Purpose:

```text
Integration/E2E harness buildout.
```

Starter steps:

```text
INTEG_SS0 — harness skeleton
INTEG_SS1 — observability and failure capture
INTEG_SS2 — happy-path E2E
INTEG_SS3 — failure-path E2E
```

Can be documented as future if not implemented in code.

## Template: research_spike

Purpose:

```text
Exploratory spike with explicit non-production boundaries.
```

Starter steps:

```text
SPIKE_SS0 — hypothesis and measurement harness
SPIKE_SS1 — prototype
SPIKE_SS2 — findings and recommendation
```

Can be documented as future if not implemented in code.

## CLI behavior

Add:

```bash
aiwk init --template generic
aiwk init --template ros2_refactor
aiwk init --template bugfix_redteam
```

Default template:

```text
generic
```

Add:

```bash
aiwk templates list
```

or:

```bash
aiwk init --list-templates
```

Choose the simpler option consistent with the CLI.

## Parser/storage implementation

Use Python package data or simple internal template strings. Keep it boring.

Suggested structure:

```text
aiwk/templates/
  __init__.py
  registry.py
  generic.py
  ros2_refactor.py
  bugfix_redteam.py
```

or use static text files if easier.

Do not introduce Jinja unless already present. Use stdlib formatting.

## Tests to add/update

### 1. CLI/template listing

- list templates returns expected names.

### 2. Init generic

- `aiwk init --template generic`
- creates workflow.yaml
- has objective gate
- has commit mode
- renders
- generated JS passes syntax if Node available.

### 3. Init ros2_refactor

- creates workflow.yaml with ROS2 placeholder commands.
- contains no hardcoded private robotics package names.
- contains package placeholder.
- contains three starter steps.
- renders.

### 4. Init bugfix_redteam

- contains reproduce/pin bug language.
- contains regression test guidance.
- renders.

### 5. Backward compatibility

- `aiwk init` without `--template` still works.
- Existing tests still pass.

### 6. Runtime compatibility

Generated JS from each template must still:

```text
include meta.name
not include export default
not include process.env
not include permissionMode
not include env:
preserve objective gate wiring
preserve commit behavior
```

## README update

Add:

```markdown
## Templates

- generic
- ros2_refactor
- bugfix_redteam
```

Include example:

```bash
aiwk init \
  --project my_refactor \
  --repo ~/dev/my_repo \
  --workflow-folder ~/dev/.aiwk \
  --template ros2_refactor
```

Document that template output is starter material and should be edited before serious runs.

## Commands to run

Run tests:

```bash
cd ~/dev/aiwk
~/dev/aiwk/.venv/bin/python -m pytest -q
```

Smoke init each implemented template:

```bash
TMP=$(mktemp -d)

for template in generic ros2_refactor bugfix_redteam; do
  mkdir -p "$TMP/repo_$template"
  cd "$TMP/repo_$template"
  git init
  git config user.email "test@example.com"
  git config user.name "Test User"
  echo hello > README.md
  git add README.md
  git commit -m init

  ~/dev/aiwk/.venv/bin/aiwk init \
    --project "demo_$template" \
    --repo "$TMP/repo_$template" \
    --workflow-folder "$TMP/.aiwk" \
    --template "$template"

  ~/dev/aiwk/.venv/bin/aiwk render claude-workflow \
    --config "$TMP/.aiwk/demo_$template/aiwk.yaml"
done
```

Syntax check if Node available:

```bash
for js in "$TMP"/.aiwk/*/generated/*.js; do
  echo "== $js =="
  node --check "$js"
done
```

Regenerate existing `.aiwk` workflows only if template changes affect shared rendering:

```bash
for cfg in ~/dev/.aiwk/*/aiwk.yaml; do
  ~/dev/aiwk/.venv/bin/aiwk render claude-workflow --config "$cfg"
done
```

## Stop rules

Stop and report if:

- Template system starts turning into a large rendering framework.
- You need a non-stdlib templating dependency.
- Runtime-compatible JS constraints are violated.
- Existing init/render behavior breaks.
- Tests fail after 2–3 serious attempts.

## Final report format

Report exactly:

```text
AIWK source files changed:
Tests added/changed:
Templates added:
CLI behavior changes:
Generated project files:
Commands run:
Test results:
Template smoke results:
Node syntax results:
Runtime validation request to run next:
Remaining limitations:
Recommended next pass:
```
