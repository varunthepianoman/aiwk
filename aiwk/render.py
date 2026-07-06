from __future__ import annotations

from pathlib import Path

from .config import load_config
from .renderers.claude_workflow import render_claude_workflow
from .workflow_spec import load_workflow_spec


def render(config_path: Path, workflow_spec_path: Path | None = None, out_path: Path | None = None) -> dict[str, str]:
    config_path = config_path.expanduser().resolve()
    config = load_config(config_path)
    project_root = config_path.parent
    workflow_spec_path = (workflow_spec_path or project_root / "workflow.yaml").expanduser().resolve()
    out_path = (out_path or project_root / "generated" / f"{config.project}.claude_workflow.js").expanduser().resolve()
    spec = load_workflow_spec(workflow_spec_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        render_claude_workflow(config, config_path, spec, workflow_spec_path),
        encoding="utf-8",
    )
    return {"status": "rendered", "workflow_spec": str(workflow_spec_path), "output_path": str(out_path)}
