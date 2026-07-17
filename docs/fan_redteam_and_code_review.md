# Task: Add two optional, placeable modules to AIWK — Code-Review agents and Fanned Red-Team agents

## Context — the AIWK architecture you're extending

AIWK is a Python workflow codegen tool at `/home/varunkamat/dev/aiwk`. It reads a
YAML `WorkflowSpec` and renders it to a Claude Agent SDK workflow script.

Key files (read these first, do not redesign the architecture):
- `aiwk/workflow_spec.py` — the provider-neutral spec dataclasses + YAML reader.
  - `SUPPORTED_PHASES = {"scope","discovery","dev","redteam","review","commit"}`
  - `WorkflowStep(id,title,model,effort,phases,prompt,objective_gate,commit,discovery)`
  - Per-feature config is a frozen dataclass (see `DiscoveryConfig`,
    `ContextEconomyConfig`, `ObjectiveGate`) loaded by a `_load_*` helper and
    threaded onto `WorkflowSpec`/`WorkflowStep`.
- `aiwk/renderers/claude_workflow.py` (~1331 LOC) — emits the JS workflow. Phases
  become agents here. Existing `redteam` and `review` roles already exist:
  `roleFor`/role routing (~line 800), `buildReviewerPrompt` (~919),
  `REVIEW_SCHEMA` (~324), `reviewAccepted` (~849), `MAX_REVIEW_ATTEMPTS` (~183).
- `aiwk/coordinator.py` — routing prose; mentions Scope/Developer/Red Team/
  Objective Gate/Reviewer/Commit and `startAtRole` intra-step entry points.
- `aiwk/templates.py` — starter templates (`generic`, `ros2_refactor`,
  `bugfix_redteam`) via `_step(...)`.

Both new features are **modules the workflow author opts into per step and places
where they want** — exactly like `discovery` today (a phase you can include or
omit, with its own config block). Follow the `DiscoveryConfig` precedent for the
shape of everything.

## Design constraints (must follow)
1. **Opt-in and placeable.** Neither module runs unless the step's spec asks for
   it. The author controls placement (which step, and — for review — before or
   after the red-team round). Default OFF; existing specs must render byte-identically
   when the new blocks are absent. Add a regression test asserting this.
2. **Backward compatible.** New YAML keys are optional with safe defaults. Do not
   change the meaning of the existing `review` or `redteam` phases for specs that
   don't opt in.
3. **Follow existing idioms.** Frozen dataclass + `_load_*` helper + validation in
   `load_workflow_spec`; render via a helper in `claude_workflow.py` that mirrors
   how `redteam`/`review` agents are already emitted. Reuse the StructuredOutput
   schema pattern (`REVIEW_SCHEMA`, the redteam findings schema) — don't invent a
   new reporting shape.
4. **Tests.** Add unit tests under `tests/` for spec-loading (defaults, validation
   errors) and a render snapshot test for each new module both present and absent.

---

## Feature 1: Code-Review agent module (`review` phase, wired to `/code-review`)

Today the `review` phase emits a reviewer agent driven by `buildReviewerPrompt`.
Add an **optional code-review sub-step** that invokes the `/code-review` skill on
the current diff as a *cheap, narrow filter* — distinct from the existing holistic
reviewer.

Requirements:
- New config dataclass `CodeReviewConfig` (mirror `DiscoveryConfig`):
  - `enabled: bool = False`
  - `placement: str = "post_dev"` — one of `{"post_dev","pre_redteam","final"}`.
    `post_dev`/`pre_redteam` = run on each dev/fix diff before the red-team round
    (the cheap-filter position). `final` = one comprehensive pass at end of step.
  - `effort: str = "medium"` — passed through to the `/code-review` invocation
    (low/medium/high/max).
  - `apply_fixes: bool = False` — if true, invoke with `--fix`; else review-only.
  - `scope: str = "diff"` — `"diff"` (changed files only) or `"step"` (all files
    the step touched).
- Thread it onto `WorkflowStep` (per-step) with an optional top-level default on
  `WorkflowSpec`, exactly like `DiscoveryConfig`.
- Validate: `placement` and `effort` in their enums; `enabled` requires the step
  to also include a `dev` phase (nothing to review otherwise).
- In `claude_workflow.py`, emit an agent (or role branch) at the chosen placement
  that calls the `/code-review` skill via the Skill mechanism the agents already
  have, scoped per `scope`, at the configured `effort`, with `--fix` when
  `apply_fixes`. It reports through a StructuredOutput schema (reuse/extend
  `REVIEW_SCHEMA`; findings must be machine-readable so the coordinator can route).
- A blocking code-review finding at `pre_redteam` should short-circuit back to
  dev/fix **before** spending a red-team cycle — same routing shape the reviewer
  rejection already uses.

Rationale to encode in comments: `/code-review` reads the diff and catches
diff-readable logic bugs (e.g. a fix that edits one branch and forgets another)
for the cost of one pass, so the expensive red-team harness work is reserved for
behavioral/protocol/security defects that actually need runtime adversarial proof.

---

## Feature 2: Fanned Red-Team module (parallel attack lenses)

Today `redteam` emits a single adversarial agent. Add an optional **fan mode**:
N red-team agents run in parallel, each with a distinct, blindered attack-lens
mandate, and each finding is adversarially verified before it's reported.

Requirements:
- New config dataclass `RedTeamFanConfig` (mirror `DiscoveryConfig`):
  - `enabled: bool = False` — when false, keep today's single-agent behavior
    unchanged.
  - `lenses: list[RedTeamLens] = []` — author-designed, in advance (see below).
  - `verify: bool = True` — run the adversarial verify stage per finding.
  - `verify_votes: int = 1` — number of independent refuters per finding; a
    finding survives only if `< majority` refute it.
  - `model`/`effort` for the lens agents (defaults `opus`/`high`).
- `RedTeamLens` dataclass: `key: str` (kebab-case id), `prompt: str` (the mandate
  — should cite the spec scenario/surface it attacks). Validate keys are unique
  and non-empty; `enabled` requires ≥2 lenses (a fan of one is just the single
  agent).
- YAML shape (per step):
  ```yaml
  redteam_fan:
    enabled: true
    verify: true
    verify_votes: 3
    lenses:
      - key: payload-bound
        prompt: "Attack the receive-boundary payload limit ..."
      - key: fault-drop
        prompt: "Attack connection disposition after a framing fault ..."
In claude_workflow.py, when fan is enabled for a step's redteam phase, emit the pipeline below instead of the single red-team agent. Each lens is one agent labelled attack:<key>; each finding is verified by verify_votes refuters labelled verify:<key>. Aggregate confirmed findings into the same redteam StructuredOutput the coordinator already consumes (so downstream routing, cycles, and convergence detection are unchanged).
Preserve the existing redteam findings schema and the failures_found / all_passed status contract — the fan is a different way of producing the same findings report, not a new report type.
Reference implementation of the fan pipeline (emit JS shaped like this)
This is the exact pattern the fan should generate in the rendered workflow. Adapt
label/schema names to the existing renderer conventions:


export const meta = {
  name: 'dataplane-redteam-parallel',
  description: 'Red-team the data plane across independent attack lenses, verify each finding',
  phases: [{ title: 'Attack' }, { title: 'Verify' }],
}

const LENSES = [
  { key: 'payload-bound',    prompt: 'Attack the receive-boundary payload limit: oversized/negative/unaligned payload_length, unbounded allocation, DoS. Cite spec + write a deterministic repro.' },
  { key: 'fault-drop',       prompt: 'Attack connection disposition after a framing fault (bad magic, malformed frame): must the connection drop per Scenario 2? Find keep-open desync.' },
  { key: 'session-teardown', prompt: 'Attack session-state teardown on fd drop/disconnect: is_established() vs is_client_connected() consistency, spin hazards (Scenario 6).' },
  { key: 'serialized-txn',   prompt: 'Attack the strictly-serialized transactions (send_ping): ACK timeout, wrong-type ACK, write-failure branches. Must close per Scenario 4.' },
]

const results = await pipeline(
  LENSES,
  lens => agent(lens.prompt, { label: `attack:${lens.key}`, phase: 'Attack', schema: FINDINGS_SCHEMA }),
  review => parallel((review.findings || []).map(f => () =>
    agent(`Adversarially verify — try to REFUTE this finding, default to refuted if uncertain: ${f.detail}`,
          { label: `verify:${f.id}`, phase: 'Verify', schema: VERDICT_SCHEMA })
      .then(v => ({ ...f, verdict: v }))))
)
const confirmed = results.flat().filter(Boolean).filter(f => f.verdict?.real)
return { confirmed }
Notes on the pattern (encode as comments):

pipeline (not parallel for the outer stage) so each lens's findings verify as soon as that lens finishes — the fast lenses aren't blocked by the slow one.
Lenses are blind to each other on purpose: that diversity of mandate is what collapses many serial red-team cycles into one round.
verify_votes > 1 → run that many refuters per finding in an inner parallel and keep the finding only if fewer than a majority refute it.
Optional stretch (implement only if cheap): completeness critic
After the fan, an optional single agent that reads all confirmed findings and asks
"what attack surface did no lens cover?" — its answer is surfaced as a suggested
new lens for the author's next round. Gate behind redteam_fan.completeness_critic: bool = False. Do not auto-add lenses; just report the gap.

Deliverables
CodeReviewConfig, RedTeamFanConfig, RedTeamLens dataclasses + _load_* helpers + validation in aiwk/workflow_spec.py, threaded onto WorkflowStep/WorkflowSpec.
Renderer support in aiwk/renderers/claude_workflow.py for both modules, reusing existing role/schema/routing machinery.
A worked YAML example for each module (add to examples/ or a template in aiwk/templates.py).
Tests under tests/: spec-load defaults + validation errors for both; render snapshot with each module present AND absent (absent must be byte-identical to today).
Short docs note in README.md/docs/ describing when to use each and the placement options.
Do NOT
Do not make either module run by default or change existing specs' output.
Do not replace the existing single-agent redteam or the holistic reviewer; these are additive/alternative modes.
Do not invent a new findings-report shape; reuse the existing StructuredOutput schemas so the coordinator's cycle/convergence routing is untouched.


