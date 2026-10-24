import pytest

from evrp.storage import ROOT, load_json, save_json
from evrp import experiments
from scripts import archive_frozen_inputs as archive
from scripts.extend_mp_reference_coverage import construct
from tests.test_simulator import synthetic


def test_cache_target_is_confined_to_its_input_directory(tmp_path):
    row = dict(kind="scenarios", cache_path="results/scenarios/example.json")
    assert archive.cache_target(row, tmp_path) == tmp_path / "scenarios/example.json"
    for path in ("../example.json", "results/scenarios/../../example.json", "results/elsewhere/example.json"):
        with pytest.raises(ValueError, match="escapes"):
            archive.cache_target(row | {"cache_path": path}, tmp_path)
    with pytest.raises(ValueError, match="inside repository results"):
        archive.cache_target(row, ROOT.parent)


def test_restore_preserves_a_conflicting_existing_cache(tmp_path, monkeypatch):
    instance = synthetic(release=5).instance
    reference = construct(instance)
    target = tmp_path / "cache/reference_schedules/example.json"
    reference.save(target)
    before = target.read_bytes()
    archive_root = tmp_path / "archive"
    save_json(archive_root / "manifest.json", dict(inputs=[dict(
        instance=instance.name, kind="reference_schedules",
        cache_path="results/reference_schedules/example.json", identifier="different")]))
    monkeypatch.setattr(archive, "OUTPUT", archive_root)
    monkeypatch.setattr(archive, "validate", lambda _: (1, 0))
    monkeypatch.setattr(archive, "load_instance", lambda _: instance)
    with pytest.raises(ValueError, match="Conflicting existing cache preserved"):
        archive.restore(tmp_path / "cache")
    assert target.read_bytes() == before


def test_all_archived_scenarios_prepare_without_regenerating_inputs(tmp_path, monkeypatch):
    archive.restore(tmp_path / "results")
    manifest = load_json(archive.OUTPUT / "manifest.json")
    references = {row["identifier"]: load_json(archive.OUTPUT / row["artifact"])
                  for row in manifest["inputs"] if row["kind"] == "reference_schedules"}

    def forbidden(*args, **kwargs):
        raise AssertionError("Frozen reproduction must not regenerate references or scenarios")

    monkeypatch.setattr(experiments, "ROOT", tmp_path)
    for name in ("published_full_reference", "solve_reference", "generate"):
        monkeypatch.setattr(experiments, name, forbidden)
    for row in manifest["inputs"]:
        if row["kind"] != "scenarios":
            continue
        scenario = load_json(archive.OUTPUT / row["artifact"])
        ref = references[scenario["reference_schedule_identifier"]]["config"]
        config = dict(dynamicity=scenario["target_DoD"], scenario_seed=scenario["scenario_seed"],
                      reference_solver_multistarts=ref["multistarts"],
                      reference_improvement_passes=ref["improvement_passes"],
                      reference_seed=ref["seed"], reference_label_limit=ref["label_limit"])
        _, reference, prepared, _ = experiments.prepare(row["instance"], config)
        assert prepared.identifier == row["identifier"]
        assert reference.identifier == scenario["reference_schedule_identifier"]
