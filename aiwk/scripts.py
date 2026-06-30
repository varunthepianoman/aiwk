from __future__ import annotations

from pathlib import Path
import shlex


def script_text(command: str, config_path: str | Path) -> str:
    config = shlex.quote(str(Path(config_path).resolve()))
    extra = {
        "preflight": "",
        "context-pack": ' --phase "${1:?usage: context_pack.sh PHASE_ID}"',
        "checkpoint": ' --step "${1:?usage: checkpoint_commit.sh STEP_ID}"',
    }[command]
    return f"#!/bin/sh\nset -eu\npython -m aiwk {command} --config {config}{extra}\n"


def write_scripts(scripts_dir: Path, config_path: Path) -> None:
    names = {
        "preflight.sh": "preflight",
        "context_pack.sh": "context-pack",
        "checkpoint_commit.sh": "checkpoint",
    }
    for name, command in names.items():
        path = scripts_dir / name
        path.write_text(script_text(command, config_path), encoding="utf-8")
        path.chmod(0o755)

