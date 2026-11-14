"""#88 scoped admission: synthetic counterexamples, no production assertions."""
from copy import deepcopy

import pytest

from custom_components.trybatec.energy_bulk_scoped_l6_88 import (
    _digest, assess_scoped_selection_l6_88,
)

SID = "trybatec:synthetic_eau_v02"
OLD = "trybatec:synthetic_eau_quarantine_v01"


def synthetic():
    choice = {
        "account": "SYNTH-ACCOUNT", "lot": "SYNTH-LOT", "fluid": "EF",
        "start": "2026-03-01", "end": "2026-03-02",
        "statistic_id": SID, "generation_ids": ["GEN-RETIRED", "GEN-NEW"],
        "rows_hash": "a" * 64,
    }
    binding = {k: choice[k] for k in (
        "account", "lot", "fluid", "start", "end", "statistic_id")}
    stamp = _digest(choice)
    recorder = {
        "schema": "history_36_scoped_selection_v2",
        **binding, "selection_digest": stamp,
        "mode": "native_immutable_readback",
        "selected_version_state": "verified_immutable",
        "selected_series_persisted": True,
        "post_restart_readback_verified": True,
        "pending_for_selected_id": False,
        "quarantined_selected_id": False,
        "selected_statistic_id_owned_by_one_scope": True,
        "unit": "m³",
        "metadata": {
            "unit": "m³", "device_class": "water",
            "has_sum": True, "has_data": True,
            "persisted_readback_hash": choice["rows_hash"],
        },
        "version_catalog_complete_for_selected_scope": True,
        "versions": [
            {"statistic_id": SID, "state": "verified_immutable"},
            {"statistic_id": OLD, "state": "quarantined"},
        ],
        "selected_total": "3",
        "daily": [
            {"date": "2026-03-01", "measured": "1", "estimated": "0"},
            {"date": "2026-03-02", "measured": "0", "estimated": "2"},
        ],
        "approved_days": [{
            "ref": "APPROVAL-02", "date": "2026-03-02",
            "generation_id": "GEN-NEW", "statistic_id": SID,
            "provenance": "portal_unattested_user_approved",
            "amount": "2", "revision_hash": "b" * 64, "approved": True,
        }],
    }
    lineage = {
        "schema": "lineage_37_scoped_selection_v2",
        **binding, "selection_digest": stamp,
        "mode": "native_selected_generations",
        "selected_generation_ids": choice["generation_ids"].copy(),
        "selected_scope_reconciled": True, "unit": "m³",
        "version_catalog_reconciled": True, "competing_version_conflict": False,
        "generations": [
            {"generation_id": "GEN-RETIRED", "status": "retired", "unit": "m³",
             "identity_verified": True, "supplier_observation_attested": True},
            {"generation_id": "GEN-NEW", "status": "active", "unit": "m³",
             "identity_verified": True, "supplier_observation_attested": False},
        ],
        "selected_total": "3",
        "daily": [
            {"date": "2026-03-01", "total": "1", "contributors": [{
                "generation_id": "GEN-RETIRED",
                "amount": "1", "provenance": "measured",
                "source_observation_verified": True, "reading_pair_hash": "c" * 64,
            }]},
            {"date": "2026-03-02", "total": "2", "contributors": [{
                "generation_id": "GEN-NEW", "amount": "2",
                "provenance": "portal_unattested_user_approved",
                "approval_ref": "APPROVAL-02",
            }]},
        ],
    }
    prefs = {
        "energy_sources": [{"type": "grid", "stat_energy_from": "sensor.synthetic_grid"}],
        "device_consumption": [{"stat_consumption": "sensor.synthetic_external"}],
        "device_consumption_water": [],
    }
    audit = {
        "native_ha_readback": True, "live": prefs, "persisted": deepcopy(prefs),
        "catalog_complete_for_selected_scope": True,
        "alternative_ids": [SID, OLD],
        "external_writer_revalidation_required": True,
        "classified_references": [
            {"section": "energy_sources", "index": 0, "field": "stat_energy_from",
             "statistic_id": "sensor.synthetic_grid",
             "relation": "scope_disjoint_verified"},
            {"section": "device_consumption", "index": 0, "field": "stat_consumption",
             "statistic_id": "sensor.synthetic_external",
             "relation": "scope_disjoint_verified"},
        ],
    }
    return choice, recorder, lineage, audit


