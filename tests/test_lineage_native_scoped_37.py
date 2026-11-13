"""#37 v2: synthetic native-scope proof; no HA, Recorder or API access."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sys
import types
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec"
PKG = "lineage37_native_scope_isolated"
package = types.ModuleType(PKG)
package.__path__ = [str(ROOT)]
sys.modules.setdefault(PKG, package)


def load(name):
    fullname = f"{PKG}.{name}"
    spec = importlib.util.spec_from_file_location(fullname, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[fullname] = module
    spec.loader.exec_module(module)
    return module


scoped = load("lineage_selected_scope_37")
native = load("lineage_native_scoped_37")
ACCOUNT = "SYNTHETIC-ACCOUNT"
LOT, FLUID = "SYNTH-LOT", "EF"
SID = "trybatec:fictional_v03"
T1 = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
T2 = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)
T3 = datetime(2026, 1, 3, 12, tzinfo=timezone.utc)
T4 = datetime(2026, 1, 4, 12, tzinfo=timezone.utc)
SRC = {"OLD": "a" * 64, "NEW": "b" * 64}
REV = "c" * 64


def source(serial, readings, *, retired=False):
    return {
        "lot": LOT, "fluid": FLUID, "serial": serial,
        "source_fingerprint": SRC[serial], "retired": retired,
        "reviewed_readings": readings, "fatal_conflicts": False,
    }


def measured(serial, day, amount):
    return {
        "date": day, "consumption": amount,
        "contributors": [{
            "serial": serial, "provenance": "measured", "consumption": amount,
        }],
    }


def estimated(day="2026-01-03", amount="0.5"):
    return {
        "date": day, "consumption": amount,
        "contributors": [{
            "serial": "NEW", "provenance": "estimated_linear_confirmed",
            "consumption": amount, "measured": "0", "estimated": amount,
            "decision_attribution": "day_revision_candidate_unverified",
            "decision_fingerprint": "approved-interval-A",
            "revision_fingerprint": REV,
        }],
    }


def fixtures(*, estimate=False, gap=False):
    raw = {"__physical_meters__": {
        (LOT, FLUID, "OLD"): source("OLD", [(T1, 10), (T2, 11)], retired=True),
        (LOT, FLUID, "NEW"): source("NEW", [
            (T2, 50), (T3, 52)] if not estimate else [(T2, 50), (T4, 51)],
        ),
    }}
    rows = [measured("OLD", "2026-01-02", "1")]
    if not gap:
        rows.append(estimated() if estimate else measured("NEW", "2026-01-03", "2"))
    preview = {
        "mode": "read_only_37_history_bridge",
        "writes": False, "energy_activation_authorized": False,
        "historical_inventory_proven_complete": False,
        "inventory": [{
            "lot": LOT, "fluid": FLUID, "serial": serial,
            "source_fingerprint": SRC[serial],
            "status": "depose" if serial == "OLD" else "en_service",
            "service_start": None, "service_end": None,
        } for serial in ("OLD", "NEW")],
        "groups": [{
            "lot": LOT, "fluid": FLUID, "status": "preview_only",
            "blockers": [], "rows": rows,
        }],
    }
    selection = {
        "account": ACCOUNT, "lot": LOT, "fluid": FLUID,
        "start": "2026-01-02", "end": "2026-01-03",
        "statistic_id": SID,
        "serials": ["OLD", "NEW"],
        "generation_ids": [
            native.generation_id_37(ACCOUNT, LOT, FLUID, s)
            for s in ("OLD", "NEW")
        ],
        "accepted_missing_days": ["2026-01-03"] if gap else [],
        "rows_hash": "d" * 64,
    }
    selection["physical_snapshot_digest"] = scoped.selected_snapshot_37(
        ACCOUNT, preview, lot=LOT, fluid=FLUID,
        start="2026-01-02", end="2026-01-03", serials=selection["serials"],
    )
    proof = {
        "schema": "history_36_scoped_selection_v2",
        "mode": "native_immutable_readback",
        "account": ACCOUNT, "lot": LOT, "fluid": FLUID,
        "start": "2026-01-02", "end": "2026-01-03",
        "statistic_id": SID, "unit": "m³",
        "selected_version_state": "verified_immutable",
        "selected_series_persisted": True,
        "post_restart_readback_verified": True,
        "pending_for_selected_id": False,
        "quarantined_selected_id": False,
        "selected_statistic_id_owned_by_one_scope": True,
        "version_catalog_complete_for_selected_scope": True,
        "metadata": {"unit": "m³", "device_class": "water",
                     "has_sum": True, "has_data": True,
                     "persisted_readback_hash": selection["rows_hash"]},
        "versions": [{"statistic_id": SID, "state": "verified_immutable"},
                     {"statistic_id": "trybatec:old_version",
                      "state": "quarantined"}],
        "selected_total": ("1" if gap else "1.5" if estimate else "3"),
        "daily": [
            {"date": "2026-01-02", "measured": "1", "estimated": "0"},
        ] + ([] if gap else [{
            "date": "2026-01-03",
            "measured": "0" if estimate else "2",
            "estimated": "0.5" if estimate else "0",
        }]),
        "approved_days": [{
            "date": "2026-01-03",
            "generation_id": selection["generation_ids"][1],
            "ref": "approved-interval-A", "statistic_id": SID,
            "revision_hash": REV, "amount": "0.500000",
            "provenance": "linear_user_approved",
            "approved": True,
        }] if estimate else [],
        "approved_absences": [{
            "date": "2026-01-03", "statistic_id": SID, "approved": True,
            "provenance": "portal_unattested_user_approved",
            "no_statistical_row": True, "quantity": None,
            "decision_ref": "accepted-sparse-day", "revision_hash": REV,
        }] if gap else [],
    }
    proof["selection_digest"] = native._hash(dict(selection))
    original_payloads = [{
        "lines": [{
            "lot": LOT, "fluide": FLUID, "compteur": serial,
            "indexes": [{
                "date": stamp.isoformat(), "value": index,
            } for stamp, index in raw["__physical_meters__"][
                (LOT, FLUID, serial)
            ]["reviewed_readings"]],
        } for serial in ("OLD", "NEW")],
    }]
    return selection, raw, preview, proof, original_payloads


def approved_user(payload):
    return payload["physical_source_fingerprints"] == {
        native.generation_id_37(ACCOUNT, LOT, FLUID, serial): fp
        for serial, fp in SRC.items()
    }


def approved_day(payload):
    return (
        payload["date"] == "2026-01-03"
        and payload["serial"] == "NEW"
        and payload["revision_hash"] == REV
        and payload["amount"] == "0.500000"
        and payload["source_fingerprint"] == SRC["NEW"]
    )


def approved_absence(payload):
    return (
        payload["date"] == "2026-01-03"
        and payload["revision_hash"] == REV
        and payload["quantity"] is None
    )


def evaluate(bundle, **kwargs):
    selection, raw, preview, proof, original_payloads = bundle
    return native.prepare_native_scoped_lineage_37(
        selection, source_history=raw, preview_37=preview,
        original_supplier_payloads=original_payloads,
        native_recorder_36=proof,
        verify_user_selection=kwargs.get("verify_user_selection", approved_user),
        verify_36_day=kwargs.get("verify_36_day", approved_day),
        verify_36_absence=kwargs.get("verify_36_absence", approved_absence),
    )


class NativeScopedLineage37Tests(unittest.TestCase):
    def test_successive_generations_consolidate_deltas_without_index_subtraction(self):
        bundle = fixtures()
        original = deepcopy(bundle)
        evidence = evaluate(bundle)
        self.assertTrue(evidence["selected_scope_reconciled"], evidence["blockers"])
        self.assertEqual(evidence["schema"], "lineage_37_scoped_selection_v2")
        self.assertEqual(evidence["mode"], "native_selected_generations")
        self.assertEqual(evidence["selected_total"], "3.000000")
        self.assertEqual([d["total"] for d in evidence["daily"]],
                         ["1.000000", "2.000000"])
        self.assertEqual([g["status"] for g in evidence["generations"]],
                         ["retired", "active"])
        self.assertIsNone(evidence["generations"][0]["service_end"])
        self.assertIsNone(evidence["generations"][1]["service_start"])
        self.assertEqual(evidence["daily"][0]["contributors"][0]["provenance"], "measured")
        self.assertEqual(len(evidence["daily"][0]["contributors"][0]["reading_pair_hash"]), 64)
        self.assertFalse(evidence["historical_global_exhaustiveness"])
        self.assertFalse(evidence["energy_activation_authorized"])
        self.assertFalse(evidence["writes"])
        self.assertEqual(bundle, original)

    def test_native_88_B15_serial_generation_ids_match_exact_scope(self):
        bundle = fixtures()
        bundle[0]["generation_ids"] = ["OLD", "NEW"]
        bundle[3]["selection_digest"] = native._hash(dict(bundle[0]))
        result = evaluate(bundle, verify_user_selection=lambda evidence: (
            evidence["physical_source_fingerprints"] == SRC
            and evidence["generation_ids"] == ["OLD", "NEW"]
        ))
        self.assertTrue(result["selected_scope_reconciled"], result["blockers"])
        self.assertEqual(result["selected_generation_ids"], ["OLD", "NEW"])
        self.assertEqual(result["generations"][0]["physical_identity_digest"],
                         native.generation_id_37(ACCOUNT, LOT, FLUID, "OLD"))
        self.assertEqual(result["daily"][1]["contributors"][0]["generation_id"], "NEW")
        self.assertFalse(result["energy_activation_authorized"])

    def test_native_88_serial_selection_rejects_foreign_technical_suffix(self):
        bundle = fixtures()
        bundle[0]["generation_ids"] = ["OLD", "NEW_2"]
        with self.assertRaisesRegex(ValueError, "differ from native selected serials"):
            evaluate(bundle)

    def test_exact_36_day_and_revision_allows_unattested_estimate_as_candidate(self):
        p = evaluate(fixtures(estimate=True))
        self.assertTrue(p["selected_scope_reconciled"], p["blockers"])
        self.assertEqual(p["selected_total"], "1.500000")
        self.assertEqual(p["daily"][1]["contributors"][0]["provenance"],
                         "linear_user_approved")
        self.assertFalse(p["generations"][1]["supplier_observation_attested"])

    def test_estimate_over_a_fully_observed_index_pair_is_contradiction(self):
        bundle = fixtures(estimate=True)
        bundle[1]["__physical_meters__"][
            (LOT, FLUID, "NEW")
        ]["reviewed_readings"][1] = (T3, 50)
        bundle[4][0]["lines"][1]["indexes"][1] = {
            "date": T3.isoformat(), "value": 50,
        }
        evidence = evaluate(bundle)
        self.assertFalse(evidence["selected_scope_reconciled"])
        self.assertIn("estimated_day_overlaps_unaltered_raw_measurement",
                      evidence["blockers"])

    def test_missing_36_revision_must_refuse(self):
        bundle = fixtures(estimate=True)
        bundle[3]["approved_days"][0]["revision_hash"] = "e" * 64
        p = evaluate(bundle)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("native_36_exact_day_revision_receipt_mismatch", p["blockers"])

    def test_36_verifier_denial_must_refuse(self):
        p = evaluate(fixtures(estimate=True), verify_36_day=lambda _: False)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("native_36_independent_day_approval_missing", p["blockers"])

    def test_user_verifier_denial_must_refuse(self):
        p = evaluate(fixtures(), verify_user_selection=lambda _: False)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("selected_administrator_decision_not_authenticated", p["blockers"])

    def test_missing_native_36_producer_stays_blocked(self):
        bundle = list(fixtures())
        bundle[3] = None
        p = evaluate(bundle)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("native_36_selected_revision_and_scope_unavailable", p["blockers"])

    def test_accepted_gap_remains_absent_without_zero_row(self):
        p = evaluate(fixtures(gap=True))
        self.assertTrue(p["selected_scope_reconciled"], p["blockers"])
        self.assertEqual(len(p["daily"]), 1)
        self.assertEqual(p["approved_absences"][0]["quantity"], None)
        self.assertTrue(p["approved_absences"][0]["no_statistical_row"])
        self.assertEqual(p["selected_total"], "1.000000")

    def test_missing_gap_receipt_does_not_get_invented(self):
        bundle = fixtures(gap=True)
        bundle[3]["approved_absences"] = []
        p = evaluate(bundle)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("native_36_missing_day_receipt_mismatch", p["blockers"])

    def test_missing_gap_verifier_denial(self):
        p = evaluate(fixtures(gap=True), verify_36_absence=lambda _: False)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("native_36_missing_day_approval_not_authenticated", p["blockers"])

    def test_raw_index_mismatch_is_refused(self):
        bundle = fixtures()
        bundle[1]["__physical_meters__"][(LOT, FLUID, "OLD")]["reviewed_readings"][1] = (
            T2, 13,
        )
        p = evaluate(bundle)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("measured_day_without_supplier_raw_pair", p["blockers"])

    def test_decreasing_raw_index_is_not_a_consumption(self):
        bundle = fixtures()
        bundle[1]["__physical_meters__"][(LOT, FLUID, "OLD")]["reviewed_readings"][1] = (
            T2, 9,
        )
        p = evaluate(bundle)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("decreasing_index_within_selected_generation", p["blockers"])

    def test_raw_meter_fingerprint_change_rejected(self):
        bundle = fixtures()
        bundle[1]["__physical_meters__"][(LOT, FLUID, "OLD")]["source_fingerprint"] = "e" * 64
        p = evaluate(bundle)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("physical_source_fingerprint_mismatch", p["blockers"])

    def test_missing_original_supplier_indexes_cannot_attest_measurement(self):
        bundle = list(fixtures())
        bundle[4] = []
        p = evaluate(bundle)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("measured_day_without_native_index_pair", p["blockers"])

    def test_reviewer_corrected_index_is_not_vendor_observation(self):
        bundle = fixtures()
        bundle[1]["__physical_meters__"][
            (LOT, FLUID, "OLD")
        ]["reviewed_readings"][1] = (T2, 14)
        p = evaluate(bundle)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("measured_day_without_supplier_raw_pair", p["blockers"])

    def test_recorder_daily_quantity_change_is_refused(self):
        bundle = fixtures()
        bundle[3]["daily"][0]["measured"] = "7"
        p = evaluate(bundle)
        self.assertIn("native_36_daily_measured_estimated_mismatch", p["blockers"])
        self.assertFalse(p["selected_scope_reconciled"])

    def test_unknown_old_generation_outside_selection_does_not_block(self):
        bundle = fixtures()
        bundle[2]["inventory"].append({
            "lot": LOT, "fluid": FLUID, "serial": "OTHER",
            "status": "inconnu", "source_fingerprint": None,
        })
        p = evaluate(bundle)
        self.assertTrue(p["selected_scope_reconciled"], p["blockers"])

    def test_same_day_generations_cannot_duplicate(self):
        bundle = fixtures()
        bundle[2]["groups"][0]["rows"][0]["contributors"].append({
            "serial": "NEW", "provenance": "measured", "consumption": "1",
        })
        bundle[2]["groups"][0]["rows"][0]["consumption"] = "2"
        bundle[0]["physical_snapshot_digest"] = scoped.selected_snapshot_37(
            ACCOUNT, bundle[2], lot=LOT, fluid=FLUID,
            start="2026-01-02", end="2026-01-03", serials=["OLD", "NEW"],
        )
        bundle[3]["selection_digest"] = native._hash(dict(bundle[0]))
        p = evaluate(bundle)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("concurrent_physical_generations_not_apportioned", p["blockers"])

    def test_overlapping_physical_lifetimes_inside_selected_period_blocked(self):
        bundle = fixtures()
        moved = datetime(2026, 1, 2, 11, tzinfo=timezone.utc)
        bundle[1]["__physical_meters__"][(LOT, FLUID, "NEW")][
            "reviewed_readings"
        ][0] = (moved, 50)
        bundle[4][0]["lines"][1]["indexes"][0] = {
            "date": moved.isoformat(), "value": 50,
        }
        p = evaluate(bundle)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("selected_generations_observation_spans_overlap",
                      p["blockers"])

    def test_mixed_same_generation_day_requires_separate_l6_contract(self):
        bundle = fixtures()
        bundle[2]["groups"][0]["rows"][1] = {
            "date": "2026-01-03", "consumption": "2.5",
            "contributors": [{
                "serial": "NEW", "provenance": "mixed",
                "consumption": "2.5", "measured": "2",
                "estimated": "0.5",
                "decision_attribution": "day_revision_candidate_unverified",
                "decision_fingerprint": "approved-interval-A",
                "revision_fingerprint": REV,
            }],
        }
        bundle[0]["physical_snapshot_digest"] = scoped.selected_snapshot_37(
            ACCOUNT, bundle[2], lot=LOT, fluid=FLUID,
            start="2026-01-02", end="2026-01-03", serials=["OLD", "NEW"],
        )
        bundle[3]["selection_digest"] = native._hash(dict(bundle[0]))
        p = evaluate(bundle)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("mixed_physical_day_not_representable_in_l6_v2",
                      p["blockers"])

    def test_foreign_recorded_statistic_is_refused(self):
        bundle = fixtures()
        bundle[3]["statistic_id"] = "trybatec:other_account_series"
        p = evaluate(bundle)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("native_36_selected_revision_and_scope_unavailable",
                      p["blockers"])

    def test_duplicate_physical_inventory_is_refused(self):
        bundle = fixtures()
        bundle[2]["inventory"].append(deepcopy(bundle[2]["inventory"][0]))
        p = evaluate(bundle)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("duplicated_or_invalid_source_inventory", p["blockers"])

    def test_stale_selected_snapshot_is_rejected(self):
        bundle = fixtures()
        bundle[2]["groups"][0]["rows"][0]["consumption"] = "7"
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            evaluate(bundle)

    def test_HA_entity_suffix_does_not_define_generation_id(self):
        physical = native.generation_id_37(ACCOUNT, LOT, FLUID, "NEW")
        self.assertEqual(physical, native.generation_id_37(ACCOUNT, LOT, FLUID, "NEW"))
        self.assertNotEqual(physical, native.generation_id_37(ACCOUNT, LOT, FLUID, "NEW_2"))
        self.assertTrue(physical.startswith("trybatec:physical_"))

    def test_native_C11_server_adapter_uses_authenticated_admin_and_source(self):
        selection, raw, preview, proof, payloads = fixtures()
        native_data = {
            "complete": True, "payloads": payloads,
            "coverage_start": "2026-01-01", "coverage_end": "2026-01-04",
        }
        counters = {"store_reads": 0, "c11_reads": 0, "raw_rebuilds": 0}
        modules = {}

        def fake_module(name, **methods):
            module = types.ModuleType(f"{PKG}.{name}")
            for key, fn in methods.items():
                setattr(module, key, fn)
            modules[f"{PKG}.{name}"] = module

        def fake_history(*args, **kwargs):
            counters["raw_rebuilds"] += 1
            self.assertEqual(kwargs["allowed_lots"], {LOT})
            return raw

        async def fake_decisions(*args):
            counters["store_reads"] += 1
            return {}

        def fake_C11(*args, **kwargs):
            counters["c11_reads"] += 1
            self.assertEqual(kwargs["start"].isoformat(), "2026-01-02")
            return native_data

        fake_module("history", build_history=fake_history)
        fake_module("history_store", load_decisions=fake_decisions)
        fake_module("panel_history_coverage", get_source=fake_C11)

        before = {k: sys.modules.get(k) for k in modules}
        sys.modules.update(modules)

        class Auth:
            async def async_get_user(self, actor_id):
                return SimpleNamespace(is_admin=actor_id == "fake-admin")

        hass = SimpleNamespace(auth=Auth())
        coordinator = SimpleNamespace(entry=SimpleNamespace(
            unique_id=ACCOUNT, entry_id="FAKE-ENTRY",
        ))

        async def fake_36(*args):
            return proof

        async def run():
            return await native.async_collect_server_scoped_lineage_37(
                hass, coordinator, actor_id="fake-admin",
                selection=selection, preview_37=preview,
                read_native_recorder_36=fake_36,
                verify_user_selection=approved_user,
                verify_36_day=approved_day,
                verify_36_absence=approved_absence,
            )

        try:
            result = asyncio.run(run())
            self.assertTrue(result["selected_scope_reconciled"], result["blockers"])
            self.assertEqual(counters, {
                "store_reads": 1, "c11_reads": 1, "raw_rebuilds": 1,
            })
            self.assertFalse(result["writes"])

            async def denied():
                return await native.async_collect_server_scoped_lineage_37(
                    hass, coordinator, actor_id="not-admin",
                    selection=selection, preview_37=preview,
                )

            with self.assertRaises(PermissionError):
                asyncio.run(denied())
            self.assertEqual(counters["store_reads"], 1)

            async def no_recorder():
                return await native.async_collect_server_scoped_lineage_37(
                    hass, coordinator, actor_id="fake-admin",
                    selection=selection, preview_37=preview,
                    verify_user_selection=approved_user,
                    verify_36_day=approved_day,
                    verify_36_absence=approved_absence,
                )
            blocked = asyncio.run(no_recorder())
            self.assertFalse(blocked["selected_scope_reconciled"])
            self.assertIn("native_36_selected_revision_and_scope_unavailable",
                          blocked["blockers"])
        finally:
            for key, original in before.items():
                if original is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = original

    def test_no_callbacks_is_never_an_native_attestation(self):
        p = evaluate(fixtures(), verify_user_selection=None,
                     verify_36_day=None, verify_36_absence=None)
        self.assertFalse(p["selected_scope_reconciled"])
        self.assertIn("trusted_native_decision_verifiers_unavailable", p["blockers"])


if __name__ == "__main__":
    unittest.main()
