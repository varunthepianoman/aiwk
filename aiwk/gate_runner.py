"""Deterministic objective-gate execution with durable evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import platform
from pathlib import Path
import re
import subprocess
import sys
import time

from . import __version__
from .config import load_config
from .workflow_spec import ObjectiveGate, load_workflow_spec


@dataclass
class CommandEvidence:
    command: str
    rc: int
    timed_out: bool
    timeout_seconds: float
    started_at: str
    ended_at: str
    duration_seconds: float
    stdout: str
    stderr: str

    def public(self) -> dict[str, object]:
        data = asdict(self)
        data["stdout_tail"] = data.pop("stdout")[-2000:]
        data["stderr_tail"] = data.pop("stderr")[-2000:]
        return data


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_component(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return (sanitized or "unnamed")[:100]


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode(errors="replace") if isinstance(value, bytes) else value


def _run_command(command: str, repo: Path, timeout_seconds: float) -> CommandEvidence:
    started_at = _now()
    start = time.monotonic()
    try:
        completed = subprocess.run(
            command, shell=True, cwd=repo, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
            timeout=timeout_seconds,
        )
        rc, stdout, stderr, timed_out = (
            completed.returncode, completed.stdout, completed.stderr, False
        )
    except subprocess.TimeoutExpired as exc:
        rc, stdout, stderr, timed_out = 124, _text(exc.stdout), _text(exc.stderr), True
        stderr = (stderr + f"\ncommand timed out after {timeout_seconds:g} seconds").strip()
    return CommandEvidence(
        command, rc, timed_out, timeout_seconds, started_at, _now(),
        round(time.monotonic() - start, 6), stdout, stderr,
    )


def _log_command(log_parts: list[str], label: str, result: CommandEvidence) -> None:
    log_parts.extend([
        f"=== {label} ===", f"$ {result.command}", f"rc={result.rc}",
        f"timed_out={str(result.timed_out).lower()}",
        f"timeout_seconds={result.timeout_seconds:g}",
        f"duration_seconds={result.duration_seconds}",
        "--- stdout ---", result.stdout, "--- stderr ---", result.stderr, "",
    ])


def _run_section(
    name: str, commands: list[str], repo: Path, timeout_seconds: float,
    log_parts: list[str], raw_parts: list[str],
) -> tuple[int, list[dict[str, object]]]:
    section_rc = 0
    evidence: list[dict[str, object]] = []
    for index, command in enumerate(commands, 1):
        result = _run_command(command, repo, timeout_seconds)
        _log_command(log_parts, f"{name} command {index}", result)
        raw_parts.extend([result.stdout, result.stderr])
        evidence.append(result.public())
        if result.rc != 0:
            section_rc = result.rc
    return section_rc, evidence


def _run_checks(
    gate: ObjectiveGate, repo: Path, log_parts: list[str], raw_parts: list[str]
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for check in gate.checks:
        result = _run_command(check.command, repo, check.timeout_seconds)
        _log_command(log_parts, f"check {check.name}", result)
        raw_parts.extend([result.stdout, result.stderr])
        count = sum(1 for line in result.stdout.splitlines() if line.strip())
        combined = (result.stdout + result.stderr).strip()
        detail = combined[-1000:] if combined else (
            "no matches" if result.rc == 1 and not result.stdout else "no output"
        )
        results.append({
            "name": check.name, "command": check.command, "rc": result.rc,
            "count": count, "max_count": check.max_count,
            "timed_out": result.timed_out, "timeout_seconds": result.timeout_seconds,
            "duration_seconds": result.duration_seconds, "detail": detail,
        })
    return results


def compute_gate_clean(
    build_rc: int, test_rc: int, result_rc: int,
    check_results: list[dict[str, object]],
) -> bool:
    return (
        build_rc == 0 and test_rc == 0 and result_rc == 0
        and all(
            not bool(result.get("timed_out"))
            and int(result["count"]) <= int(result["max_count"])
            for result in check_results
        )
    )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _git_value(repo: Path, *args: str) -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args], text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
    except OSError as exc:
        return None, str(exc)
    if result.returncode:
        return None, result.stderr.strip() or f"git exited {result.returncode}"
    return result.stdout.rstrip(), None


def _canonical_hash(value: object) -> str:
    return _sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def run_objective_gate(
    config_path: Path, gate_name: str, step: str, attempt: int,
    workflow_spec_path: Path | None = None, repo_path: Path | None = None,
) -> dict[str, object]:
    if attempt < 1:
        raise ValueError("Gate attempt must be at least 1")
    config_path = config_path.expanduser().resolve()
    config = load_config(config_path)
    project_root = config_path.parent
    workflow_spec_path = (workflow_spec_path or project_root / "workflow.yaml").expanduser().resolve()
    spec = load_workflow_spec(workflow_spec_path)
    if gate_name not in spec.objective_gates:
        raise ValueError(f"Unknown objective gate: {gate_name}")
    gate = spec.objective_gates[gate_name]
    repo = (repo_path or Path(config.repo)).expanduser().resolve()
    if not repo.is_dir():
        raise ValueError(f"Repository path does not exist: {repo}")

    evidence_dir, log_dir = project_root / "state" / "gates", project_root / "logs" / "gates"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stem = f"{_safe_component(step)}_{_safe_component(gate_name)}_attempt{attempt}_{stamp}"
    evidence_path, log_path = evidence_dir / f"{stem}.json", log_dir / f"{stem}.log"
    head_before, head_before_note = _git_value(repo, "rev-parse", "HEAD")
    status_before, status_before_note = _git_value(repo, "status", "--short")
    log_parts = [f"project={config.project}", f"repo={repo}", f"gate={gate_name}", f"step={step}", f"attempt={attempt}", ""]
    raw_parts: list[str] = []
    sections: dict[str, list[dict[str, object]]] = {}
    section_values: dict[str, int] = {}
    for name, commands, timeout in (
        ("setup", gate.setup_commands, gate.setup_timeout_seconds),
        ("build", gate.build_commands, gate.build_timeout_seconds),
        ("test", gate.test_commands, gate.test_timeout_seconds),
        ("result", gate.result_commands, gate.result_timeout_seconds),
    ):
        section_values[name], sections[name] = _run_section(
            name, commands, repo, timeout, log_parts, raw_parts
        )
    check_results = _run_checks(gate, repo, log_parts, raw_parts)
    head_after, head_after_note = _git_value(repo, "rev-parse", "HEAD")
    status_after, status_after_note = _git_value(repo, "status", "--short")
    log_path.write_text("\n".join(log_parts), encoding="utf-8")
    created_at = _now()
    integrity: dict[str, object] = {
        "evidence_schema_version": 1, "created_at": created_at,
        "aiwk_version": __version__, "python_executable": sys.executable,
        "python_version": platform.python_version(), "platform": platform.platform(),
        "repo_head_before": head_before, "repo_status_before": status_before,
        "repo_head_after": head_after, "repo_status_after": status_after,
        "git_notes": [note for note in (head_before_note, status_before_note, head_after_note, status_after_note) if note],
        "workflow_spec_path": str(workflow_spec_path),
        "workflow_spec_sha256": _file_sha256(workflow_spec_path),
        "aiwk_config_path": str(config_path), "aiwk_config_sha256": _file_sha256(config_path),
        "gate_config_sha256": _canonical_hash(asdict(gate)),
        "log_sha256": _file_sha256(log_path), "evidence_sha256": None,
        "evidence_hash_rule": "SHA-256 of canonical JSON with integrity.evidence_sha256 set to null",
    }
    raw_output = "".join(raw_parts).strip()
    evidence: dict[str, object] = {
        "status": "ok", "project": config.project, "repo": str(repo),
        "gate": gate_name, "step": step, "attempt": attempt,
        "setup_rc": section_values["setup"], "build_rc": section_values["build"],
        "test_rc": section_values["test"], "result_rc": section_values["result"],
        "sections": sections, "check_results": check_results,
        "gate_clean": compute_gate_clean(
            section_values["build"], section_values["test"],
            section_values["result"], check_results,
        ),
        "evidence_path": str(evidence_path), "log_path": str(log_path),
        "raw_tail": raw_output[-4000:], "integrity": integrity,
    }
    integrity["evidence_sha256"] = _canonical_hash(evidence)
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    compact = {key: evidence[key] for key in (
        "status", "project", "repo", "gate", "step", "attempt", "setup_rc",
        "build_rc", "test_rc", "result_rc", "check_results", "gate_clean",
        "evidence_path", "log_path", "raw_tail",
    )}
    compact["integrity"] = {
        key: integrity[key] for key in (
            "evidence_sha256", "log_sha256", "repo_head_before", "repo_head_after"
        )
    }
    return compact