def validate(bundle):
    return assess_scoped_selection_l6_88(*bundle)


def test_scoped_positive_fictional_no_global_exhaustiveness_needed():
    data = synthetic()
    before = deepcopy(data)
    output = validate(data)
    assert output["status"] == "eligible_for_scoped_review"
    assert output["blockers"] == []
    assert output["selected_statistic_id"] == SID
    assert output["approved_unattested_contributions"] == 1
    assert output["quarantined_alternative_versions"] == 1
    assert output["global_supplier_history_attested"] is False
    assert output["supplier_portal_comparison"] == "user_responsibility"
    assert output["activation_authorized"] is False and output["writes"] is False
    assert data == before


@pytest.mark.parametrize("change,reason", [
    ("selection_range_changed", "history_36_scoped_selection_v2_scope_or_digest_mismatch"),
    ("recorder_legacy_v1", "history_36_scoped_selection_v2_scope_or_digest_mismatch"),
    ("lineage_missing", "independent_native_producers_missing"),
    ("selected_quarantined", "selected_immutable_recorder_version_not_verified"),
    ("reused_immutable_identity", "selected_immutable_recorder_version_not_verified"),
    ("unverified_readback", "selected_immutable_recorder_version_not_verified"),
    ("missing_restart_proof", "selected_immutable_recorder_version_not_verified"),
    ("unknown_recorder_unit", "selected_source_unit_incompatible"),
    ("recorder_sum_absent", "selected_recorder_metadata_or_rows_mismatch"),
    ("statistic_id_reused", "version_reused_duplicated_or_unclassified"),
    ("unlisted_competitor", "competing_versions_not_independently_enumerated"),
    ("alternative_selected", "selected_or_quarantined_version_already_in_energy"),
    ("quarantined_version_selected", "selected_or_quarantined_version_already_in_energy"),
    ("unknown_third_party", "third_party_reference_not_disjoint_or_unverified"),
    ("omitted_device_source", "third_party_references_not_exhaustively_classified"),
    ("competing_source_in_water", "third_party_references_not_exhaustively_classified"),
    ("stale_preferences", "energy_live_disk_conflict"),
    ("omitted_day", "selected_daily_window_missing_or_partial"),
    ("duplicate_day", "selected_days_missing_duplicated_or_reordered"),
    ("overlapping_generation", "unknown_or_duplicate_generation_contribution"),
    ("physical_sum_wrong", "recorder_lineage_day_amount_mismatch"),
    ("user_not_approved", "missing_independent_day_version_user_approval"),
    ("approval_different_version", "missing_independent_day_version_user_approval"),
    ("approval_wrong_day", "missing_independent_day_version_user_approval"),
    ("unattested_as_measured", "measured_day_must_not_be_relabelled"),
    ("unknown_provenance", "unknown_or_falsified_source_provenance"),
    ("measured_without_vendor_indexes", "measured_contribution_without_vendor_readings"),
    ("selected_generation_missing", "selected_generation_inventory_missing"),
    ("external_writer_check_missing", "external_energy_writer_concurrency_unaddressed"),
])
def test_scoped_refusals_are_not_mutation_permits(change, reason):
    choice, recorder, lineage, audit = synthetic()
    if change == "selection_range_changed":
        choice["end"] = "2026-03-03"
    elif change == "recorder_legacy_v1":
        recorder["schema"] = "history_36_recorder_handoff_v1"
    elif change == "lineage_missing":
        lineage = None
    elif change == "selected_quarantined":
        recorder["quarantined_selected_id"] = True
    elif change == "reused_immutable_identity":
        recorder["selected_statistic_id_owned_by_one_scope"] = False
    elif change == "unverified_readback":
        recorder["selected_series_persisted"] = False
    elif change == "missing_restart_proof":
        recorder["post_restart_readback_verified"] = False
    elif change == "unknown_recorder_unit":
        recorder["unit"] = "kWh"
    elif change == "recorder_sum_absent":
        recorder["metadata"]["has_sum"] = False
    elif change == "statistic_id_reused":
        recorder["versions"].append({"statistic_id": SID, "state": "verified_immutable"})
    elif change == "unlisted_competitor":
        audit["alternative_ids"] = [SID]
    elif change == "alternative_selected":
        audit["live"]["energy_sources"].append({
            "type": "water", "stat_energy_from": SID,
        })
        audit["persisted"] = deepcopy(audit["live"])
        audit["classified_references"].append({
            "section": "energy_sources", "index": 1,
            "field": "stat_energy_from", "statistic_id": SID,
            "relation": "scope_disjoint_verified",
        })
    elif change == "quarantined_version_selected":
        audit["live"]["device_consumption_water"].append({
            "stat_consumption": OLD,
        })
        audit["persisted"] = deepcopy(audit["live"])
        audit["classified_references"].append({
            "section": "device_consumption_water", "index": 0,
            "field": "stat_consumption", "statistic_id": OLD,
            "relation": "scope_disjoint_verified",
        })
    elif change == "unknown_third_party":
        audit["classified_references"][1]["relation"] = "unknown"
    elif change == "omitted_device_source":
        audit["classified_references"].pop()
    elif change == "competing_source_in_water":
        audit["live"]["device_consumption_water"].append({
            "stat_consumption": "sensor.some_other_water",
        })
        audit["persisted"] = deepcopy(audit["live"])
    elif change == "stale_preferences":
        audit["persisted"]["energy_sources"] = []
    elif change == "omitted_day":
        recorder["daily"].pop()
    elif change == "duplicate_day":
        lineage["daily"][1]["date"] = "2026-03-01"
    elif change == "overlapping_generation":
        lineage["daily"][1]["contributors"].append(
            deepcopy(lineage["daily"][1]["contributors"][0]))
    elif change == "physical_sum_wrong":
        lineage["daily"][1]["total"] = "7"
    elif change == "user_not_approved":
        recorder["approved_days"][0]["approved"] = False
    elif change == "approval_different_version":
        recorder["approved_days"][0]["statistic_id"] = OLD
    elif change == "approval_wrong_day":
        recorder["approved_days"][0]["date"] = "2026-03-01"
    elif change == "unattested_as_measured":
        lineage["daily"][1]["contributors"][0]["provenance"] = "measured"
    elif change == "unknown_provenance":
        lineage["daily"][1]["contributors"][0]["provenance"] = "invented_vendor_measured"
    elif change == "measured_without_vendor_indexes":
        lineage["daily"][0]["contributors"][0].pop("reading_pair_hash")
    elif change == "selected_generation_missing":
        lineage["generations"].pop()
    elif change == "external_writer_check_missing":
        audit["external_writer_revalidation_required"] = False
    out = validate((choice, recorder, lineage, audit))
    assert out["status"] == "blocked", change
    assert reason in out["blockers"], (change, out["blockers"])
    assert out["activation_authorized"] is False
    assert out["writes"] is False


