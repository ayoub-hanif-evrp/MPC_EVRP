"""Small, simulation-free checks on selection, provenance, pairing, and admission."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from evrp.experiments import load_config
from evrp.instance import Instance
from evrp.reference import ReferenceConfig, ReferenceSchedule, evaluate_route
from evrp.scenario import DynamicScenario
from evrp.storage import ROOT
from scripts.experiments import design_balanced_benchmark as design
from tests.test_repair import customer, setup


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def panel():
    variants = [dict(name=f"{prefix}{digit:02d}_21_{size}", reference_valid=True,
                     dod_eligible=True, path="fixture", sha256="fixture")
                for prefix in ("c1", "c2", "r1", "r2", "rc1", "rc2")
                for digit in (1, 2, 3) for size in design.SIZES]
    grouped = design.groups(variants)
    exposure = dict(parents={p: dict(status="no_outcome_evidence_found") for p in grouped}, errors=[])
    return grouped, exposure


def samples():
    return [dict(size=size, method=method, wall_seconds=100 if method == "MPC_ALNS" else 200,
                 cpu_seconds=80 if method == "MPC_ALNS" else 160, bytes=1000)
            for size in design.SIZES for method in design.METHODS]


@pytest.mark.parametrize("name,expected", [
    ("c105_21_25", ("c105", "C1", 25)),
    ("r210_21_50", ("r210", "R2", 50)),
    ("rc108_21_100", ("rc108", "RC1", 100)),
])
def test_parent_and_family_grouping(name, expected):
    assert design.identity(name) == expected


def test_parent_count_sizes_and_no_outcome_selection():
    grouped, exposure = panel()
    selected, eligible = design.select(grouped, exposure)
    assert len(selected) == len(set(selected)) == 18
    assert sum(len(v["variants"]) for v in grouped.values()) == 54
    assert all(len(values) == 3 for values in eligible.values())
    for row in grouped.values():
        for variant in row["variants"].values():
            variant["irrelevant_served_outcome"] = -999
    assert design.select(grouped, exposure)[0] == selected
    exposure["parents"]["c101"]["status"] = "exposed"
    assert design.select(grouped, exposure)[0] == []
    exposure["parents"]["c101"]["status"] = "no_outcome_evidence_found"
    del grouped["c101"]["variants"]["50"]
    assert design.select(grouped, exposure)[0] == []
    with pytest.raises(ValueError, match="Duplicate"):
        design.groups([dict(name="c105_21_25"), dict(name="c105_21_25")])


def test_exposure_distinguishes_raw_outcomes_plans_references_and_archives(tmp_path, monkeypatch):
    data = {
        "results/desaulniers/reference_validation/inventory.json": {"instances": ["c101_21_25"]},
        "results/desaulniers/development_campaign/manifest.json": {
            "records": [dict(instance="c102_21_25", raw="saved", customers_served=1)]},
        "results/desaulniers/reliability_v2/development/protocol.json": {
            "cases": ["c103_21_25"], "historical_exposed_parents": ["c104_21"]},
        "results/desaulniers/local/raw/hashed.json": {
            "metadata": dict(base_instance="c105_21_100", algorithm="MPC_HGS"),
            "metrics": dict(customers_served=99)},
        "results/research_v2/slad_feasibility_v2/validation/report.json": {"root": "c106_21_100"},
        "docs/review.md": {"mention": "c108_21_50"},
    }
    for rel, content in data.items():
        write(tmp_path / rel, content)
    monkeypatch.setattr(design, "evidence_paths", lambda root: (sorted(data), set(data) - {
        "results/desaulniers/local/raw/hashed.json"}, []))
    monkeypatch.setattr(design, "historical_paths", lambda root: [
        "results/desaulniers/old/raw/c107_21_50_MPC_ALNS.json.gz"])
    rows, _ = design.scan_exposure(tmp_path, [f"c10{i}" for i in range(1, 9)])
    assert not rows["errors"]
    states = {p: row["status"] for p, row in rows["parents"].items()}
    assert states["c101"] == states["c103"] == "no_outcome_evidence_found"
    assert all(states[p] == "exposed" for p in ("c102", "c104", "c105", "c106", "c107"))
    assert states["c108"] == "uncertain"
    assert any(not row["tracked"] for row in rows["sources"])


def test_original_pair_configs_and_common_scenarios(monkeypatch):
    def forbid_save(*args, **kwargs):
        raise AssertionError("Preview must not save a reference or scenario")
    monkeypatch.setattr(ReferenceSchedule, "save", forbid_save)
    monkeypatch.setattr(DynamicScenario, "save", forbid_save)
    configs = design.paired_configs(load_config(ROOT / "configs/paper_controller.yaml"))
    assert tuple(configs) == ("MPC_ALNS", "MPC_HGS")
    left, right = (configs[m] for m in design.METHODS)
    assert {k for k in left if left[k] != right[k]} == {"algorithm"}
    assert left["total_planning_time_limit"] == 5
    assert all(left[key] == "original" for key in design.POLICIES)
    assert left["mpc"]["route_decoder_version"] == "original"
    assert left["mpc"]["charging_mode"] == "partial"
    # Four-customer physical fixture; the labels exercise three size slots without optimization.
    _, obs, _ = setup([customer(chr(65 + i), i + 1, ready=20, service=1) for i in range(4)])
    instance = Instance("toy", "toy", obs.infrastructure, obs.customers)
    trace = evaluate_route(instance, tuple(c.id for c in instance.customers))
    assert trace is not None
    reference = ReferenceSchedule(instance.name, instance.sha256, ReferenceConfig(), (trace,))
    grouped, _ = panel()
    valid = {v["name"]: (instance, reference) for p in grouped.values() for v in p["variants"].values()}
    cases, jobs = design.planned_jobs(sorted(grouped), grouped, valid, configs)
    assert len(cases) == 54 and len(jobs) == 108
    assert len({job["id"] for job in jobs}) == 108
    for index, case in enumerate(cases):
        block = [job for job in jobs if job["paired_block"] == index]
        assert {job["method"] for job in block} == set(design.METHODS)
        assert {job["scenario_identifier"] for job in block} == {case["scenario_identifier"]}
        assert {job["k_ref"] for job in block} == {reference.fleet_size}
        assert case["scenario"]["scenario_seed"] == 7301
    with pytest.raises(ValueError, match="Duplicate"):
        design.planned_jobs(["c101", "c101"], grouped, valid, configs)


def test_conservative_budget_admission_and_refusal():
    result = design.cost_estimate(samples())
    assert result["admitted"]
    assert result["strata"][0]["worker_cap_seconds"] == 260
    assert result["strata"][1]["worker_cap_seconds"] == 460
    assert result["predicted_worker_wall_seconds"]["MPC_ALNS"] == 18 * 3 * 260
    assert not design.cost_estimate(samples(), wall_hours=1)["admitted"]
    assert not design.cost_estimate(samples(), cpu_hours=1)["admitted"]
    assert not design.cost_estimate(samples(), storage_gib=.0001)["admitted"]
    expensive = samples()
    expensive[0]["wall_seconds"] = 1000
    assert design.cost_estimate(expensive)["strata"][0]["worker_cap_seconds"] == 2060
    missing = samples()
    missing[0]["cpu_seconds"] = None
    assert not design.cost_estimate(missing)["admitted"]
    with pytest.raises(ValueError, match="finite"):
        design.cost_estimate(samples(), wall_hours=float("inf"))


@pytest.mark.parametrize("corrupt", [False, True])
def test_missing_or_invalid_references_fail_eligibility(tmp_path, monkeypatch, corrupt):
    grouped = design.groups([dict(name="c105_21_25", path="fixture")])
    instance = SimpleNamespace(name="c105_21_25", sha256="fixture")
    row = dict(instance=instance.name, physical_witness=True, instance_sha256=instance.sha256,
               artifact="results/reference_schedules/missing.json", artifact_sha256="wrong")
    if corrupt:
        write(tmp_path / row["artifact"], {"corrupt": True})
    write(tmp_path / "results/desaulniers/targeted_service_v1/reference_inventory.json", {"rows": [row]})
    monkeypatch.setattr(design, "load_instance", lambda path: instance)
    assert not design.validate_inputs(tmp_path, grouped)
    variant = grouped["c105"]["variants"]["25"]
    assert not variant["reference_valid"] and variant["exclusion"]


def ready_report():
    grouped, exposure = panel()
    selected, _ = design.select(grouped, exposure)
    return dict(status="READY", budget=design.cost_estimate(samples()),
                selected_parents=selected, independent_parents=18, benchmark_files=54,
                optimizer_jobs=108, methods=list(design.METHODS), cases=[{}] * 54,
                jobs=[dict(id=str(i)) for i in range(108)], source_commit="fixture")


def test_preview_cli_makes_no_writes_and_freeze_fails_closed(tmp_path, monkeypatch, capsys):
    report = dict(status="BLOCKED", budget=dict(admitted=False))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(design, "preview", lambda **kwargs: report)
    before = list(tmp_path.rglob("*"))
    assert design.main([]) == 2
    assert list(tmp_path.rglob("*")) == before
    assert '"BLOCKED"' in capsys.readouterr().out
    with pytest.raises(ValueError, match="BLOCKED"):
        design.freeze(report, tmp_path)
    with pytest.raises(ValueError, match="OVER BUDGET"):
        design.freeze(dict(report, status="OVER BUDGET"), tmp_path)
    for name in ("protocol.json", "../exposure_inventory.json"):
        with pytest.raises(ValueError, match="Inventory name"):
            design.main(["--write-inventory", name])
    assert list(tmp_path.rglob("*")) == before


def test_immutable_protocol_verification_and_nonoverwrite(tmp_path, monkeypatch):
    report = ready_report()
    path = design.freeze(report, tmp_path)
    saved = path.read_bytes()
    monkeypatch.setattr(design, "preview", lambda *args: dict(report))
    assert design.verify(path, tmp_path) == design.identifier(report)
    drifted = deepcopy(report)
    drifted["source_commit"] = "newer-harmless-commit"
    monkeypatch.setattr(design, "preview", lambda *args: dict(drifted))
    assert design.verify(path, tmp_path) == design.identifier(report)
    drifted["jobs"][0]["id"] = "changed-input"
    with pytest.raises(ValueError, match="drift"):
        design.verify(path, tmp_path)
    assert path.read_bytes() == saved
    with pytest.raises(FileExistsError):
        design.freeze(ready_report(), tmp_path)
    altered = deepcopy(design.read_json(path))
    altered["protocol"]["status"] = "BLOCKED"
    tampered = write(tmp_path / "tampered.json", altered)
    with pytest.raises(ValueError, match="Invalid"):
        design.verify(tampered, tmp_path)
    duplicate = ready_report()
    duplicate["selected_parents"][0] = duplicate["selected_parents"][1]
    with pytest.raises(ValueError, match="parent"):
        design.freeze(duplicate, tmp_path / "other")


def test_verification_ignores_only_operational_inventory_metadata(tmp_path, monkeypatch):
    report = ready_report()
    report["exposure"] = dict(searched_files=10, excluded_scratch_or_vendor_directories=["scratch-old"],
                              sources=[dict(path="raw.json", sha256="hash", tracked=False)])
    path = design.freeze(report, tmp_path)
    current = deepcopy(report)
    current["exposure"]["searched_files"] = 11
    current["exposure"]["excluded_scratch_or_vendor_directories"] = ["scratch-new"]
    current["exposure"]["sources"][0]["tracked"] = True
    monkeypatch.setattr(design, "preview", lambda *args: deepcopy(current))
    assert design.verify(path, tmp_path) == design.identifier(report)
    current["exposure"]["sources"][0]["sha256"] = "changed-raw"
    with pytest.raises(ValueError, match="drift"):
        design.verify(path, tmp_path)
