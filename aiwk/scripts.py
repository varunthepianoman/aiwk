from __future__ import annotations

from pathlib import Path
import shlex
import sys


def script_text(command: str, config_path: str | Path, python_path: str | Path | None = None) -> str:
    config = shlex.quote(str(Path(config_path).resolve()))
    python = shlex.quote(str(python_path or sys.executable))
    if command == "context-pack":
        # context-pack takes optional flags (--include-diff, --max-diff-lines,
        # --beads-snapshot-file, ...). Forward everything after the phase so the
        # wrapper is not limited to a bare phase argument.
        base = f"{python} -m aiwk context-pack --config {config}"
        return (
            "#!/bin/sh\n"
            "set -eu\n"
            'if [ "$#" -eq 0 ]; then\n'
            '  echo "usage: context_pack.sh PHASE_ID [context-pack options] OR '
            'context_pack.sh --phase PHASE [context-pack options]" >&2\n'
            "  exit 2\n"
            "fi\n"
            'if [ "${1#--}" != "$1" ]; then\n'
            f'  exec {base} "$@"\n'
            "fi\n"
            'PHASE="$1"\n'
            "shift\n"
            f'exec {base} --phase "$PHASE" "$@"\n'
        )
    extra = {
        "preflight": "",
        "checkpoint": ' --step "${1:?usage: checkpoint_commit.sh STEP_ID}"',
    }[command]
    return f"#!/bin/sh\nset -eu\n{python} -m aiwk {command} --config {config}{extra}\n"


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