def synthetic_heating():
    choice, rec, lineage, audit = synthetic()
    choice["fluid"] = rec["fluid"] = lineage["fluid"] = "CET"
    rec["unit"] = lineage["unit"] = "kWh"
    rec["metadata"]["unit"] = "kWh"
    rec["metadata"]["device_class"] = "energy"
    for gen in lineage["generations"]:
        gen["unit"] = "kWh"
    digest = _digest(choice)
    rec["selection_digest"] = lineage["selection_digest"] = digest
    return choice, rec, lineage, audit


def test_cet_kwh_can_be_prepared_without_claiming_live_display_acceptance():
    from custom_components.trybatec.energy_bulk_scoped_state_88 import (
        build_native_scoped_energy_state_88,
    )
    from custom_components.trybatec.energy_bulk_transaction import _prepare_state

    choice, rec, lineage, audit = synthetic_heating()
    result = validate((choice, rec, lineage, audit))
    assert result["status"] == "eligible_for_scoped_review"
    state = build_native_scoped_energy_state_88(
        deepcopy(audit["live"]), [{
            "selection": choice, "history_36": rec,
            "lineage_37": lineage, "energy_audit": audit,
        }], account=choice["account"], lot=choice["lot"],
        schema_version="2026.11.1",
    )
    preview, plan = _prepare_state(state, account=choice["account"], lot=choice["lot"])
    assert preview.status == "prepared_for_explicit_admin_review"
    assert state.candidates[0]["unit"] == "kWh"
    assert plan["proposed"]["energy_sources"][-1] == {
        "type": "gas", "stat_energy_from": SID,
    }
    assert not preview.writes and not preview.activation_authorized


