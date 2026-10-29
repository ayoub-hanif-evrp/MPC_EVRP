"""Read-only path resolution for future research_v2 studies."""

from pathlib import Path, PureWindowsPath
import os
import re

from evrp.storage import ROOT


OUTPUT_KINDS = frozenset({"baseline", "proposed", "ablations", "validation", "paper"})
_STUDY_ID = re.compile(r"[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*\Z", re.ASCII)
_FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z", re.ASCII)
_WINDOWS_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                     *(f"lpt{i}" for i in range(1, 10))}


def _safe_component(value: str, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or len(value) > 80 or not pattern.fullmatch(value):
        raise ValueError(f"Invalid {label}: {value!r}")
    if value.split(".", 1)[0].lower() in _WINDOWS_RESERVED or value.endswith("."):
        raise ValueError(f"Invalid {label}: {value!r}")
    return value


def validate_study_id(study_id: str) -> str:
    return _safe_component(study_id, _STUDY_ID, "study identifier")


def _root(repo_root: Path) -> Path:
    return Path(repo_root).resolve()


def _reject_links(root: Path, path: Path) -> None:
    if not path.is_relative_to(root):
        raise ValueError("Path escapes repository root")
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ValueError(f"Linked path component is not allowed: {current}")


def study_path(study_id: str, repo_root: Path = ROOT) -> Path:
    root = _root(repo_root)
    path = root / "results" / "research_v2" / validate_study_id(study_id)
    _reject_links(root, path)
    if not path.resolve().is_relative_to(root / "results" / "research_v2"):
        raise ValueError("Study path escapes research_v2 workspace")
    return path


def output_dir(study_id: str, kind: str, repo_root: Path = ROOT) -> Path:
    if kind not in OUTPUT_KINDS:
        raise ValueError(f"Unknown output kind: {kind!r}")
    path = study_path(study_id, repo_root) / kind
    _reject_links(_root(repo_root), path)
    return path


def artifact_path(study_id: str, kind: str, filename: str, repo_root: Path = ROOT) -> Path:
    filename = _safe_component(filename, _FILE_NAME, "artifact filename")
    path = output_dir(study_id, kind, repo_root) / filename
    _reject_links(_root(repo_root), path)
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"Refusing to overwrite existing artifact: {path}")
    return path


def resolve_config(value: str | Path, repo_root: Path = ROOT) -> Path:
    root = _root(repo_root)
    raw = str(value)
    if not raw or (PureWindowsPath(raw).drive and not Path(raw).is_absolute()):
        raise ValueError("Configuration path must be absolute or repository-relative")
    if "\\" in raw and os.name != "nt":
        raise ValueError("Use native or forward-slash configuration paths")
    path = Path(value)
    candidate = path if path.is_absolute() else root / path
    if ".." in candidate.parts:
        raise ValueError("Configuration path must not contain traversal")
    resolved = candidate.resolve()
    configs = root / "configs"
    if not resolved.is_relative_to(configs) or resolved.suffix.lower() not in {".yaml", ".yml"}:
        raise ValueError("Configuration must be a YAML file inside repository configs/")
    _reject_links(root, candidate.absolute())
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved
