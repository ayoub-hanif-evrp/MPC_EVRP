from hashlib import sha256

import pytest

from evrp import reference_extensions
from evrp.reference import ReferenceFailure
from evrp.storage import ROOT, save_json, verify_text_digest
from scripts.extend_mp_reference_coverage import construct
from tests.test_simulator import synthetic


def test_text_digest_accepts_only_newline_transport(tmp_path):
    path = tmp_path / "artifact.json"
    windows = b'{\r\n  "value": 1\r\n}\r\n'
    path.write_bytes(windows)
    expected = sha256(windows).hexdigest()
    assert not verify_text_digest(path, expected)
    path.write_bytes(windows.replace(b"\r\n", b"\n"))
    assert verify_text_digest(path, expected)
    path.write_bytes(path.read_bytes().replace(b"1", b"2"))
    with pytest.raises(ValueError, match="beyond line-ending"):
        verify_text_digest(path, expected)


def test_mp_witness_loader_checks_digest_identity_and_replay(tmp_path, monkeypatch):
    instance = synthetic(release=5).instance
    reference = construct(instance)
    artifact = tmp_path / "reference.json"
    reference.save(artifact)
    inventory = tmp_path / "inventory.json"
    row = dict(instance=instance.name, physical_witness=True, instance_sha256=instance.sha256,
               artifact=artifact.relative_to(ROOT).as_posix(),
               artifact_sha256=sha256(artifact.read_bytes()).hexdigest(),
               reference_id=reference.identifier)
    save_json(inventory, dict(rows=[row]))
    monkeypatch.setattr(reference_extensions, "INVENTORY", inventory)
    assert reference_extensions.load_mp_witness(instance).identifier == reference.identifier
    row["reference_id"] = "wrong"
    save_json(inventory, dict(rows=[row]))
    with pytest.raises(ReferenceFailure, match="canonical content"):
        reference_extensions.load_mp_witness(instance)