@pytest.mark.parametrize("broken", ["unit", "recorder", "lineage", "approval"])
def test_heating_keeps_independent_safety_requirements(broken):
    bundle = synthetic_heating()
    if broken == "unit":
        bundle[1]["metadata"]["unit"] = "m³"
    elif broken == "recorder":
        bundle[1]["selected_series_persisted"] = False
    elif broken == "lineage":
        bundle[2]["selected_scope_reconciled"] = False
    else:
        bundle[1]["approved_days"][0]["approved"] = False
    result = validate(bundle)
    assert result["status"] == "blocked"
    assert not result["writes"] and not result["activation_authorized"]


def test_linear_smoothing_with_matching_user_validation_is_allowed_but_not_vendor_measured():
    choice, rec, lineage, audit = synthetic()
    approval = rec["approved_days"][0]
    contributor = lineage["daily"][1]["contributors"][0]
    approval["provenance"] = contributor["provenance"] = "linear_user_approved"
    result = validate((choice, rec, lineage, audit))
    assert result["status"] == "eligible_for_scoped_review"
    assert result["approved_unattested_contributions"] == 0
    assert result["global_supplier_history_attested"] is False
    assert result["writes"] is False


def test_scoped_admin_diagnostics_expose_positive_without_any_activation():
    from custom_components.trybatec.energy_bulk_admin_service_88 import (
        _blockers, _native_l6_diagnostics,
    )

    choice, rec, lineage, audit = synthetic()
    evidence = {
        "scoped_selections_v2": [{
            "selection": choice, "history_36": rec,
            "lineage_37": lineage, "energy_audit": audit,
        }],
        # Synthetic success does NOT prove actual restore.
        "native_backup_restore_qualified": False,
    }
    diagnostics = _native_l6_diagnostics(evidence, account=choice["account"],
                                          lot=choice["lot"])
    assert diagnostics["EF"]["status"] == "eligible_for_scoped_review"
    assert diagnostics["EF"]["approved_unattested_contributions"] == 1
    assert diagnostics["EF"]["global_supplier_history_attested"] is False
    assert diagnostics["EF"]["activation_authorized"] is False
    blockers = _blockers(evidence)
    assert "native_backup_restore_not_qualified" in blockers
    assert "l7_external_writer_commit_guarantee_not_qualified" in blockers
    assert "history_36_global_historical_lineage_attested_unverified" not in blockers
    assert "l6_independent_historical_inventory_unverified" not in blockers


def test_absent_or_malformed_scoped_producers_are_never_silently_accepted():
    from custom_components.trybatec.energy_bulk_admin_service_88 import _blockers

    assert "l6_selected_scopes_missing_or_ambiguous" in _blockers({
        "scoped_selections_v2": [],
    })
    assert "l6_native_selection_missing" in _blockers({
        "scoped_selections_v2": [{}],
    })
    data = synthetic()
    first = {"selection": data[0], "history_36": data[1],
             "lineage_37": data[2], "energy_audit": data[3]}
    assert "l6_selection_fluid_duplicate_or_unknown" in _blockers({
        "scoped_selections_v2": [first, deepcopy(first)],
    })


