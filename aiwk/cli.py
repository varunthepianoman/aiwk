from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from .checkpoint import checkpoint
from .config import Config, dump_config, load_config, project_folder
from .context_pack import create_context_pack
from .git_utils import git_snapshot, relevant_dirty_files, run_git
from .scripts import write_scripts


def initialize(project: str, repo: str, workflow_folder: str) -> dict[str, str]:
    root = project_folder(workflow_folder, project)
    for directory in (root / "spec", root / "scripts", root / "state", root / "logs"):
        directory.mkdir(parents=True, exist_ok=True)
    config_path = root / "aiwk.yaml"
    config = Config(project, repo, workflow_folder, str(root))
    dump_config(config, config_path)
    (root / "spec" / "project.spec.md").write_text(
        f"# Project Spec: {project}\n\n## Goal\n\nTODO\n\n## Source of Truth\n\nTODO\n\n"
        "## Non-goals\n\nTODO\n\n## Workflow Notes\n\nTODO\n",
        encoding="utf-8",
    )
    (root / "spec" / "invariants.yaml").write_text("invariants: []\n", encoding="utf-8")
    (root / "spec" / "gates.yaml").write_text("gates: []\n", encoding="utf-8")
    write_scripts(root / "scripts", config_path)
    return {"status": "initialized", "project_folder": str(root), "config_path": str(config_path)}


def preflight(config: Config, config_path: Path) -> dict[str, object]:
    repo = Path(config.repo).expanduser().resolve()
    snap = git_snapshot(repo)
    relevant = relevant_dirty_files(snap["changed_files"], config.relevant_paths)  # type: ignore[arg-type]
    logs = config_path.resolve().parent / "logs"
    logs.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = logs / f"preflight_{stamp}.log"
    verbose = run_git(repo, "status", "--short", "--branch")
    log_path.write_text(verbose.stdout + verbose.stderr, encoding="utf-8")
    return {
        "status": "dirty" if relevant else "ok",
        "project": config.project,
        "repo": config.repo,
        "head": snap["head"],
        "branch": snap["branch"],
        "dirty_relevant": bool(relevant),
        "dirty_relevant_files": relevant,
        "log_path": str(log_path),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="aiwk")
    commands = result.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--project", required=True)
    init.add_argument("--repo", required=True)
    init.add_argument("--workflow-folder", required=True)
    for name in ("preflight", "context-pack", "checkpoint"):
        command = commands.add_parser(name)
        command.add_argument("--config", required=True, type=Path)
        if name == "context-pack":
            command.add_argument("--phase", required=True)
        if name == "checkpoint":
            command.add_argument("--step", required=True)
    return result


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            result = initialize(args.project, args.repo, args.workflow_folder)
        else:
            config = load_config(args.config)
            if args.command == "preflight":
                result = preflight(config, args.config)
            elif args.command == "context-pack":
                result = create_context_pack(config, args.config, args.phase)
            else:
                result = checkpoint(config, args.config, args.step)
        print(json.dumps(result, separators=(",", ":")))
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, separators=(",", ":")), file=sys.stderr)
        raise SystemExit(1) from None

