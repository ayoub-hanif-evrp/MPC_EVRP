"""Publication closure must reject incomplete validation and altered evidence bytes."""

import pytest

from scripts import audit_final_cpu_completion as completion


def test_junit_failure_cannot_be_reported_as_complete(tmp_path):
    path = tmp_path / "validation.xml"
    path.write_text('<testsuites><testsuite tests="403" failures="1" errors="0" skipped="0" /></testsuites>')
    with pytest.raises(ValueError, match="did not pass"):
        completion.read_tests(path)
    path.write_text('<testsuites><testsuite tests="403" failures="0" errors="0" skipped="1" /></testsuites>')
    result = completion.read_tests(path)
    assert (result["tests"], result["skipped"], result["failures"]) == (403, 1, 0)


def test_git_transport_does_not_tolerate_newlines_that_change_frozen_hash(tmp_path, monkeypatch):
    path = tmp_path / "evidence.json"
    path.write_bytes(b'{"frozen": true}\r\n')
    monkeypatch.setattr(completion, "ROOT", tmp_path)
    monkeypatch.setattr(completion, "git", lambda *args: b"evidence.json\0" if args[0] == "ls-files"
                        else b'{"frozen": true}\n')
    with pytest.raises(ValueError, match="executed evidence bytes"):
        completion.transport_check("index")
    monkeypatch.setattr(completion, "git", lambda *args: b"evidence.json\0" if args[0] == "ls-files"
                        else path.read_bytes())
    assert completion.transport_check("index")["all_exact"]


def test_document_audit_rejects_broken_reproduction_links(tmp_path):
    path = tmp_path / "README.md"
    path.write_text("[Missing results](missing.json)\n")
    with pytest.raises(ValueError, match="Broken local link"):
        completion.local_links([path])
