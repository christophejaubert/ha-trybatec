"""Synthetic crosschecks only; no user energy readings or HA environment."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from custom_components.trybatec.energy_bulk_contract_l6 import crosscheck_36_37_120


ACCOUNT = "SYNTH-ACCOUNT"
LOT = "SYNTH-LOT"


def _v(logical):
    return {"number": 1, "state": "verified", "statistic_id": f"{logical}_v1",
            "snapshot_hash": "s" * 64, "source_fingerprint": "f" * 64}


def sample():
    physical = "trybatec:logical_meter_ef_raw_synthetic"
    consolidated = "trybatec:logical_dwelling_ef_synthetic"
    archive_key = sha256(json.dumps([LOT, "EF", "OLD"], separators=(",", ":")).encode()).hexdigest()[:48]
    ledger = {"schema": 1, "series": {
        physical: {"scope": {"lot": LOT, "fluid": "EF", "kind": "physical", "serial": "OLD"},
                   "unit": "m³", "versions": [_v(physical)]},
        consolidated: {"scope": {"lot": LOT, "fluid": "EF", "kind": "consolidated", "serial": None},
                       "unit": "m³", "versions": [_v(consolidated)]},
    }}
    retired = {"schema": 1, "meters": {archive_key: {"lot": LOT, "fluid": "EF", "serial": "OLD", "retired": True}}}
    observed = [{"lot": LOT, "fluid": "EF", "serial": "OLD", "retired": True}]
    return ledger, retired, observed


def run(ledger=None, retired=None, observed=None):
    d = sample()
    return crosscheck_36_37_120(ledger=d[0] if ledger is None else ledger,
                                retired=d[1] if retired is None else retired,
                                observed=d[2] if observed is None else observed,
                                account=ACCOUNT, lot=LOT)


def test_registered_retired_meter_still_not_exhaustively_verified():
    r = run()
    ef = r["fluids"]["EF"]
    assert ef["retired_meters"] == 1
    assert ef["consolidated_statistic"].endswith("_v1")
    assert ef["status"] == "insufficient_evidence"
    assert r["complete"] is False and r["activation_authorized"] is False


def test_unknown_inventory_never_empty_certification():
    l, _, _ = sample()
    r = run(l, {"schema": 0}, [])
    assert "retired_inventory_unavailable" in r["fluids"]["EF"]["blockers"]
    assert r["complete"] is False


def test_uncovered_retired_meter_blocks():
    ledger, retired, observed = sample()
    ledger["series"].pop("trybatec:logical_meter_ef_raw_synthetic")
    r = run(ledger, retired, observed)
    assert r["fluids"]["EF"]["status"] == "blocked"
    assert "observed_or_retired_meter_missing_from_b15" in r["fluids"]["EF"]["blockers"]


def test_unobserved_physical_ledger_requires_inventory():
    l, r, o = sample()
    out = run(l, r, [])
    assert out["fluids"]["EF"]["retired_meters"] == 1  # Archived member remains known.
    # This is not proof of all physical meters; no admission.
    assert out["fluids"]["EF"]["status"] != "admissible"


def test_invalid_retired_archive_hash_blocks():
    ledger, archive, observed = sample()
    value = next(iter(archive["meters"].values()))
    archive["meters"] = {"tampered": value}
    r = run(ledger, archive, observed)
    assert r["fluids"]["EF"]["status"] == "blocked"


def test_duplicate_current_serial_blocks_all():
    ledger, archive, observed = sample()
    report = run(ledger, archive, observed + observed)
    assert all(v["status"] == "blocked" for v in report["fluids"].values())


def test_consolidated_bad_unit_blocks():
    ledger, archive, observed = sample()
    ledger["series"]["trybatec:logical_dwelling_ef_synthetic"]["unit"] = "kWh"
    report = run(ledger, archive, observed)
    assert "consolidation_unit_incompatible" in report["fluids"]["EF"]["blockers"]


def test_consolidated_version_pending_not_verified():
    ledger, archive, observed = sample()
    ledger["series"]["trybatec:logical_dwelling_ef_synthetic"]["versions"][0]["state"] = "imported"
    report = run(ledger, archive, observed)
    assert "ambiguous_persisted_version_selection" in report["fluids"]["EF"]["blockers"]


def test_ambiguous_multiple_consolidations():
    ledger, archive, observed = sample()
    name = "trybatec:logical_dwelling_ef_other"
    ledger["series"][name] = {"scope": {"lot": LOT, "fluid": "EF", "kind": "consolidated", "serial": None},
                               "unit": "m³", "versions": [_v(name)]}
    assert "multiple_logical_consolidations" in run(ledger, archive, observed)["fluids"]["EF"]["blockers"]


def test_invalid_version_ledger_blocks():
    ledger, archive, observed = sample()
    ledger["series"]["trybatec:logical_dwelling_ef_synthetic"]["versions"][0]["statistic_id"] = "bad"
    report = run(ledger, archive, observed)
    assert all(v["status"] == "blocked" for v in report["fluids"].values())


def test_original_inputs_unchanged():
    args = sample()
    frozen = deepcopy(args)
    run(*args)
    assert args == frozen


def test_invalid_scope_refused():
    import pytest
    with pytest.raises(ValueError):
        crosscheck_36_37_120(ledger={}, retired={}, observed=[], account="", lot=LOT)
