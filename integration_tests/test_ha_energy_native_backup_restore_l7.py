"""#88 native Home Assistant backup/restore drill on disposable CI-only paths.

Uses the real 2026.11.0 BackupManager, local tar agent, SecureTar archive,
and Home Assistant startup restoration function. The restore target is always
a DIFFERENT pytest tmp_path; production Home Assistant is never accessed.
The L7 activation gate remains disabled.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from homeassistant.backup_restore import (
    RESTORE_BACKUP_FILE, RESTORE_BACKUP_RESULT_FILE, restore_backup,
)
from homeassistant.components.backup import async_get_manager
from homeassistant.setup import async_setup_component

from custom_components.trybatec.energy_bulk_native_port_l7 import HAGuardedEnergyPort


@pytest.fixture
def hass_storage():
    """Allow actual .storage files inside the isolated CI config directory."""
    return {}


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir):
    """Isolated HA fixture, not the user's configuration directory."""
    return hass_tmp_config_dir


@pytest.mark.asyncio
async def test_native_ha_backup_archive_restores_energy_and_database_to_disposable_dir(
    hass, tmp_path: Path,
):
    """Real native archive creation, catalog verification, and offline restore.

    Invokes the actual HA startup restore function with a separate scratch
    directory. Does not call Home Assistant restart or mutate the source HA.
    """
    assert await async_setup_component(hass, "backup", {})
    await hass.async_block_till_done()

    source_config = Path(hass.config.path())
    assert source_config.resolve() == tmp_path.resolve()  # pytest isolates HA here
    manager = async_get_manager(hass)
    assert manager.local_backup_agents

    # All test material is artificial and under pytest's disposable config.
    unique_text = "Trybatec CI synthetic restoration evidence 2026.11"
    marker = source_config / "ci_trybatec_restore_marker.txt"
    marker.write_text(unique_text, encoding="utf-8")
    database = source_config / "home-assistant_v2.db"
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE ci_trybatec_test (marker TEXT NOT NULL)")
        connection.execute("INSERT INTO ci_trybatec_test VALUES (?)", (unique_text,))
        connection.commit()
    finally:
        connection.close()

    from homeassistant.components.energy.data import async_get_manager as energy_manager
    energy = await energy_manager(hass)
    hass.data["energy_manager"] = energy
    preferences = energy.default_preferences()
    await energy.async_update({"energy_sources": []})
    await energy._store.async_save(preferences)

    port = HAGuardedEnergyPort(
        hass,
        SimpleNamespace(entry=SimpleNamespace(
            entry_id="ci-native-backup-only", unique_id="ci-isolated-account",
        )),
        lot="CI-LOT",
    )
    before_energy = await port.read_persisted()
    receipt = await port.create_backup()
    assert await port.verify_backup(receipt) is True

    backup_path = manager.local_backup_agents[receipt["agent_id"]].get_backup_path(
        receipt["backup_id"]
    )
    assert backup_path.is_file() and backup_path.stat().st_size > 0

    # Deliberately change the source AFTER backup: restoration must recover
    # the snapshot, not silently use the modified live source.
    marker.write_text("changed after backup", encoding="utf-8")

    # A sibling scratch directory prevents restoration from touching or
    # accidentally being archived within the source Home Assistant config.
    restore_dir = tmp_path.parent / (tmp_path.name + "_restored_disposable")
    restore_dir.mkdir()
    assert restore_dir.resolve() != source_config.resolve()
    assert restore_dir not in source_config.parents
    assert source_config not in restore_dir.parents
    (restore_dir / RESTORE_BACKUP_FILE).write_text(json.dumps({
        "path": backup_path.as_posix(),
        "password": None,
        "remove_after_restore": False,
        "restore_database": True,
        "restore_homeassistant": True,
    }), encoding="utf-8")

    assert await hass.async_add_executor_job(
        restore_backup, restore_dir.as_posix()
    ) is True
    result = json.loads(
        (restore_dir / RESTORE_BACKUP_RESULT_FILE).read_text(encoding="utf-8")
    )
    assert result == {"success": True, "error": None, "error_type": None}
    assert (restore_dir / marker.name).read_text(encoding="utf-8") == unique_text
    with sqlite3.connect(restore_dir / database.name) as restored_db:
        assert restored_db.execute(
            "SELECT marker FROM ci_trybatec_test"
        ).fetchone() == (unique_text,)

    # Compare only synthetic Energy data, not any user-specific HA information.
    energy_doc = json.loads(
        (restore_dir / ".storage" / "energy").read_text(encoding="utf-8")
    )
    assert energy_doc["key"] == "energy"
    assert energy_doc["minor_version"] == 3
    assert energy_doc["data"] == before_energy
    assert marker.read_text(encoding="utf-8") == "changed after backup"
