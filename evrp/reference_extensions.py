"""Explicit access to separately audited MP witnesses for new scenario policies."""

from .reference import ReferenceConfig, ReferenceFailure, ReferenceSchedule, published_full_reference
from .storage import ROOT, load_json, verify_text_digest


INVENTORY = ROOT / "results/desaulniers/publication_development/audits/reference_inventory.json"


def load_mp_witness(instance):
    if not INVENTORY.is_file():
        raise ReferenceFailure("Build and audit the separate MP reference inventory first")
    inventory = load_json(INVENTORY)
    row = next((r for r in inventory["rows"] if r["instance"] == instance.name), None)
    if row is None or not row["physical_witness"] or row["instance_sha256"] != instance.sha256:
        raise ReferenceFailure("No audited MP witness for this instance and input SHA-256")
    if row.get("artifact"):
        path = (ROOT / row["artifact"]).resolve()
        if not path.is_relative_to((ROOT / "results").resolve()):
            raise ReferenceFailure("MP reference artifact escapes repository results")
        verify_text_digest(path, row["artifact_sha256"])
        reference = ReferenceSchedule.load(path, instance)
    else:
        reference = published_full_reference(instance, ReferenceConfig())
    if reference is None or reference.identifier != row["reference_id"]:
        raise ReferenceFailure("MP witness canonical content differs from the audited inventory")
    return reference
