from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from .config import Config
from .git_utils import git_snapshot, relevant_dirty_files, run_git


def create_context_pack(config: Config, config_path: Path, phase: str) -> dict[str, str]:
    repo = Path(config.repo).expanduser().resolve()
    root = config_path.resolve().parent
    state, logs = root / "state", root / "logs"
    state.mkdir(exist_ok=True)
    logs.mkdir(exist_ok=True)
    snap = git_snapshot(repo)
    changed = snap["changed_files"]
    relevant = relevant_dirty_files(changed, config.relevant_paths)  # type: ignore[arg-type]
    diff = run_git(repo, "diff", "--stat", "HEAD", check=False)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs / f"context_{phase}_{stamp}.log"
    log_path.write_text(
        f"git status --short\n{snap['status_output']}\ngit diff --stat HEAD\n{diff.stdout}{diff.stderr}",
        encoding="utf-8",
    )
    context_path = state / f"{phase}_context.json"
    handoff_path = state / f"{phase}_handoff.md"
    context = {
        "phase": phase,
        "head": snap["head"],
        "branch": snap["branch"],
        "relevant_dirty_files": relevant,
        "changed_files": changed,
        "diff_stat": diff.stdout.strip(),
        "log_paths": [str(log_path)],
        "summary": "",
        "decisions": [],
        "known_failures": [],
        "next_agent_instructions": "",
    }
    context_path.write_text(json.dumps(context, indent=2) + "\n", encoding="utf-8")
    handoff_path.write_text(
        f"# Context Handoff: {phase}\n\n"
        f"- Head: `{snap['head'] or 'unborn'}`\n- Branch: `{snap['branch']}`\n"
        f"- Relevant dirty files: {', '.join(relevant) or 'none'}\n"
        f"- Changed files: {', '.join(changed) or 'none'}\n"
        f"- Verbose log: `{log_path}`\n\n## Diff Stat\n\n```text\n{diff.stdout.strip()}\n```\n\n"
        "## Summary\n\nTODO\n\n## Decisions\n\nTODO\n\n## Known Failures\n\nTODO\n\n"
        "## Next-Agent Instructions\n\nTODO\n",
        encoding="utf-8",
    )
    return {"status": "ok", "handoff_path": str(handoff_path), "context_path": str(context_path), "log_path": str(log_path)}