def test_legacy_global_v1_does_not_gain_trust_from_scoped_business_arbitration():
    from custom_components.trybatec.energy_bulk_admin_service_88 import _blockers
    blockers = _blockers({
        "independent_contracts": {
            "history_36": {"schema": "history_36_recorder_handoff_v1"},
            "lineage_37": {"schema": "lineage_37_energy_handoff_v1"},
        },
    })
    assert "history_36_native_attestation_missing" in blockers
    assert "lineage_37_native_attestation_missing" in blockers


def test_synthetic_scoped_l6_to_l7_complete_additive_transaction():
    """A fictional native producer feeds the L7 port; the real port stays OFF."""
    import asyncio
    from contextlib import asynccontextmanager

    from custom_components.trybatec.energy_bulk_transaction import (
        EnergyTransactionRefused,
        apply_bulk_energy_transaction, preview_bulk_energy_transaction,
    )
    from custom_components.trybatec.energy_switch import preferences_fingerprint

    proofs = synthetic()

    class FictionalNativePort:
        def __init__(self):
            self.prefs = deepcopy(proofs[3]["live"])
            self.disk = deepcopy(self.prefs)
            self.last_journal = None
            self.backups = 0
            self.writes = 0
            self.lock = asyncio.Lock()

        async def assert_admin(self, actor):
            if actor != "synthetic-administrator":
                raise PermissionError("native admin required")

        @asynccontextmanager
        async def exclusive(self):
            async with self.lock:
                yield

        async def collect(self, actor, *, account, lot):
            await self.assert_admin(actor)
            assert account == "SYNTH-ACCOUNT" and lot == "SYNTH-LOT"
            from custom_components.trybatec.energy_bulk_scoped_state_88 import (
                build_native_scoped_energy_state_88,
            )

            # This fixture supplies fictional independent v2 envelopes,
            # but exercises the exact L6 candidate builder and native L7
            # state machine rather than bypassing with arbitrary booleans.
            return build_native_scoped_energy_state_88(
                deepcopy(self.prefs),
                [{
                    "selection": proofs[0], "history_36": proofs[1],
                    "lineage_37": proofs[2], "energy_audit": proofs[3],
                }],
                account=account, lot=lot, schema_version="2026.11.1",
            )

        async def read_live(self):
            return deepcopy(self.prefs)

        async def read_persisted(self):
            return deepcopy(self.disk)

        async def create_backup(self):
            self.backups += 1
            return {"fictional_recoverable_copy": True}

        async def verify_backup(self, receipt):
            return receipt.get("fictional_recoverable_copy") is True

        async def journal(self, payload):
            self.last_journal = deepcopy(payload)

        async def read_last_journal(self):
            return deepcopy(self.last_journal)

        async def write_energy_sources(self, sources):
            if (self.last_journal is None or
                    self.last_journal["status"] != "prepared"):
                raise EnergyTransactionRefused("No durable synthetic journal")
            self.writes += 1
            self.prefs["energy_sources"] = deepcopy(sources)

        async def flush_and_read_persisted(self):
            self.disk = deepcopy(self.prefs)
            return deepcopy(self.disk)

    async def scenario():
        port = FictionalNativePort()
        actor = "synthetic-administrator"
        first = deepcopy(port.prefs)
        preview = await preview_bulk_energy_transaction(
            port, actor, account="SYNTH-ACCOUNT", lot="SYNTH-LOT",
        )
        assert preview.status == "prepared_for_explicit_admin_review"
        assert preview.proposed_count == 1
        assert port.writes == port.backups == 0
        result = await apply_bulk_energy_transaction(
            port, actor, account="SYNTH-ACCOUNT", lot="SYNTH-LOT",
            approved_before=preview.before,
            approved_digest=preview.plan_digest, confirm=True,
        )
        assert result["status"] == "persisted_verified"
        assert result["activation_authorized"] is False
        assert port.backups == port.writes == 1
        assert port.last_journal["status"] == "verified"
        assert port.disk == port.prefs
        assert port.prefs["energy_sources"][:1] == first["energy_sources"]
        assert port.prefs["energy_sources"][1:] == [{
            "type": "water", "stat_energy_from": SID,
        }]
        assert port.prefs["device_consumption"] == first["device_consumption"]
        assert port.prefs["device_consumption_water"] == first["device_consumption_water"]
        assert port.last_journal["backup"] == {"fictional_recoverable_copy": True}

        # Unapproved range or conflicting lineage cannot reach a backup.
        denied = FictionalNativePort()
        denied_proofs = proofs[1]["approved_days"][0]
        denied_proofs["approved"] = False
        blocked = await preview_bulk_energy_transaction(
            denied, actor, account="SYNTH-ACCOUNT", lot="SYNTH-LOT",
        )
        assert blocked.status == "blocked"
        assert denied.backups == denied.writes == 0

    asyncio.run(scenario())


