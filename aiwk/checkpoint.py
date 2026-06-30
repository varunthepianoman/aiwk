from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .git_utils import run_git, validate_repo


def checkpoint(config: Config, config_path: Path, step: str) -> dict[str, object]:
    repo = Path(config.repo).expanduser().resolve()
    validate_repo(repo)
    logs = config_path.resolve().parent / "logs"
    logs.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs / f"checkpoint_{step}_{stamp}.log"
    before = run_git(repo, "status", "--short")
    add = run_git(repo, "add", "-A", check=False)
    staged = run_git(repo, "diff", "--cached", "--quiet", check=False)
    output = ["git status --short", before.stdout, "git add -A", add.stdout, add.stderr]
    if add.returncode:
        log_path.write_text("\n".join(output), encoding="utf-8")
        raise RuntimeError(f"git add failed; see {log_path}")
    if staged.returncode == 0:
        log_path.write_text("\n".join(output), encoding="utf-8")
        return {"status": "nothing_to_commit", "commit_hash": None, "log_path": str(log_path)}
    commit = run_git(repo, "commit", "-m", step, check=False)
    output.extend(["git commit", commit.stdout, commit.stderr])
    log_path.write_text("\n".join(output), encoding="utf-8")
    if commit.returncode:
        raise RuntimeError(f"git commit failed; see {log_path}")
    commit_hash = run_git(repo, "rev-parse", "HEAD").stdout.strip()
    return {"status": "committed", "commit_hash": commit_hash, "log_path": str(log_path)}

