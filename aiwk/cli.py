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
from .templates import TEMPLATE_NAMES, get_template


def initialize(project: str, repo: str, workflow_folder: str, template: str = "generic") -> dict[str, str]:
    root = project_folder(workflow_folder, project)
    for directory in (root / "spec", root / "scripts", root / "state", root / "logs", root / "generated"):
        directory.mkdir(parents=True, exist_ok=True)
    config_path = root / "aiwk.yaml"
    config = Config(project, repo, workflow_folder, str(root))
    dump_config(config, config_path)
    selected = get_template(template, project)
    (root / "workflow.yaml").write_text(selected.workflow, encoding="utf-8")
    (root / "spec" / "project.spec.md").write_text(selected.project_spec, encoding="utf-8")
    (root / "spec" / "invariants.yaml").write_text(selected.invariants, encoding="utf-8")
    (root / "spec" / "gates.yaml").write_text(selected.gates, encoding="utf-8")
    write_scripts(root / "scripts", config_path)
    return {"status": "initialized", "project_folder": str(root), "config_path": str(config_path), "template": template}


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
    init.add_argument("--template", choices=TEMPLATE_NAMES, default="generic")
    templates = commands.add_parser("templates")
    template_commands = templates.add_subparsers(dest="template_command", required=True)
    template_commands.add_parser("list")
    for name in ("preflight", "context-pack", "checkpoint"):
        command = commands.add_parser(name)
        command.add_argument("--config", required=True, type=Path)
        if name == "context-pack":
            command.add_argument("--phase", required=True)
            command.add_argument("--step")
            command.add_argument("--include-diff", action="store_true")
            command.add_argument("--max-diff-lines", type=int, default=80)
            command.add_argument("--gate-evidence", type=Path)
            command.add_argument("--beads-snapshot-file", type=Path)
        if name == "checkpoint":
            command.add_argument("--step", required=True)
    render_command = commands.add_parser("render")
    render_targets = render_command.add_subparsers(dest="render_target", required=True)
    claude = render_targets.add_parser("claude-workflow")
    claude.add_argument("--config", required=True, type=Path)
    claude.add_argument("--workflow-spec", type=Path)
    claude.add_argument("--out", type=Path)
    gate_run = commands.add_parser("gate-run")
    gate_run.add_argument("--config", required=True, type=Path)
    gate_run.add_argument("--workflow-spec", type=Path)
    gate_run.add_argument("--gate", required=True)
    gate_run.add_argument("--step", required=True)
    gate_run.add_argument("--attempt", required=True, type=int)
    gate_run.add_argument("--repo", type=Path)
    return result


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    try:
        if args.command == "init":
            result = initialize(args.project, args.repo, args.workflow_folder, args.template)
        elif args.command == "templates":
            result = {"status": "ok", "templates": list(TEMPLATE_NAMES)}
        elif args.command == "render":
            from .render import render
            result = render(args.config, args.workflow_spec, args.out)
        elif args.command == "gate-run":
            from .gate_runner import run_objective_gate
            result = run_objective_gate(
                args.config,
                args.gate,
                args.step,
                args.attempt,
                args.workflow_spec,
                args.repo,
            )
        else:
            config = load_config(args.config)
            if args.command == "preflight":
                result = preflight(config, args.config)
            elif args.command == "context-pack":
                result = create_context_pack(
                    config, args.config, args.phase, args.step, args.include_diff,
                    args.max_diff_lines, args.gate_evidence, args.beads_snapshot_file,
                )
            else:
                result = checkpoint(config, args.config, args.step)
        print(json.dumps(result, separators=(",", ":")))
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, separators=(",", ":")), file=sys.stderr)
        raise SystemExit(1) from None
