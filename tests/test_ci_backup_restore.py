"""Synthetic-only backup/restore regressions; no production HA, credentials or network."""
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/ci_backup_restore.py"
SPEC = spec_from_file_location("synthetic_ci_backup_restore", SCRIPT)
assert SPEC and SPEC.loader
BACKUP = module_from_spec(SPEC)
SPEC.loader.exec_module(BACKUP)


@pytest.fixture
def ci_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    home = tmp_path / "ha-decision-candidate-self"
    (home / ".storage").mkdir(parents=True)
    store = home / ".storage" / BACKUP.KEY
    record = {
        "version": 1,
        "data": {"decisions": {"a" * 32: {
            "action": "correct",
            "reason": "Synthetic year-end accounting reassignment for restart verification",
        }}},
    }
    store.write_text(json.dumps(record), encoding="utf-8")
    return home, tmp_path / "ha-backup-candidate-self", tmp_path / "ha-restored-candidate-self"


def test_verified_physical_snapshot_restores_identical_bytes(ci_paths):
    original, archive, restored = ci_paths
    BACKUP.snapshot(original, archive)
    BACKUP.restore(archive, restored)
    assert (restored / ".storage" / BACKUP.KEY).read_bytes() == (
        original / ".storage" / BACKUP.KEY
    ).read_bytes()
    with pytest.raises(ValueError, match="already used"):
        BACKUP.restore(archive, restored)


def test_tampered_payload_is_rejected_before_restore_writes(ci_paths):
    original, archive, restored = ci_paths
    BACKUP.snapshot(original, archive)
    (archive / BACKUP.PAYLOAD_NAME).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        BACKUP.restore(archive, restored)
    assert not restored.exists()


def test_foreign_manifest_key_is_rejected_before_restore(ci_paths):
    original, archive, restored = ci_paths
    BACKUP.snapshot(original, archive)
    manifest = archive / BACKUP.MANIFEST_NAME
    record = json.loads(manifest.read_text(encoding="utf-8"))
    record["key"] = "../../not-allowed"
    manifest.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="foreign"):
        BACKUP.restore(archive, restored)
    assert not restored.exists()


def test_missing_or_invalid_synthetic_source_is_not_backed_up(ci_paths):
    original, archive, _ = ci_paths
    (original / ".storage" / BACKUP.KEY).unlink()
    with pytest.raises(ValueError, match="Missing"):
        BACKUP.snapshot(original, archive)
    assert not archive.exists()


def test_real_or_outside_ci_paths_are_never_accepted(ci_paths, monkeypatch, tmp_path):
    original, archive, _ = ci_paths
    with pytest.raises(ValueError, match="name"):
        BACKUP.snapshot(tmp_path / "actual-homeassistant", archive)
    monkeypatch.delenv("GITHUB_ACTIONS")
    with pytest.raises(ValueError, match="only in GitHub Actions"):
        BACKUP.snapshot(original, archive)
    assert not archive.exists()


def test_malformed_or_oversized_source_fails_closed(ci_paths):
    original, archive, _ = ci_paths
    file = original / ".storage" / BACKUP.KEY
    file.write_text('{"version": 999}', encoding="utf-8")
    with pytest.raises(ValueError, match="envelope"):
        BACKUP.snapshot(original, archive)
    file.write_bytes(b"x" * (BACKUP.MAX_STORAGE_BYTES + 1))
    with pytest.raises(ValueError, match="safe size"):
        BACKUP.snapshot(original, archive)


def test_snapshot_refuses_symlink_source(ci_paths, tmp_path):
    original, archive, _ = ci_paths
    store = original / ".storage" / BACKUP.KEY
    backup = tmp_path / "synthetic-original.json"
    store.rename(backup)
    store.symlink_to(backup)
    with pytest.raises(ValueError, match="linked"):
        BACKUP.snapshot(original, archive)
