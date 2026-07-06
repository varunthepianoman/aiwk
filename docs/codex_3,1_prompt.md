You are working in the existing AIWK repository at:

  ~/dev/aiwk

This is Pass 3.1: Objective Gate Evidence / Provenance.

Context:
AIWK now has:
- Pass 1: durable substrate
- Pass 2: workflow.yaml + Claude workflow renderer
- Pass 2.5/2.6: mature runtime-compatible Claude workflow renderer
- Pass 3: Objective Gate DSL + enforced reviewer/gate separation

Pass 3 added generic objective gates:
- objective_gates in workflow.yaml
- setup/build/test/result command sections
- optional checks with max_count thresholds
- GATE_SCHEMA
- buildGatePrompt
- formatGateResult
- computeGateClean
- accepted = gateClean && review.accepted
- gate failures routed to Developer Fix Pass

Pass 3 result:
- 27 passed, 60 subtests passed
- all generated workflows passed Node syntax
- runtime validation workflow includes objective gates
- gate agent executes commands and reports raw rc/counts
- AIWK enforces the reported numbers and thresholds

Known limitation:
The gate agent still executes shell commands and reports the result. AIWK enforces the numbers it receives, but does not yet create durable, independently captured evidence/logs for the exact command execution. We want to reduce reliance on the agent’s prose/reporting by having AIWK itself run/capture the commands through a deterministic command runner that writes JSON evidence and full logs.

Important reality:
The Claude Workflow runtime cannot directly run shell from JS. The workflow still needs a low-effort gate agent to run one command. But the gate agent should no longer manually run arbitrary command blocks and summarize them. It should run one deterministic AIWK command, then return the JSON evidence produced by AIWK.

Goal:
Add an AIWK objective gate runner command that:
- executes a named objective gate from workflow.yaml;
- captures exact section exit codes;
- captures check counts;
- writes durable JSON evidence;
- writes full raw command logs;
- prints compact JSON to stdout;
- can be called by generated Claude workflows from the Objective Gate agent.

Core idea:
Instead of the gate agent running a long generated shell block, it should run something like:

  cd <repo>
  /home/varunkamat/dev/aiwk/.venv/bin/python -m aiwk gate-run \
    --config <project_folder>/aiwk.yaml \
    --workflow-spec <project_folder>/workflow.yaml \
    --gate <gate_name> \
    --step <step_id> \
    --attempt <attempt_number> \
    --repo <repo>

The command writes evidence under the AIWK project folder, for example:

  <project_folder>/state/gates/<step_id>_<gate_name>_attempt<attempt>_<timestamp>.json
  <project_folder>/logs/gates/<step_id>_<gate_name>_attempt<attempt>_<timestamp>.log

The gate agent then returns the compact stdout JSON from `aiwk gate-run` into GATE_SCHEMA.

Important constraints:
- Edit AIWK source under ~/dev/aiwk.
- Do not edit ~/dev/t_robotics source.
- Do not hand-patch generated JS except by regenerating from AIWK.
- Do not implement Beads integration.
- Do not implement templates.
- Do not implement token accounting.
- Do not implement provider abstraction.
- Do not break runtime-compatible JS:
  - meta.name remains present
  - no export default
  - no process.env
  - no permissionMode
  - no env:
  - Node syntax stays valid
- Preserve Pass 3 objective gate semantics.
- Preserve backward compatibility for workflows without objective_gates.
- Keep the pass focused. Do not redesign the whole renderer.

New CLI command:
Add:

  aiwk gate-run \
    --config <path-to-aiwk.yaml> \
    --workflow-spec <path-to-workflow.yaml> \
    --gate <gate-name> \
    --step <step-id> \
    --attempt <attempt-number> \
    --repo <repo-path>

Also support default workflow spec:

  aiwk gate-run \
    --config <path-to-aiwk.yaml> \
    --gate <gate-name> \
    --step <step-id> \
    --attempt <attempt-number> \
    --repo <repo-path>

Default behavior:
- If --workflow-spec is omitted, use `<project_folder>/workflow.yaml`.
- If --repo is omitted, use repo from aiwk.yaml.
- Create directories if needed:
  - `<project_folder>/state/gates/`
  - `<project_folder>/logs/gates/`

