"""File-based research artifacts, with benchmark write protection."""

from dataclasses import asdict, is_dataclass
from hashlib import sha256
from pathlib import Path
import json
import gzip
from time import sleep

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "opre.2016.1535-sm-data"
BENCHMARK = DATASET / "instances" / "instances_format_1"
BENCHMARK_ARCS = DATASET / "instances" / "instances_format_2"
PUBLISHED_SOLUTIONS = DATASET / "solutions"


def writable_path(path: str | Path) -> Path:
    path = Path(path)
    if path.resolve().is_relative_to(BENCHMARK.resolve()):
        raise ValueError("Original benchmark files are read-only")
    resolved = (path if path.is_absolute() else ROOT / path).resolve()
    allowed = (ROOT / "results").resolve()
    if not allowed.is_relative_to(ROOT.resolve()) or not resolved.is_relative_to(allowed):
        raise ValueError("Generated research files must stay inside repository results/")
    path = resolved
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def canonical(data: object) -> str:
    return json.dumps(asdict(data) if is_dataclass(data) else data,
                      sort_keys=True, separators=(",", ":"), allow_nan=False)


def identifier(data: object) -> str:
    return sha256(canonical(data).encode("utf-8")).hexdigest()


def save_json(path: str | Path, data: object) -> None:
    path = writable_path(path)
    encoded = json.dumps(asdict(data) if is_dataclass(data) else data,
                         indent=2, sort_keys=True, allow_nan=False) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    if path.suffix == ".gz":
        with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=3) as stream:
            stream.write(encoded)
    else:
        temporary.write_text(encoded, encoding="utf-8")
    # Windows readers/sync agents can momentarily deny an atomic replacement.
    for attempt in range(6):
        try:
            temporary.replace(path)
            break
        except PermissionError:
            if attempt == 5:
                raise
            sleep(.02 * 2**attempt)


def load_json(path: str | Path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8"))


def verify_text_digest(path: str | Path, expected: str) -> bool:
    """Verify a Git text artifact, returning True only for proven newline transport."""
    path = Path(path)
    if sha256(path.read_bytes()).hexdigest() == expected:
        return False
    normalized = path.read_text(encoding="utf-8").encode("utf-8")
    if expected in {sha256(normalized).hexdigest(),
                    sha256(normalized.replace(b"\n", b"\r\n")).hexdigest()}:
        return True
    raise ValueError(f"Text artifact differs beyond line-ending transport: {path}")


def benchmark_hashes() -> dict[str, str]:
    return {p.relative_to(DATASET).as_posix(): sha256(p.read_bytes()).hexdigest()
            for p in sorted(DATASET.rglob("*")) if p.is_file() and p.name != ".DS_Store"}
