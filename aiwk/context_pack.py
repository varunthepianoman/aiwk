from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from .config import Config
from .git_utils import git_snapshot, relevant_dirty_files, run_git


def _load_json(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"evidence_path": str(path), "error": str(exc)}
    if not isinstance(value, dict):
        return {"evidence_path": str(path), "error": "evidence is not a JSON object"}
    return value


def create_context_pack(
    config: Config,
    config_path: Path,
    phase: str,
    step: str | None = None,
    include_diff: bool = False,
    max_diff_lines: int = 80,
    gate_evidence_path: Path | None = None,
    beads_snapshot_path: Path | None = None,
) -> dict[str, str]:
    if max_diff_lines < 0:
        raise ValueError("max_diff_lines must be non-negative")
    repo = Path(config.repo).expanduser().resolve()
    root = config_path.resolve().parent
    state, logs = root / "state", root / "logs"
    state.mkdir(exist_ok=True)
    logs.mkdir(exist_ok=True)
    snap = git_snapshot(repo)
    changed = snap["changed_files"]
    relevant = relevant_dirty_files(changed, config.relevant_paths)  # type: ignore[arg-type]
    diff_stat_result = run_git(repo, "diff", "--stat", "HEAD", check=False)
    diff_result = run_git(repo, "diff", "HEAD", check=False)
    diff_lines = diff_result.stdout.splitlines()
    diff_excerpt = "\n".join(diff_lines[:max_diff_lines]) if include_diff else ""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs / f"context_{phase}_{stamp}.log"
    log_path.write_text(
        f"git status --short\n{snap['status_output']}\n"
        f"git diff --stat HEAD\n{diff_stat_result.stdout}{diff_stat_result.stderr}\n"
        f"git diff HEAD\n{diff_result.stdout}{diff_result.stderr}",
        encoding="utf-8",
    )
    if gate_evidence_path is None:
        candidates = sorted((state / "gates").glob("*.json")) if (state / "gates").is_dir() else []
        gate_evidence_path = candidates[-1] if candidates else None
    gate_evidence = _load_json(gate_evidence_path)
    objective_gate = {
        "evidence_path": str(gate_evidence_path) if gate_evidence_path else "",
        "log_path": str(gate_evidence.get("log_path", "")) if gate_evidence else "",
        "gate_clean": gate_evidence.get("gate_clean") if gate_evidence else None,
        "summary": (
            f"gate={gate_evidence.get('gate')} clean={gate_evidence.get('gate_clean')} "
            f"build={gate_evidence.get('build_rc')} test={gate_evidence.get('test_rc')} result={gate_evidence.get('result_rc')}"
            if gate_evidence else "No objective gate evidence supplied."
        ),
    }
    beads_snapshot = ""
    if beads_snapshot_path:
        beads_snapshot = beads_snapshot_path.expanduser().read_text(encoding="utf-8")
    context_path = state / f"{phase}_context.json"
    handoff_path = state / f"{phase}_handoff.md"
    next_instructions = "Read the project spec, invariants, gates, and this handoff before editing; verify repository state before continuing."
    recent_results = [str(path) for path in sorted(state.glob("*result*.json"))[-5:]]
    context = {
        "project": config.project,
        "phase": phase,
        "step": step,
        "repo": str(repo),
        "head": snap["head"],
        "branch": snap["branch"],
        "status_short": snap["status_output"],
        "dirty_relevant": bool(relevant),
        "dirty_relevant_files": relevant,
        "relevant_dirty_files": relevant,
        "changed_files": changed,
        "diff_stat": diff_stat_result.stdout.strip(),
        "diff_excerpt": diff_excerpt,
        "preflight": {"status": "dirty" if relevant else "ok", "log_path": str(log_path)},
        "objective_gate": objective_gate,
        "beads": {"snapshot": beads_snapshot, "notes": str(beads_snapshot_path or "")},
        "recent_workflow_results": recent_results,
        "summary": "",
        "decisions": [],
        "known_failures": [],
        "next_agent_instructions": next_instructions,
        "log_paths": [str(log_path)],
        "log_path": str(log_path),
    }
    context_path.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
    handoff_path.write_text(
        f"# AIWK Handoff: {phase}\n\n"
        "## Current state\n\n"
        f"- Project: `{config.project}`\n- Repo: `{repo}`\n- Step: `{step or 'not specified'}`\n"
        f"- Branch: `{snap['branch']}`\n- HEAD: `{snap['head'] or 'unborn'}`\n"
        f"- Dirty relevant: `{bool(relevant)}`\n- Changed files: {', '.join(changed) or 'none'}\n\n"
        f"## What changed\n\n```text\n{diff_stat_result.stdout.strip()}\n```\n\n"
        + (f"### Targeted diff excerpt\n\n```diff\n{diff_excerpt}\n```\n\n" if include_diff else "")
        + "## Key evidence\n\n"
        f"- Preflight/context log: `{log_path}`\n"
        f"- Objective gate evidence: `{objective_gate['evidence_path'] or 'none'}`\n"
        f"- Objective gate log: `{objective_gate['log_path'] or 'none'}`\n"
        f"- Objective gate summary: {objective_gate['summary']}\n"
        f"- Beads snapshot file: `{beads_snapshot_path or 'none'}`\n\n"
        "## Known failures / blockers\n\nTODO\n\n"
        "## Decisions / invariants to preserve\n\nTODO\n\n"
        f"## Next-agent instructions\n\n{next_instructions}\n",
        encoding="utf-8",
    )
    return {
        "status": "ok", "handoff_path": str(handoff_path),
        "context_path": str(context_path), "log_path": str(log_path),
    }