Command semantics:
- Read aiwk.yaml.
- Read workflow.yaml.
- Resolve named objective gate.
- Execute setup/build/test/result command sections.
- Execute checks.
- Capture raw stdout/stderr into a log file.
- Capture each section exit code.
- Capture check counts.
- Write evidence JSON.
- Print compact JSON to stdout.

Execution details:
- Use Python subprocess from stdlib.
- Run commands with shell=True for now because workflow.yaml command strings are shell snippets.
- Run each command with cwd=<repo>.
- Preserve ordering.
- Do not stop on first failure.
- Capture stdout/stderr for each command.
- For each section:
  - run all commands in that section in order;
  - section rc should be the last nonzero rc if any command failed, otherwise 0.
  - This means if setup has three commands and command 2 fails but command 3 passes, setup_rc still records failure.
- If a command times out is not yet implemented, document as future work. Do not add timeout unless simple.
- setup_rc is captured but not enforced by computeGateClean, preserving Pass 3 behavior.

Checks:
Each check has:
- name
- command
- max_count, default 0
- counting_instructions optional

For each check:
- run the command with cwd=<repo>
- count non-empty stdout lines by default
- if command exits 1 and stdout is empty, treat count as 0, because grep-like “no matches” often exits 1
- if command exits nonzero with stderr or stdout, still record rc and count lines
- include detail with short output/tail
- include max_count in result

Evidence JSON shape:
The exact shape can vary, but include at least:

  {
    "status": "ok",
    "project": "...",
    "repo": "...",
    "gate": "...",
    "step": "...",
    "attempt": 1,
    "setup_rc": 0,
    "build_rc": 0,
    "test_rc": 0,
    "result_rc": 0,
    "check_results": [
      {
        "name": "no_forbidden_marker",
        "command": "...",
        "rc": 1,
        "count": 0,
        "max_count": 0,
        "detail": "..."
      }
    ],
    "gate_clean": true,
    "evidence_path": "...",
    "log_path": "...",
    "raw_tail": "..."
  }

If gate-run itself cannot run because of config errors, print compact JSON with:
  status: "error"
  error: "clear message"
and exit nonzero.

Gate-clean logic:
Implement the same logic in Python as generated JS uses:

  gate_clean =
    build_rc == 0 &&
    test_rc == 0 &&
    result_rc == 0 &&
    all(check.count <= check.max_count)

setup_rc is reported but not enforced by default.

Renderer updates:
Update generated Claude workflow JS so the Objective Gate agent no longer gets a huge manual command block by default.

Instead, buildGatePrompt(step, gateConfig, attempt) should instruct the gate agent:

  You are the OBJECTIVE BUILD GATE.
  Do not judge design, scope, or quality.
  Do not edit files.
  Run exactly this one AIWK command.
  Return the JSON it prints.
  If the command fails, return the JSON/error exactly and include the evidence/log paths if present.

Generated command should include:
- repo path
- aiwk config path
- workflow spec path
- gate name
- step id
- attempt number

The generated JS should still define:
- GATE_SCHEMA
- buildGatePrompt
- formatGateResult
- computeGateClean
- gateClean
- accepted = gateClean && review.accepted

But GATE_SCHEMA should now include:
- status
- setup_rc
- build_rc
- test_rc
- result_rc
- check_results
- gate_clean
- evidence_path
- log_path
- raw_tail

Keep JS computeGateClean as the source of enforcement in the workflow. Do not merely trust gate_clean. The Python gate runner reports gate_clean as evidence, but generated JS should still recompute from rc/counts.

Workflow config:
Update the runtime validation project if it exists:

  ~/dev/.aiwk/aiwk_runtime_validation/workflow.yaml

Keep its objective gate tiny and deterministic:
- setup: python --version
- build: python -m py_compile tests/test_runtime_marker.py
- test: python -m unittest discover -s tests -p "test_*.py"
- result: true
- check: no FORBIDDEN_MARKER

Generated workflow should call:

  ~/dev/aiwk/.venv/bin/python -m aiwk gate-run ...