def _approved_missing_day_bundle():
    choice, recorder, lineage, audit = synthetic()
    # Keep only the verified measured row. The second civil day is approved
    # as having NO supplier/Recorder statistic, not invented zero consumption.
    choice["accepted_missing_days"] = ["2026-03-02"]
    recorder["daily"] = recorder["daily"][:1]
    lineage["daily"] = lineage["daily"][:1]
    recorder["selected_total"] = lineage["selected_total"] = "1"
    proof = {
        "date": "2026-03-02", "statistic_id": SID, "approved": True,
        "provenance": "portal_unattested_user_approved",
        "no_statistical_row": True, "quantity": None,
        "decision_ref": "SYNTH-MISSING-02", "revision_hash": "e" * 64,
    }
    recorder["approved_absences"] = [deepcopy(proof)]
    lineage["approved_absences"] = [deepcopy(proof)]
    recorder["selection_digest"] = lineage["selection_digest"] = _digest(choice)
    return choice, recorder, lineage, audit


def test_approved_missing_window_does_not_fabricate_a_zero_or_vendor_reading():
    bundle = _approved_missing_day_bundle()
    result = validate(bundle)
    assert result["status"] == "eligible_for_scoped_review"
    assert result["approved_missing_days_without_fabricated_rows"] == 1
    assert len(bundle[1]["daily"]) == len(bundle[2]["daily"]) == 1
    assert bundle[1]["daily"][0]["date"] == "2026-03-01"
    assert result["global_supplier_history_attested"] is False
    assert result["activation_authorized"] is False


def test_missing_day_without_both_independent_receipts_remains_blocked():
    bundle = _approved_missing_day_bundle()
    bundle[2].pop("approved_absences")
    result = validate(bundle)
    assert result["status"] == "blocked"
    assert "independent_missing_day_receipts_unavailable" in result["blockers"]


def test_missing_day_receipt_may_not_claim_a_measured_zero():
    bundle = _approved_missing_day_bundle()
    bundle[1]["approved_absences"][0]["quantity"] = "0"
    bundle[2]["approved_absences"][0]["quantity"] = "0"
    result = validate(bundle)
    assert result["status"] == "blocked"
    assert "invalid_missing_day_approval" in result["blockers"]


def test_missing_day_cannot_be_implicitly_zero_when_unapproved():
    bundle = list(_approved_missing_day_bundle())
    bundle[0].pop("accepted_missing_days")
    # Canonical selection digest is refreshed but the decision does not exist.
    digest = _digest(bundle[0])
    bundle[1]["selection_digest"] = bundle[2]["selection_digest"] = digest
    result = validate(bundle)
    assert result["status"] == "blocked"
    assert "missing_days_not_exactly_user_approved" in result["blockers"]


