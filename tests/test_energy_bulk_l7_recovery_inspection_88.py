"""Pure synthetic L7 native-recovery inspector, no HA writes."""
import asyncio
from copy import deepcopy

import pytest

from custom_components.trybatec.energy_bulk_l7_recovery_inspection_88 import (
    async_inspect_l7_recovery_88,
)
from custom_components.trybatec.energy_switch import preferences_fingerprint

BEFORE = {
    "energy_sources": [{
        "type": "grid", "stat_energy_from": "sensor.synthetic_grid",
    }],
    "device_consumption": [{
        "stat_consumption": "sensor.synthetic_other",
    }],
    "device_consumption_water": [],
}
AFTER = deepcopy(BEFORE)
AFTER["energy_sources"].append({
    "type": "water", "stat_energy_from": "trybatec:synthetic_ef_v1",
})
FOREIGN = deepcopy(AFTER)
FOREIGN["device_consumption"].append({
    "stat_consumption": "sensor.synthetic_foreign_later",
})


class Fake:
    def __init__(self, *, live=None, disk=None, state="prepared"):
        self.live = deepcopy(BEFORE if live is None else live)
        self.disk = deepcopy(BEFORE if disk is None else disk)
        self.journal = {
            "status": state, "snapshot": deepcopy(BEFORE),
            "proposed": deepcopy(AFTER),
            "before": preferences_fingerprint(BEFORE),
            "after": preferences_fingerprint(AFTER),
            "backup": {"fake": "private"},
        }
        self.calls = []

    async def assert_admin(self, actor):
        self.calls.append("admin")
        if actor != "synthetic-admin":
            raise PermissionError("Native administrator required")

    async def read_last_journal(self):
        self.calls.append("journal")
        return deepcopy(self.journal)

    async def read_live(self):
        self.calls.append("live")
        return deepcopy(self.live)

    async def read_persisted(self):
        self.calls.append("disk")
        return deepcopy(self.disk)


def inspect(port, actor="synthetic-admin"):
    return asyncio.run(async_inspect_l7_recovery_88(port, actor))


@pytest.mark.parametrize("live,disk,expected", [
    (BEFORE, BEFORE, "prepared_no_write_observed"),
    (AFTER, AFTER, "prepared_applied_without_terminal_audit"),
    (AFTER, BEFORE, "prepared_in_memory_only"),
    (BEFORE, AFTER, "prepared_disk_only"),
    (FOREIGN, AFTER, "prepared_external_or_partial_divergence"),
    (FOREIGN, FOREIGN, "prepared_external_or_partial_divergence"),
])
def test_recovery_states_preserve_all_foreign_data(live, disk, expected):
    port = Fake(live=live, disk=disk)
    prior_live, prior_disk, prior_journal = (
        deepcopy(port.live), deepcopy(port.disk), deepcopy(port.journal),
    )
    result = inspect(port)
    assert result["status"] == expected
    assert result["requires_administrator_review"] is True
    assert result["automatic_retry_allowed"] is False
    assert result["automatic_rollback_allowed"] is False
    assert result["writes"] is False
    assert port.live == prior_live and port.disk == prior_disk
    assert port.journal == prior_journal
    assert port.calls == ["admin", "journal", "live", "disk"]
    assert "private" not in str(result)


@pytest.mark.parametrize("status,live,disk,expected", [
    ("verified", AFTER, AFTER, "terminal_journal_consistent"),
    ("verified", BEFORE, BEFORE, "terminal_journal_diverged"),
    ("rolled_back_verified", BEFORE, BEFORE, "terminal_journal_consistent"),
    ("no_write_observed", BEFORE, BEFORE, "terminal_journal_consistent"),
    ("rolled_back_verified", AFTER, AFTER, "terminal_journal_diverged"),
])
def test_terminal_journal_must_match_native_memory_and_disk(
    status, live, disk, expected,
):
    result = inspect(Fake(live=live, disk=disk, state=status))
    assert result["status"] == expected
    assert result["requires_administrator_review"] == (
        expected != "terminal_journal_consistent"
    )
    assert result["writes"] is False


def test_no_prior_journal_safe_idle_no_mutation():
    port = Fake()
    port.journal = None
    data = inspect(port)
    assert data["status"] == "none"
    assert data["requires_administrator_review"] is False
    assert port.calls == ["admin", "journal"]


def test_invalid_or_divergent_journal_requires_manual_review():
    port = Fake()
    port.journal["after"] = "f" * 64
    assert inspect(port)["status"] == "journal_snapshot_or_fingerprint_invalid"
    port = Fake()
    port.journal["status"] = "unexpected"
    assert inspect(port)["status"] == "journal_invalid_or_unknown"


def test_admin_check_happens_before_any_journal_or_private_snapshot_read():
    port = Fake()
    with pytest.raises(PermissionError):
        inspect(port, "outsider")
    assert port.calls == ["admin"]
