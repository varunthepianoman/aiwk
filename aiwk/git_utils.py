"""Small git subprocess helpers."""

from __future__ import annotations

from pathlib import Path
import subprocess


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def validate_repo(repo: Path) -> None:
    if not repo.is_dir():
        raise ValueError(f"Repository path does not exist: {repo}")
    result = run_git(repo, "rev-parse", "--is-inside-work-tree", check=False)
    if result.returncode or result.stdout.strip() != "true":
        raise ValueError(f"Not a git repository: {repo}")


def git_snapshot(repo: Path) -> dict[str, object]:
    validate_repo(repo)
    head_result = run_git(repo, "rev-parse", "HEAD", check=False)
    branch = run_git(repo, "branch", "--show-current", check=False).stdout.strip()
    status = run_git(repo, "status", "--short")
    changed = [line[3:] for line in status.stdout.splitlines() if len(line) >= 4]
    return {
        "head": head_result.stdout.strip() if head_result.returncode == 0 else None,
        "branch": branch or "HEAD",
        "status_output": status.stdout,
        "changed_files": changed,
    }


def relevant_dirty_files(changed: list[str], relevant_paths: list[str]) -> list[str]:
    if not relevant_paths:
        return list(changed)
    prefixes = [p.rstrip("/") for p in relevant_paths]
    return [p for p in changed if any(p == prefix or p.startswith(prefix + "/") for prefix in prefixes)]

