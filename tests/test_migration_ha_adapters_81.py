"""Use HA-native backup metadata, not a checkbox, to guard migration #81."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from custom_components.trybatec.migration_ha_adapters_81 import (
    lookup_verified_backup, MAX_BACKUP_AGE,
)

NOW = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)


def _backup(**changes):
    record = dict(
        backup_id="synthetic-backup",
        date=(NOW - timedelta(minutes=15)).isoformat(),
        homeassistant_included=True,
        database_included=True,
        failed_agent_ids=[],
        failed_folders=[],
        failed_addons=[],
        agents={"hassio.local": SimpleNamespace(size=100_000, protected=True)},
    )
    record.update(changes)
    return SimpleNamespace(**record)


class Manager:
    def __init__(self, backup, *, errors=None):
        self.backup = backup
        self.errors = errors or {}
        self.reads = 0

    async def async_get_backup(self, backup_id):
        self.reads += 1
        return self.backup, self.errors


def _check(backup=None, *, errors=None):
    manager = Manager(_backup() if backup is None else backup, errors=errors)
    result = asyncio.run(
        lookup_verified_backup(manager, "synthetic-backup", now=NOW)
    )
    assert manager.reads == 1
    return result


def test_real_manager_backup_metadata_is_read_only_and_complete():
    record = _check()
    assert record["backup_id"] == "synthetic-backup"
    assert record["homeassistant_included"] is True
    assert record["database_included"] is True
    assert record["agents"]["hassio.local"]["size"] == 100_000
    assert record["date"]


@pytest.mark.parametrize("override", [
    {"date": (NOW - MAX_BACKUP_AGE - timedelta(seconds=1)).isoformat()},
    {"date": (NOW + timedelta(seconds=1)).isoformat()},
    {"date": "2026-11-12T10:00:00"},
    {"date": "invalid"},
    {"date": None},
    {"homeassistant_included": False},
    {"database_included": False},
    {"failed_agent_ids": ["remote.failed"]},
    {"failed_folders": ["ssl"]},
    {"failed_addons": ["music"]},
    {"failed_addons": None},
    {"agents": {}},
    {"agents": {"hassio.local": SimpleNamespace(size=0, protected=True)}},
    {"agents": {"hassio.local": SimpleNamespace(size=-2, protected=True)}},
    {"backup_id": "other-backup"},
])
def test_stale_incomplete_or_wrong_backup_is_rejected(override):
    with pytest.raises(ValueError):
        _check(_backup(**override))


def test_ha_backup_listing_errors_fail_closed():
    with pytest.raises(ValueError, match="agent errors"):
        _check(errors={"hassio.local": RuntimeError("disconnected")})


def test_missing_backup_is_rejected():
    with pytest.raises(ValueError, match="not available"):
        _check(backup=object() if False else SimpleNamespace(
            backup_id="other", date=NOW.isoformat(), agents={},
        ))


def test_manager_returning_no_backup_is_rejected():
    async def scenario():
        with pytest.raises(ValueError, match="not available"):
            await lookup_verified_backup(Manager(None), "synthetic-backup", now=NOW)
    asyncio.run(scenario())


@pytest.mark.parametrize("reference", ["", " " * 200, None, 42])
def test_invalid_backup_ids_are_never_sent_to_manager(reference):
    async def scenario():
        manager = Manager(_backup())
        with pytest.raises(ValueError, match="Invalid backup reference"):
            await lookup_verified_backup(manager, reference, now=NOW)
        assert manager.reads == 0
    asyncio.run(scenario())
