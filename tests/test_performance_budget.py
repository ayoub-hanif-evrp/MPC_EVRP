import json
import sys

import pytest

from scripts import performance_budget as accounting


@pytest.fixture
def local_storage(monkeypatch,tmp_path):
    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data),encoding="utf-8")
    def writable(path):
        path.parent.mkdir(parents=True,exist_ok=True)
        return path
    monkeypatch.setattr(accounting,"save_json",write)
    monkeypatch.setattr(accounting,"writable_path",writable)
    monkeypatch.setattr(accounting,"ROOT",tmp_path)


def test_admission_reserves_complete_pair_and_reporting():
    assert not accounting.admit(300,200,180)
    assert accounting.admit(400,200,180)
    assert not accounting.admit(400,0,180)


def test_frozen_budget_cannot_be_extended(tmp_path, local_storage):
    budget=accounting.HardBudget(tmp_path,10)
    budget.flush()
    with pytest.raises(ValueError,match="extend"):
        accounting.HardBudget(tmp_path,20)


def test_oversized_job_never_spawns(tmp_path,local_storage,monkeypatch):
    budget=accounting.HardBudget(tmp_path,10)
    def prohibited(*args,**kwargs):
        raise AssertionError("Oversized admission spawned a child")
    monkeypatch.setattr(accounting.subprocess,"Popen",prohibited)
    assert budget.execute("oversized",[sys.executable,"-c","pass"],20,reserve=0) is None
    assert not budget.data["jobs"]


def test_hard_watchdog_preserves_incomplete_and_forbids_silent_retry(tmp_path,local_storage):
    budget=accounting.HardBudget(tmp_path,10)
    record=budget.execute("watchdog",[sys.executable,"-c","import time; time.sleep(3)"],.15,reserve=0)
    assert record["status"]=="incomplete"
    assert record["elapsed_seconds"]<2
    assert record["returncode"]!=0
    with pytest.raises(ValueError,match="retry"):
        budget.execute("watchdog",[sys.executable,"-c","pass"],1,reserve=0)


def test_complete_job_is_reused_without_reexecution(tmp_path,local_storage,monkeypatch):
    budget=accounting.HardBudget(tmp_path,10)
    record=budget.execute("once",[sys.executable,"-c","print('done')"],1,reserve=0)
    assert record["status"]=="complete"
    def prohibited(*args,**kwargs):
        raise AssertionError("Completed worker reran")
    monkeypatch.setattr(accounting.subprocess,"Popen",prohibited)
    assert budget.execute("once",["unreachable"],1,reserve=0)==record
