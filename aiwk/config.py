"""Configuration loading and path derivation without third-party YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json


@dataclass(eq=True)
class Config:
    project: str
    repo: str
    workflow_folder: str
    project_folder: str
    relevant_paths: list[str] = field(default_factory=list)
    ignored_scratch_dirs: list[str] = field(default_factory=lambda: ["z_random/"])
    test_commands: dict[str, str] = field(default_factory=dict)


def project_folder(workflow_folder: str | Path, project: str) -> Path:
    return Path(workflow_folder) / project


def _scalar(value: str):
    value = value.strip()
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if value in {"null", "~"}:
        return None
    if value in {"true", "false"}:
        return value == "true"
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return json.loads(value) if value[0] == '"' else value[1:-1].replace("''", "'")
    return value


def load_config(path: str | Path) -> Config:
    """Read the small YAML subset used by aiwk configuration files."""
    data: dict[str, object] = {}
    current: str | None = None
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw.startswith((" ", "\t")):
            if current is None:
                raise ValueError(f"Unexpected indentation on line {number}")
            stripped = raw.strip()
            if stripped.startswith("- "):
                if not isinstance(data[current], list):
                    data[current] = []
                data[current].append(_scalar(stripped[2:]))  # type: ignore[union-attr]
            elif ":" in stripped:
                key, value = stripped.split(":", 1)
                if not isinstance(data[current], dict):
                    data[current] = {}
                parsed_key = _scalar(key)
                data[current][str(parsed_key)] = _scalar(value)  # type: ignore[index]
            else:
                raise ValueError(f"Unsupported YAML on line {number}")
            continue
        if ":" not in raw:
            raise ValueError(f"Expected key/value on line {number}")
        key, value = raw.split(":", 1)
        current = key.strip()
        data[current] = _scalar(value) if value.strip() else []
    required = {"project", "repo", "workflow_folder", "project_folder"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(sorted(missing))}")
    return Config(**data)  # type: ignore[arg-type]


def _quote(value: str) -> str:
    # JSON strings are valid YAML strings and avoid surprises around ':' and '#'.
    return json.dumps(value)


def dump_config(config: Config, path: str | Path) -> None:
    lines = [
        f"project: {_quote(config.project)}",
        f"repo: {_quote(config.repo)}",
        f"workflow_folder: {_quote(config.workflow_folder)}",
        f"project_folder: {_quote(config.project_folder)}",
    ]
    for key, value in (
        ("relevant_paths", config.relevant_paths),
        ("ignored_scratch_dirs", config.ignored_scratch_dirs),
    ):
        lines.append(f"{key}:" if value else f"{key}: []")
        lines.extend(f"  - {_quote(item)}" for item in value)
    if config.test_commands:
        lines.append("test_commands:")
        lines.extend(f"  {_quote(k)}: {_quote(v)}" for k, v in config.test_commands.items())
    else:
        lines.append("test_commands: {}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
