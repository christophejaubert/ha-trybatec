"""FR/EN: synthetic #37 exact-day revisions, inventory and Energy overlap."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec"
PKG = "lineage37_extended_evidence_isolated"
pkg = types.ModuleType(PKG)
pkg.__path__ = [str(ROOT)]
sys.modules.setdefault(PKG, pkg)


def load(name):
    target = f"{PKG}.{name}"
    spec = importlib.util.spec_from_file_location(target, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[target] = module
    spec.loader.exec_module(module)
    return module


load("meter_lineage_37")
bridge = load("lineage_history_bridge_37")
handoff = load("lineage_energy_handoff_37")
FIRST = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
DAY = date(2026, 1, 2)
REF = "interval-example"
REV = "a" * 64
FINGERPRINT = "f" * 64


def source(serial="A", *, fluid="EF", start=0, span=2, retired=False):
    first = FIRST + timedelta(days=start)
    return {
        "lot": "LOT-EXAMPLE", "fluid": fluid, "serial": serial,
        "retired": retired, "source_fingerprint": FINGERPRINT,
        "reviewed_readings": [
            (first, 10), (first + timedelta(days=span), 11),
        ], "decreases": 0, "conflicts": 0,
    }


def variant(m, *, raw=None, smoothed=None, decision=None):
    first = m["reviewed_readings"][0][0].date()
    point = first + timedelta(days=1)
    raw = raw if raw is not None else {point: 1}
    smoothed = smoothed if smoothed is not None else dict(raw)
    value = {
        "lot": m["lot"], "fluid": m["fluid"], "serial": m["serial"],
        "normalized_unit": "kWh" if m["fluid"] == "CET" else "m³",
        "source_fingerprint": m["source_fingerprint"],
        "status": "preview_only",
        "selected_gap_fingerprints": [REF] if decision is not None else [],
        "raw": raw, "smoothed": smoothed,
    }
    if decision is not None:
        value["decision_daily_allocations"] = {REF: decision}
    return value


def approval(m, *, amount="0.5", revision=REV, ref_source=FINGERPRINT, day=DAY):
    return {
        "lot": m["lot"], "fluid": m["fluid"], "serial": m["serial"],
        "source_fingerprint": ref_source, "revision_fingerprint": revision,
        "daily_estimated": {day: amount},
    }


def run(meters, variants=None, **options):
    return bridge.prepare_physical_continuity_37(
        "ACCOUNT-EXAMPLE",
        {"__physical_meters__": {
            (m["lot"], m["fluid"], m["serial"]): m for m in meters
        }},
        {"meters": variants if variants is not None else [variant(m) for m in meters]},
        **options,
    )


def catalog(m, *, count=2, fp=FINGERPRINT):
    first, last = m["reviewed_readings"][0][0], m["reviewed_readings"][-1][0]
    return {
        "lot": m["lot"], "fluid": m["fluid"], "serial": m["serial"],
        "observation_count": count, "source_fingerprint": fp,
        "first_observed_at": first.isoformat(),
        "last_observed_at": last.isoformat(),
    }


class DailyRevision37Tests(unittest.TestCase):
    def test_exact_revision_bound_allocation_is_preserved_but_not_certified(self):
        m = source()
        v = variant(m, smoothed={DAY: 1.5}, decision=approval(m))
        proof = run([m], [v])
        item = proof["groups"][0]["rows"][0]["contributors"][0]
        self.assertEqual(item["decision_fingerprint"], REF)
        self.assertEqual(item["revision_fingerprint"], REV)
        self.assertEqual(item["estimated"], "0.5")
        self.assertEqual(item["measured"], "1")
        self.assertEqual(item["decision_attribution"], "day_revision_candidate_unverified")
        forwarded = handoff.prepare_energy_lineage_handoff_37(proof)["groups"][0]
        self.assertIn("day_revision_requires_independent_36_match", forwarded["blockers"])
        self.assertEqual(forwarded["daily_consumption"][0]["contributors"][0]["revision_fingerprint"], REV)
        self.assertFalse(forwarded["day_decisions_independently_verified"])

    def test_revision_allocation_wrong_amount_rejected(self):
        m = source()
        with self.assertRaisesRegex(ValueError, "disagrees with revision"):
            run([m], [variant(m, smoothed={DAY: 1.5}, decision=approval(m, amount="0.6"))])

    def test_wrong_meter_or_source_cannot_reuse_revision(self):
        m = source()
        with self.assertRaisesRegex(ValueError, "physical source mismatch"):
            run([m], [variant(m, smoothed={DAY: 1.5}, decision=approval(m, ref_source="b" * 64))])

    def test_missing_revision_rejected_without_inferring_approval(self):
        m = source()
        with self.assertRaisesRegex(ValueError, "revision or physical source mismatch"):
            run([m], [variant(m, smoothed={DAY: 1.5}, decision=approval(m, revision="bad"))])

    def test_extra_allocation_outside_actual_estimation_rejected(self):
        m = source()
        with self.assertRaisesRegex(ValueError, "without matching positive estimate"):
            run([m], [variant(m, smoothed={DAY: 1.5}, decision=approval(m, day=date(2026, 1, 3)))])

    def test_global_unattributed_approval_not_promoted(self):
        m = source()
        v = variant(m, smoothed={DAY: 1.5})
        v["selected_gap_fingerprints"] = ["global-only"]
        out = run([m], [v])
        item = out["groups"][0]["rows"][0]["contributors"][0]
        self.assertEqual(item["decision_attribution"], "approval_set_unattributed")
        self.assertNotIn("revision_fingerprint", item)
        self.assertIn("estimated_day_decision_not_individually_attributed",
                      out["groups"][0]["blockers"])

    def test_overlapping_decisions_on_same_day_rejected(self):
        m = source()
        v = variant(m, smoothed={DAY: 1.5}, decision=approval(m))
        v["selected_gap_fingerprints"].append("other-interval")
        v["decision_daily_allocations"]["other-interval"] = approval(m)
        with self.assertRaisesRegex(ValueError, "Overlapping or noncanonical"):
            run([m], [v])

    def test_forged_revision_after_handoff_is_rejected(self):
        m = source()
        proof = run([m], [variant(m, smoothed={DAY: 1.5}, decision=approval(m))])
        altered = deepcopy(proof)
        altered["groups"][0]["rows"][0]["contributors"][0]["revision_fingerprint"] = "bad"
        with self.assertRaisesRegex(ValueError, "exact revision"):
            handoff.prepare_energy_lineage_handoff_37(altered)


class CatalogReconciliation37Tests(unittest.TestCase):
    def test_matching_requested_interval_is_not_historical_exhaustiveness(self):
        m = source()
        proof = run([m], observed_catalog=[catalog(m)],
                    supplier_discovery={"status": "complete"})
        audit = proof["inventory_reconciliation"]
        self.assertEqual(audit["status"], "partiel")
        self.assertEqual(audit["catalog_rows_matching_observed_source"], 1)
        self.assertFalse(audit["historical_account_exhaustiveness_verified"])
        forward = handoff.prepare_energy_lineage_handoff_37(proof)["groups"][0]
        self.assertIn("historical_account_exhaustiveness_not_attested", forward["blockers"])
        self.assertNotIn("account_historical_discovery_not_complete", forward["blockers"])

    def test_retired_meter_only_in_catalog_blocks_complete_group(self):
        a, retired = source(), source("OLD", start=-5, retired=True)
        proof = run([a], observed_catalog=[catalog(a), catalog(retired)])
        self.assertEqual(proof["meter_count"], 2)
        self.assertEqual(proof["groups"][0]["rows"], [])
        self.assertEqual(proof["groups"][0]["status"], "blocked_incomplete_physical_series")
        self.assertIn("catalog_meter_missing_from_history", proof["groups"][0]["blockers"])
        self.assertIsNone(proof["groups"][0]["total"])
        self.assertFalse(proof["historical_inventory_proven_complete"])

    def test_wrong_source_fingerprint_is_contradictory(self):
        m = source()
        proof = run([m], observed_catalog=[catalog(m, fp="b" * 64)])
        self.assertEqual(proof["inventory_reconciliation"]["status"], "contradictoire")
        self.assertEqual(proof["groups"][0]["rows"], [])
        self.assertIn("catalog_physical_source_fingerprint_mismatch",
                      proof["groups"][0]["blockers"])

    def test_observation_count_mismatch_is_contradictory(self):
        m = source()
        proof = run([m], observed_catalog=[catalog(m, count=9)])
        self.assertEqual(proof["inventory_reconciliation"]["status"], "contradictoire")
        self.assertIn("catalog_observation_count_mismatch", proof["groups"][0]["blockers"])

    def test_missing_catalog_meter_is_not_proof_of_absence(self):
        a, b = source(), source("B", start=7)
        proof = run([a, b], observed_catalog=[catalog(a)])
        self.assertEqual(proof["inventory_reconciliation"]["status"], "partiel")
        self.assertIn("observed_meter_absent_from_supplied_catalog",
                      [r["reason"] for r in proof["inventory_reconciliation"]["differences"]])
        self.assertFalse(proof["inventory_reconciliation"]["historical_account_exhaustiveness_verified"])

    def test_sparse_observation_gaps_remain_unknown_without_interpolation(self):
        m = source(span=40)
        result = run([m])
        entry = result["inventory"][0]
        self.assertEqual(entry["unknown_observation_spans_count"], 1)
        self.assertEqual(entry["unknown_observation_spans"][0]["consumption"], None)
        self.assertFalse(entry["unknown_observation_spans"][0]["service_transition_proven"])
        self.assertEqual(result["groups"][0]["physical_meters"][0]["service_end"], None)
        hand = handoff.prepare_energy_lineage_handoff_37(result)["groups"][0]
        self.assertEqual(hand["source_observation_gap_intervals"], 1)

    def test_two_generations_stay_distinct_with_unknown_replacement(self):
        a, b = source("OLD", retired=True), source("NEW", start=10)
        proof = run([a, b])
        group = proof["groups"][0]
        self.assertEqual(group["total"], "2")
        self.assertEqual(group["physical_meters"][0]["service_end"], None)
        self.assertEqual(group["physical_meters"][1]["service_start"], None)
        self.assertEqual(len(group["unobserved_intervals"]), 1)
        self.assertEqual(group["unobserved_intervals"][0]["consumption"], None)

    def test_cross_fluid_statistics_are_never_shared(self):
        a, b = source("A", fluid="EF"), source("B", fluid="ECS")
        proof = run([a, b])
        report = handoff.prepare_energy_lineage_handoff_37(
            proof,
            known_statistic_versions={
                ("LOT-EXAMPLE", "EF"): ["trybatec:reused-stat"],
                ("LOT-EXAMPLE", "ECS"): ["trybatec:reused-stat"],
            },
            selected_energy_sources={
                ("LOT-EXAMPLE", "EF"): ["trybatec:reused-stat"],
                ("LOT-EXAMPLE", "ECS"): ["trybatec:reused-stat"],
            },
        )
        for group in report["groups"]:
            self.assertIn("statistic_id_reused_across_logical_scopes", group["blockers"])
            self.assertIn("energy_selection_reused_across_logical_scopes", group["blockers"])
            self.assertFalse(group["energy_version_exclusivity_proven"])

    def test_discovery_interrupted_does_not_attest_full_account(self):
        m = source()
        report = handoff.prepare_energy_lineage_handoff_37(
            run([m], observed_catalog=[catalog(m)],
                supplier_discovery={"status": "interrupted"}),
        )
        self.assertIn("account_historical_discovery_not_complete",
                      report["groups"][0]["blockers"])
        self.assertFalse(report["physical_inventory_complete"])


if __name__ == "__main__":
    unittest.main()
