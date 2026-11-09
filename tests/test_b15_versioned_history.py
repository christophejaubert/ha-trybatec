"""b15 V1/V2/V3 ledger: Recorder and Energy proofs are separate gates."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from custom_components.trybatec.history_versions_b15 import (
    prepare_version, transition_version, version_summary,
)

LOGICAL = "trybatec:logical_ef_synthetic"
FINGERPRINT_A = "a" * 64
FINGERPRINT_B = "b" * 64


def rows(final=1):
    origin = datetime(2022, 1, 1, tzinfo=timezone.utc)
    return [
        {"start": origin, "sum": 0.0, "state": 0.0},
        {"start": origin + timedelta(days=1), "sum": final, "state": final},
    ]


def prepare(ledger=None, final=1, fingerprint=FINGERPRINT_A, approve=False):
    return prepare_version(
        ledger, LOGICAL, rows(final), source_fingerprint=fingerprint,
        unit="m³", approve_revision=approve,
    )


def test_initial_version_is_prepared_not_automatically_active():
    ledger, result = prepare()
    assert result["version"]["statistic_id"] == LOGICAL + "_v1"
    assert result["version"]["state"] == "prepared"
    assert version_summary(ledger, LOGICAL)["active"] is None


def test_persistence_and_energy_are_independent_explicit_gates():
    ledger, _ = prepare()
    with pytest.raises(ValueError, match="Invalid history version transition"):
        transition_version(ledger, LOGICAL, 1, expected_state="prepared",
                           new_state="active", energy_verified=True)
    imported = transition_version(ledger, LOGICAL, 1, expected_state="prepared", new_state="imported")
    with pytest.raises(ValueError, match="Recorder persistence"):
        transition_version(imported, LOGICAL, 1, expected_state="imported", new_state="verified")
    verified = transition_version(imported, LOGICAL, 1, expected_state="imported",
                                  new_state="verified", recorder_verified=True)
    with pytest.raises(ValueError, match="Energy preference"):
        transition_version(verified, LOGICAL, 1, expected_state="verified", new_state="active")
    active = transition_version(verified, LOGICAL, 1, expected_state="verified",
                                new_state="active", energy_verified=True)
    assert version_summary(active, LOGICAL)["active"] == LOGICAL + "_v1"
    assert ledger["series"][LOGICAL]["versions"][0]["state"] == "prepared"


def test_changed_data_cannot_override_v1_without_approval():
    ledger, _ = prepare()
    with pytest.raises(ValueError, match="Explicit revision approval"):
        prepare(ledger, final=2)
    next_ledger, outcome = prepare(ledger, final=2, fingerprint=FINGERPRINT_B, approve=True)
    assert outcome["version"]["number"] == 2
    assert next_ledger["series"][LOGICAL]["versions"][0]["state"] == "prepared"


def test_identical_repeated_plan_is_idempotent():
    ledger, _ = prepare()
    second, result = prepare(ledger)
    assert result["status"] == "unchanged"
    assert len(second["series"][LOGICAL]["versions"]) == 1


def test_pending_import_blocks_different_revision():
    ledger, _ = prepare()
    with pytest.raises(ValueError, match="Pending"):
        prepare(ledger, final=20, fingerprint=FINGERPRINT_B, approve=True)


def test_v2_activation_archives_v1_and_rollback_requires_guarded_verification():
    ledger, _ = prepare()
    ledger = transition_version(ledger, LOGICAL, 1, expected_state="prepared", new_state="imported")
    ledger = transition_version(ledger, LOGICAL, 1, expected_state="imported", new_state="verified", recorder_verified=True)
    ledger = transition_version(ledger, LOGICAL, 1, expected_state="verified", new_state="active", energy_verified=True)
    revised, _ = prepare(ledger, final=2, fingerprint=FINGERPRINT_B, approve=True)
    assert version_summary(revised, LOGICAL)["active"] == LOGICAL + "_v1"
    revised = transition_version(revised, LOGICAL, 2, expected_state="prepared", new_state="imported")
    revised = transition_version(revised, LOGICAL, 2, expected_state="imported", new_state="verified", recorder_verified=True)
    revised = transition_version(revised, LOGICAL, 2, expected_state="verified", new_state="active", energy_verified=True)
    summary = version_summary(revised, LOGICAL)
    assert summary["active"] == LOGICAL + "_v2"
    assert [row["state"] for row in summary["versions"]] == ["archived", "active"]
    with pytest.raises(ValueError, match="explicit approval"):
        transition_version(revised, LOGICAL, 1, expected_state="archived",
                           new_state="active", energy_verified=True)
    rolled_back = transition_version(revised, LOGICAL, 1, expected_state="archived",
                                     new_state="active", energy_verified=True,
                                     rollback_confirmed=True)
    assert version_summary(rolled_back, LOGICAL)["active"] == LOGICAL + "_v1"
    assert [row["state"] for row in version_summary(rolled_back, LOGICAL)["versions"]] == ["active", "archived"]


def test_units_and_fingerprints_must_be_verified():
    with pytest.raises(ValueError, match="raw-source"):
        prepare_version(None, LOGICAL, rows(), source_fingerprint="partial", unit="m³")
    with pytest.raises(ValueError, match="unit"):
        prepare_version(None, LOGICAL, rows(), source_fingerprint=FINGERPRINT_A, unit="unknown")
    ledger, _ = prepare()
    copy = deepcopy(ledger)
    with pytest.raises(ValueError, match="Existing series unit"):
        prepare_version(ledger, LOGICAL, rows(2), source_fingerprint=FINGERPRINT_B,
                        unit="kWh", approve_revision=True)
    assert ledger == copy


def test_corrupt_double_active_or_wrong_version_numbers_fail_closed():
    ledger, _ = prepare()
    ledger["series"][LOGICAL]["versions"][0]["number"] = 9
    with pytest.raises(ValueError, match="Invalid historical version"):
        version_summary(ledger, LOGICAL)


def test_invalid_or_decreasing_statistic_rows_refused():
    bad_rows = rows()
    bad_rows[1]["sum"] = -1
    with pytest.raises(ValueError, match="nondecreasing"):
        prepare_version(None, LOGICAL, bad_rows,
                        source_fingerprint=FINGERPRINT_A, unit="m³")