def test_native_v2_scoped_proofs_build_actual_l7_plan_not_only_a_diagnostic():
    from custom_components.trybatec.energy_bulk_scoped_state_88 import (
        build_native_scoped_energy_state_88,
    )
    from custom_components.trybatec.energy_bulk_transaction import _prepare_state

    selection, recorder, lineage, audit = synthetic()
    old_prefs = deepcopy(audit["live"])
    state = build_native_scoped_energy_state_88(
        old_prefs, [{
            "selection": selection, "history_36": recorder,
            "lineage_37": lineage, "energy_audit": audit,
        }], account=selection["account"], lot=selection["lot"],
        schema_version="2026.11.1",
    )
    assert state.evidence["scoped_mode"] == "native_server_selected_scope_v2"
    assert [c["statistic_id"] for c in state.candidates] == [SID]
    assert state.evidence["fluids"]["EF"]["status"] == "admissible"
    assert state.evidence["fluids"]["ECS"]["status"] == "not_selected"
    assert state.evidence["fluids"]["CET"]["status"] == "not_selected"
    prepared, plan = _prepare_state(
        state, account=selection["account"], lot=selection["lot"],
    )
    assert prepared.status == "prepared_for_explicit_admin_review"
    assert prepared.proposed_count == 1
    assert prepared.writes is False and prepared.activation_authorized is False
    assert plan["proposed"]["energy_sources"] == [
        *old_prefs["energy_sources"],
        {"type": "water", "stat_energy_from": SID},
    ]
    assert plan["proposed"]["device_consumption"] == old_prefs["device_consumption"]
    assert plan["proposed"]["device_consumption_water"] == old_prefs["device_consumption_water"]


def test_native_scoped_builder_detects_approval_revocation_and_never_selects():
    from custom_components.trybatec.energy_bulk_scoped_state_88 import (
        build_native_scoped_energy_state_88,
    )
    from custom_components.trybatec.energy_bulk_transaction import _prepare_state

    selection, recorder, lineage, audit = synthetic()
    recorder["approved_days"][0]["approved"] = False
    state = build_native_scoped_energy_state_88(
        deepcopy(audit["live"]), [{
            "selection": selection, "history_36": recorder,
            "lineage_37": lineage, "energy_audit": audit,
        }], account=selection["account"], lot=selection["lot"],
        schema_version="2026.11.1",
    )
    assert state.candidates == ()
    assert state.evidence["fluids"]["EF"]["status"] == "blocked"
    preview, plan = _prepare_state(
        state, account=selection["account"], lot=selection["lot"],
    )
    assert preview.status == "blocked" and plan is None


def test_native_scoped_builder_can_preserve_absent_user_approved_days():
    from custom_components.trybatec.energy_bulk_scoped_state_88 import (
        build_native_scoped_energy_state_88,
    )
    from custom_components.trybatec.energy_bulk_transaction import _prepare_state

    choice, rec, lineage, audit = _approved_missing_day_bundle()
    state = build_native_scoped_energy_state_88(
        deepcopy(audit["live"]), [{
            "selection": choice, "history_36": rec,
            "lineage_37": lineage, "energy_audit": audit,
        }], account=choice["account"], lot=choice["lot"],
        schema_version="2026.11.1",
    )
    preview, plan = _prepare_state(
        state, account=choice["account"], lot=choice["lot"],
    )
    assert preview.status == "prepared_for_explicit_admin_review"
    assert plan is not None
    assert len(rec["daily"]) == 1
    assert choice["accepted_missing_days"] == ["2026-03-02"]
    assert preview.activation_authorized is False


def test_native_scoped_builder_rejects_wrong_account_and_stale_energy():
    from custom_components.trybatec.energy_bulk_scoped_state_88 import (
        build_native_scoped_energy_state_88,
    )
    from custom_components.trybatec.energy_bulk_transaction import (
        EnergyTransactionRefused,
    )

    choice, rec, lineage, audit = synthetic()
    proof = {
        "selection": choice, "history_36": rec,
        "lineage_37": lineage, "energy_audit": audit,
    }
    with pytest.raises(EnergyTransactionRefused, match="Wrong or duplicated"):
        build_native_scoped_energy_state_88(
            deepcopy(audit["live"]), [proof],
            account="FOREIGN-ACCOUNT", lot=choice["lot"],
            schema_version="2026.11.1",
        )
    prefs = deepcopy(audit["live"])
    prefs["device_consumption"].append({
        "stat_consumption": "sensor.new_third_party",
    })
    with pytest.raises(EnergyTransactionRefused, match="Concurrent or foreign"):
        build_native_scoped_energy_state_88(
            prefs, [proof], account=choice["account"],
            lot=choice["lot"], schema_version="2026.11.1",
        )