If AIWK cannot reliably know the venv Python path, use sys.executable captured in aiwk.yaml or generated scripts if that already exists. If no such mechanism exists, use the current interpreter path during render/init and document the assumption. Do not fall back to system Python silently.

Tests to add/update:

1. CLI tests for gate-run:
- Creates a temp target repo/project.
- Adds a workflow.yaml objective gate with passing commands.
- Runs `python -m aiwk gate-run ...`.
- Asserts stdout JSON has setup_rc/build_rc/test_rc/result_rc.
- Asserts evidence_path exists.
- Asserts log_path exists.
- Asserts gate_clean true.

2. Failing command test:
- build command exits 7.
- gate-run exits successfully or nonzero? Choose one and document it.
Preferred:
  - gate-run process exits 0 if it successfully captured the gate evidence, even when gate_clean false.
  - stdout JSON has gate_clean false and build_rc 7.
- This distinction is important: command failure is evidence, not AIWK runner failure.

3. Config error test:
- unknown gate name should exit nonzero and print status:error.

4. Check-count test:
- Create a file containing FORBIDDEN_MARKER.
- Run gate-run.
- Assert check_results count > max_count.
- Assert gate_clean false.

5. Generated JS tests:
Generated JS with objective gate contains:
- aiwk gate-run
- evidence_path
- log_path
- gate_clean
- computeGateClean
- accepted = gateClean && !!(review && review.accepted)
- OBJECTIVE BUILD GATE
- Do not edit files
- Run exactly this one AIWK command

Generated JS should no longer contain the old long manual instruction:
- “Run this block verbatim” should not appear, unless retained only in docs/tests for legacy mode.
- Long setup/build/test commands should not be in the generated JS body except as part of workflow config serialization if unavoidable.
Prefer not to inline entire command blocks in the prompt.

6. Runtime compatibility tests:
Generated JS must still:
- include meta.name
- not include export default
- not include process.env
- not include permissionMode
- not include env:
- preserve onlyStep/fromStep/preflightSummary/handoffPath/beadsSnapshot
- preserve mature markers:
  - MAX_DEV_RED_CYCLES
  - MAX_REVIEW_ATTEMPTS
  - SCOPING TEST WRITER
  - ADVERSARIAL RED TEAM
  - DEVELOPER FIX PASS
  - Code Reviewer
  - commitAgentPrompt

Commands to run:

  cd ~/dev/aiwk
  ~/dev/aiwk/.venv/bin/python -m pytest -q

Regenerate all workflows:

  for cfg in ~/dev/.aiwk/*/aiwk.yaml; do
    ~/dev/aiwk/.venv/bin/aiwk render claude-workflow --config "$cfg"
  done

Syntax check all generated workflows using available Node:

  for js in ~/dev/.aiwk/*/generated/*.js; do
    echo "== $js =="
    node --check "$js"
  done

If node is not on PATH but VS Code bundled Node is available, use that and report the path.

Run gate-run directly on runtime validation:

  ~/dev/aiwk/.venv/bin/python -m aiwk gate-run \
    --config ~/dev/.aiwk/aiwk_runtime_validation/aiwk.yaml \
    --gate default \
    --step RUNTIME_SS0 \
    --attempt 1 \
    --repo ~/dev/aiwk_runtime_validation_target

Then inspect:
- stdout JSON
- evidence_path
- log_path

Stop rules:
Stop and report if:
- Adding gate-run requires a large rewrite of workflow parsing.
- Existing generated workflows break runtime compatibility.
- The generated JS must rely on process.env or export default.
- Tests fail after 2-3 serious fix attempts.
- You are tempted to hardcode robotics commands into AIWK core.

Final report format:
Report exactly:

  AIWK source files changed:
  Tests added/changed:
  CLI commands added:
  Workflow.yaml/config changes:
  Generated workflow files updated:
  Commands run:
  Test results:
  Gate-run direct result:
  Evidence/log paths produced:
  Node syntax results:
  Runtime validation request to run next:
  Remaining limitations:
  Recommended next pass:

Important:
Do not claim Claude runtime success. I will run the generated Claude Workflow runtime validation myself after this patch.