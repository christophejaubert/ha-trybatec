"""Synthetic non-destructive #37/#81 lineage/identity regressions (FR/EN)."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec"
PKG = "lineage37_identity_audit_isolated"
package = types.ModuleType(PKG)
package.__path__ = [str(ROOT)]
sys.modules.setdefault(PKG, package)


def load(name):
    qualified = f"{PKG}.{name}"
    spec = importlib.util.spec_from_file_location(qualified, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


meter = load("meter_lineage_37")
bridge = load("lineage_history_bridge_37")
handoff = load("lineage_energy_handoff_37")
identity = load("meter_identity")

DAY = date(2026, 1, 2)
NEXT = date(2026, 1, 3)
SCOPE = ("TEST-LOT", "EF", "SERIAL-X")


def readings(start=100, end=102):
    return {
        "lot": SCOPE[0], "fluid": SCOPE[1], "serial": SCOPE[2],
        "retired": True, "source_fingerprint": "f" * 64,
        "reviewed_readings": [
            (datetime(2026, 1, 1, tzinfo=timezone.utc), start),
            (datetime(2026, 1, 4, tzinfo=timezone.utc), end),
        ], "decreases": 0, "conflicts": 0,
    }


def variant(raw=None, smooth=None, decisions=None, per_day=None):
    value = {
        "lot": SCOPE[0], "fluid": SCOPE[1], "serial": SCOPE[2],
        "source_fingerprint": "f" * 64,
        "status": "preview_only", "normalized_unit": "m³",
        "selected_gap_fingerprints": decisions if decisions is not None else [],
        "raw": raw if raw is not None else {DAY: 1},
        "smoothed": smooth if smooth is not None else {DAY: 1},
    }
    if per_day is not None:
        value["day_decision_fingerprints"] = per_day
    return value


def prepare(source=None, candidate=None):
    return bridge.prepare_physical_continuity_37(
        "TEST-ACCOUNT", {"__physical_meters__": {SCOPE: source or readings()}},
        {"meters": [candidate or variant()]},
    )


def registration(uid, entity="sensor.test_meter_2"):
    return {
        "entity_id": entity,
        "unique_id": uid,
        "platform": "trybatec",
        "config_entry_id": "TEST-ENTRY",
    }


class PerDayEvidenceTests(unittest.TestCase):
    def test_exact_day_reference_survives_lineage_and_handoff(self):
        p = prepare(candidate=variant(
            smooth={DAY: 1.5}, decisions=["decision-X"],
            per_day={DAY: "decision-X"},
        ))
        group = p["groups"][0]
        contributor = group["rows"][0]["contributors"][0]
        self.assertEqual(contributor["decision_fingerprint"], "decision-X")
        self.assertEqual(contributor["decision_attribution"], "day_candidate_unverified")
        self.assertEqual(contributor["measured"], "1")
        self.assertEqual(contributor["estimated"], "0.5")
        envelope = handoff.prepare_energy_lineage_handoff_37(p)
        qualified = envelope["groups"][0]
        self.assertEqual(qualified["historical_qualification"], "partiel")
        self.assertIn("day_decision_requires_independent_36_match", qualified["blockers"])
        self.assertFalse(qualified["day_decisions_independently_verified"])
        self.assertFalse(envelope["energy_activation_authorized"])

    def test_pooled_approvals_cannot_be_misrepresented_as_per_day(self):
        p = prepare(candidate=variant(
            smooth={DAY: 1.5}, decisions=["decision-X", "decision-Y"]
        ))
        group = p["groups"][0]
        self.assertIn("estimated_day_decision_not_individually_attributed", group["blockers"])
        contributor = group["rows"][0]["contributors"][0]
        self.assertEqual(contributor["decision_attribution"], "approval_set_unattributed")
        evidence = handoff.prepare_energy_lineage_handoff_37(p)
        self.assertIn(
            "estimated_day_decision_not_individually_attributed",
            evidence["groups"][0]["blockers"],
        )

    def test_day_reference_must_match_approved_set(self):
        with self.assertRaisesRegex(ValueError, "per-day decision"):
            prepare(candidate=variant(
                smooth={DAY: 1.5}, decisions=["decision-X"],
                per_day={DAY: "unrelated"},
            ))

    def test_unused_day_approval_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "without matching positive estimate"):
            prepare(candidate=variant(
                smooth={DAY: 1.5}, decisions=["decision-X"],
                per_day={NEXT: "decision-X"},
            ))

    def test_raw_index_decrease_detected_without_metadata_flag(self):
        outcome = prepare(source=readings(102, 100))
        self.assertEqual(outcome["groups"][0]["rows"], [])
        self.assertEqual(outcome["groups"][0]["historical_evidence_qualification"], "inconnu")
        self.assertIn("unresolved_physical_source_anomaly", outcome["groups"][0]["blockers"])

    def test_daily_amount_outside_observed_period_is_not_accepted(self):
        p = prepare(candidate=variant(
            raw={date(2026, 1, 8): 1},
            smooth={date(2026, 1, 8): 1},
        ))
        group = p["groups"][0]
        self.assertEqual(group["rows"], [])
        self.assertIn("consumption_outside_observed_period", group["blockers"])
        self.assertEqual(group["historical_evidence_qualification"], "contradictoire")

    def test_forged_mixed_quantities_rejected_at_energy_boundary(self):
        p = prepare(candidate=variant(
            smooth={DAY: 2}, decisions=["decision-X"],
            per_day={DAY: "decision-X"},
        ))
        changed = deepcopy(p)
        changed["groups"][0]["rows"][0]["contributors"][0]["estimated"] = "999"
        with self.assertRaisesRegex(ValueError, "do not reconcile"):
            handoff.prepare_energy_lineage_handoff_37(changed)

    def test_read_only_output_without_any_runtime_mutation(self):
        p = prepare()
        evidence = handoff.prepare_energy_lineage_handoff_37(p)
        self.assertIs(p["writes"], False)
        self.assertIs(evidence["writes"], False)
        self.assertIs(evidence["physical_inventory_complete"], False)
        self.assertIs(evidence["recorder_persistence_verified"], False)


class StableEntityIdentityAuditTests(unittest.TestCase):
    def _meters(self):
        return [{"lot": SCOPE[0], "fluid": SCOPE[1], "serial": SCOPE[2]}]

    def _stable(self):
        return identity.stable_meter_unique_id("TEST-ACCOUNT", *SCOPE)

    def test_suffix_not_a_physical_meter_generation(self):
        observed = handoff.audit_ha_identity_references_37(
            "TEST-ACCOUNT", "TEST-ENTRY", self._meters(),
            [registration(self._stable())],
            [{"consumer": "dashboard", "kind": "entity_id",
              "reference": "sensor.test_meter_2"}],
        )
        self.assertEqual(len(observed["identity_plan_81"]["meters"]), 1)
        self.assertEqual(observed["identity_plan_81"]["meters"][0]["status"],
                         "stable_registered")
        self.assertFalse(observed["suffixed_entity_id_is_physical_meter_evidence"])
        self.assertFalse(observed["safe_to_delete_legacy_entity"])
        self.assertFalse(observed["safe_to_migrate"])

    def test_stable_and_legacy_coexistence_blocks_migration(self):
        old = next(iter(sorted(identity.legacy_meter_unique_ids(
            "TEST-ACCOUNT", *SCOPE, allow_unscoped_serial=True,
        ))))
        outcome = handoff.audit_ha_identity_references_37(
            "TEST-ACCOUNT", "TEST-ENTRY", self._meters(),
            [registration(self._stable()), registration(old, "sensor.test_meter")],
        )
        self.assertEqual(outcome["status"], "contradictoire")
        self.assertIn(
            "stable_and_legacy_coexist",
            outcome["identity_plan_81"]["meters"][0]["blockers"],
        )

    def test_unknown_external_entity_reference_is_an_unresolved_audit(self):
        p = handoff.audit_ha_identity_references_37(
            "TEST-ACCOUNT", "TEST-ENTRY", self._meters(),
            [registration(self._stable())],
            [{"consumer": "automation", "kind": "entity_id",
              "reference": "sensor.unknown_legacy"}],
        )
        self.assertEqual(p["status"], "contradictoire")
        self.assertEqual(len(p["unresolved_consumer_entity_references"]), 1)
        self.assertFalse(p["consumer_inventory_exhaustive"])

    def test_recorder_statistic_reference_never_claims_exhaustiveness(self):
        p = handoff.audit_ha_identity_references_37(
            "TEST-ACCOUNT", "TEST-ENTRY", self._meters(),
            [registration(self._stable())],
            [{"consumer": "recorder", "kind": "statistic_id",
              "reference": "trybatec:legacy_synthetic"}],
        )
        self.assertIsNone(p["observed_consumers"][0]["entity_registry_match"])
        self.assertFalse(p["recorder_statistic_references_exhaustive"])

    def test_duplicate_registry_identity_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Duplicated registry identity"):
            handoff.audit_ha_identity_references_37(
                "TEST-ACCOUNT", "TEST-ENTRY", self._meters(),
                [registration(self._stable()),
                 registration(self._stable(), "sensor.other")],
            )


if __name__ == "__main__":
    unittest.main()
