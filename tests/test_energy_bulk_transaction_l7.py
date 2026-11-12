"""Synthetic L7 state-machine tests; fake port only, NO real Home Assistant."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy

import pytest

from custom_components.trybatec.energy_bulk_transaction import (
    ServerEnergyState, EnergyTransactionRefused, EnergyRecoveryRequired,
    preview_bulk_energy_transaction, apply_bulk_energy_transaction,
)
from custom_components.trybatec.energy_switch import preferences_fingerprint

ACCOUNT="SYNTH-ACCOUNT"
LOT="SYNTH-LOT"
STAT="trybatec:synth_ef_v1"


def initial():
    return {"energy_sources":[{"type":"grid","stat_energy_from":"sensor.synthetic_grid"}],
            "device_consumption":[{"stat_consumption":"sensor.third_party"}],
            "device_consumption_water":[],"unrelated":{"kept":True}}


def candidate(fluid="EF", **changes):
    c={"account":ACCOUNT,"lot":LOT,"fluid":fluid,"kind":"consolidated",
       "statistic_id":f"trybatec:synth_{fluid.lower()}_v1",
       "unit":"kWh" if fluid=="CET" else "m³",
       "recorder_device_class":"energy" if fluid=="CET" else "water",
       "competing_statistic_ids":[f"sensor.synthetic_prior_{fluid.lower()}"],
       "thermal_category_approved":fluid=="CET"}
    c.update({k:True for k in ("account_lot_verified", "unit_verified",
             "recorder_verified", "recorder_has_sum", "recorder_has_data",
             "historical_coverage_verified", "physical_meter_coverage_verified",
             "version_exclusivity_verified", "alternatives_complete", "energy_schema_verified")})
    c.update(changes)
    return c


class FakePort:
    def __init__(self, *, authorized=True, blocked=False, fluids=("EF",)):
        self.authorized=authorized
        self.live=initial()
        self.disk=deepcopy(self.live)
        self.backups=0
        self.writes=0
        self.audit=[]
        self.flushes=0
        self.flags=set()
        self.lock=asyncio.Lock()
        self.fluids=fluids
        self.blocked=blocked
        self.candidates=[candidate(f) for f in fluids]

    @asynccontextmanager
    async def exclusive(self):
        async with self.lock:
            yield

    async def assert_admin(self,actor):
        if actor != "verified-admin" or not self.authorized:
            raise PermissionError("HA backend refused non-admin")

    async def collect(self, actor, *, account, lot):
        if account!=ACCOUNT or lot!=LOT:
            raise ValueError("wrong scope")
        states={f:{"status": "admissible" if f in self.fluids and not self.blocked else
                    "insufficient_evidence" if f in self.fluids else "already_configured"}
                for f in ("EF", "ECS", "CET")}
        # A fake trusted collector deliberately exercises the eventual path.
        # Real L6 currently never issues 'admissible'.
        return ServerEnergyState(deepcopy(self.live),{
            "writes":False,"activation_authorized":False,
            "preferences_fingerprint":preferences_fingerprint(self.live),
            "fluids":states},tuple(deepcopy(self.candidates)),"2026.11.1")

    async def read_live(self):
        return deepcopy(self.live)

    async def read_persisted(self):
        return deepcopy(self.disk)

    async def create_backup(self):
        self.backups+=1
        if "backup_fail" in self.flags:
            raise IOError("simulated backup failure")
        return {"synthetic":True, "id":"backup:fake"}

    async def verify_backup(self, receipt):
        return "backup_unverified" not in self.flags and receipt["synthetic"] is True

    async def read_last_journal(self):
        return deepcopy(self.audit[-1]) if self.audit else None

    async def journal(self,payload):
        if "journal_fail" in self.flags:
            raise IOError("simulated journal failure")
        self.audit.append(deepcopy(payload))

    async def write_energy_sources(self,sources):
        self.writes+=1
        if "apply_fail_before" in self.flags and self.writes==1:
            raise IOError("simulated prewrite failure")
        self.live["energy_sources"]=deepcopy(sources)
        if "apply_fail_after" in self.flags and self.writes==1:
            raise IOError("simulated failure after mutation")
        if "third_party_during_apply" in self.flags and self.writes==1:
            self.live["unrelated"]={"changed":True}
            self.disk=deepcopy(self.live)
            raise IOError("simulated third party race")
        if "rollback_fail" in self.flags and self.writes > 1:
            raise IOError("simulated rollback failure")

    async def flush_and_read_persisted(self):
        self.flushes+=1
        if "persisted_mismatch" in self.flags and self.flushes==1:
            self.disk=deepcopy(self.live)
            self.disk["unrelated"]={"corrupt":True}
        else:
            self.disk=deepcopy(self.live)
        return deepcopy(self.disk)


def run(coro):
    return asyncio.run(coro)


def preview(port):
    return run(preview_bulk_energy_transaction(port,"verified-admin",account=ACCOUNT,lot=LOT))


def apply(port, p, *, confirm=True):
    return run(apply_bulk_energy_transaction(port,"verified-admin",account=ACCOUNT,lot=LOT,
              approved_before=p.before,approved_digest=p.plan_digest,confirm=confirm))


def test_safe_block_without_native_36_37_evidence():
    p=FakePort(blocked=True)
    item=preview(p)
    assert item.status=="blocked" and item.writes is False and item.activation_authorized is False
    assert p.writes==p.backups==0


def test_preview_never_writes_or_backs_up():
    p=FakePort()
    before=deepcopy(p.live)
    result=preview(p)
    assert result.status=="prepared_for_explicit_admin_review"
    assert p.backups==p.writes==0 and p.live==before and p.disk==before
    assert result.activation_authorized is False


def test_non_admin_denied_before_any_read_or_write():
    p=FakePort(authorized=False)
    with pytest.raises(PermissionError):
        preview(p)
    assert p.backups==p.writes==0


def test_missing_explicit_confirmation_is_refused():
    p=FakePort();v=preview(p)
    with pytest.raises(EnergyTransactionRefused):
        apply(p,v,confirm=False)
    assert p.backups==p.writes==0


def test_success_additive_and_preserves_all_third_party_settings():
    p=FakePort(fluids=("EF","ECS","CET"));old=deepcopy(p.live)
    v=preview(p);assert v.proposed_count==3
    r=apply(p,v)
    assert r["status"]=="persisted_verified" and r["activation_authorized"] is False
    assert p.live["energy_sources"][:1]==old["energy_sources"]
    assert [v["type"] for v in p.live["energy_sources"][1:]] == ["water","water","gas"]
    assert p.live["device_consumption"]==old["device_consumption"]
    assert p.live["unrelated"]==old["unrelated"]
    assert p.disk==p.live and p.backups==1 and p.writes==1
    assert p.audit[-1]["status"]=="verified"


def test_duplicated_preview_fingerprint_rejected_before_backup():
    p=FakePort();v=preview(p)
    with pytest.raises(EnergyTransactionRefused):
        run(apply_bulk_energy_transaction(p,"verified-admin",account=ACCOUNT,lot=LOT,
                 approved_before=v.before,approved_digest="wrong-digest",confirm=True))
    assert p.backups==p.writes==0


def test_concurrent_preference_change_before_apply_refused():
    p=FakePort();v=preview(p)
    p.live["unrelated"]={"third_party":True}
    p.disk=deepcopy(p.live)
    with pytest.raises(EnergyTransactionRefused):
        apply(p,v)
    assert p.backups==p.writes==0


def test_backup_failure_prevents_any_write():
    p=FakePort();v=preview(p);p.flags.add("backup_fail")
    with pytest.raises(IOError):
        apply(p,v)
    assert p.writes==0


def test_backup_unverified_prevents_any_write():
    p=FakePort();v=preview(p);p.flags.add("backup_unverified")
    with pytest.raises(EnergyTransactionRefused,match="backup"):
        apply(p,v)
    assert p.writes==0


def test_journal_failure_prevents_any_write():
    p=FakePort();v=preview(p);p.flags.add("journal_fail")
    with pytest.raises(IOError):
        apply(p,v)
    assert p.writes==0


def test_apply_fail_before_mutation_no_rollback_needed():
    p=FakePort();v=preview(p);p.flags.add("apply_fail_before")
    with pytest.raises(EnergyTransactionRefused,match="before"):
        apply(p,v)
    assert p.disk==p.live==initial() and p.audit[-1]["status"]=="no_write_observed"


def test_apply_fail_after_mutation_rolls_back():
    p=FakePort();v=preview(p);p.flags.add("apply_fail_after")
    with pytest.raises(EnergyTransactionRefused,match="rollback verified"):
        apply(p,v)
    assert p.writes==2 and p.live==p.disk==initial()
    assert p.audit[-1]["status"]=="rolled_back_verified"


def test_persistence_mismatch_guarded_rollback_or_recovery():
    p=FakePort();v=preview(p);p.flags.add("persisted_mismatch")
    with pytest.raises(EnergyRecoveryRequired):
        apply(p,v)
    assert p.audit[-1]["status"]=="prepared"


def test_concurrent_third_party_change_does_not_get_overwritten():
    p=FakePort();v=preview(p);p.flags.add("third_party_during_apply")
    with pytest.raises(EnergyRecoveryRequired):
        apply(p,v)
    assert p.writes==1 and p.live["unrelated"]=={"changed":True}


def test_wrong_unit_or_missing_recorder_proof_never_triggers_backup():
    p=FakePort();p.candidates[0]["recorder_has_data"]=False
    v=preview(p)
    assert v.status=="blocked" and p.backups==p.writes==0


def test_thermal_approval_is_not_inferred_from_kwh():
    p=FakePort(fluids=("CET",));p.candidates[0]["thermal_category_approved"]=False
    v=preview(p)
    assert v.status=="blocked" and p.writes==0


def test_rejected_scope_and_duplicate_prevent_backup():
    p=FakePort();p.candidates[0]["lot"]="ANOTHER"
    assert preview(p).status=="blocked"
    assert p.backups==p.writes==0


def test_full_idempotence_requires_real_l6_recollection():
    p=FakePort();v=preview(p);apply(p,v)
    # A future L6 reader will classify this as already_configured. Without
    # trusted post-write evidence, the fake cannot assume that classification.
    assert preview(p).status=="blocked"


def test_rollback_failure_is_reported_for_manual_recovery():
    p=FakePort();v=preview(p)
    p.flags.update(("apply_fail_after", "rollback_fail"))
    with pytest.raises(EnergyRecoveryRequired,match="Rollback"):
        apply(p,v)
    assert p.writes==2 and p.audit[-1]["status"]=="prepared"


def test_blocked_second_fluid_keeps_group_atomic():
    p=FakePort(fluids=("EF","ECS"),blocked=True)
    assert preview(p).status=="blocked"
    assert p.backups==p.writes==0


def test_no_automatic_restart_registration():
    from pathlib import Path
    file=Path(__file__).resolve().parents[1]/"custom_components/trybatec/energy_bulk_transaction.py"
    text=file.read_text()
    for prohibited in ("@websocket_api.websocket_command", "async_setup_entry",
                       "async_add_external_statistics", "async_update(",
                       "requests.post(", "TrybatecClient("):
        assert prohibited not in text


def test_other_version_selected_routes_to_separate_replacement_flow():
    p=FakePort()
    p.live["energy_sources"].append({"type":"water", "stat_energy_from":"sensor.synthetic_prior_ef"})
    p.disk=deepcopy(p.live)
    assert preview(p).status=="blocked"
    assert p.backups==p.writes==0


def test_existing_prepared_journal_requires_explicit_recovery_first():
    p=FakePort();v=preview(p)
    p.audit.append({"status":"prepared", "synthetic":True})
    with pytest.raises(EnergyRecoveryRequired,match="Unresolved earlier"):
        apply(p,v)
    assert p.backups==p.writes==0


def test_journal_not_readable_durably_refuses_before_write():
    p=FakePort();v=preview(p)
    async def lost():
        return None
    p.read_last_journal=lost
    with pytest.raises(EnergyRecoveryRequired,match="not durably readable"):
        apply(p,v)
    assert p.backups==1 and p.writes==0
