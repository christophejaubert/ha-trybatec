"""#37/#36 synthetic native-attempt comparison; never accesses Home Assistant."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec"
PKG = "lineage37_recorder_attempt_isolated"
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


load("lineage_selected_scope_37")
native = load("lineage_native_scoped_37")
ACCOUNT, LOT, FLUID = "SYNTHETIC", "LOT-FAKE", "EF"
LOGICAL = "trybatec:logical_" + "1" * 32
STAT = LOGICAL + "_v2_a1_" + "2" * 32
ROWS_HASH = "3" * 64
REV = "4" * 64


def fixture():
    choice = {
        "account": ACCOUNT, "lot": LOT, "fluid": FLUID,
        "start": "2026-01-02", "end": "2026-01-03",
        "statistic_id": STAT, "serials": ["RETIRED", "ACTIVE"],
        "generation_ids": ["RETIRED", "ACTIVE"],
        "accepted_missing_days": [], "rows_hash": ROWS_HASH,
    }
    physical = [
        {"date": "2026-01-02", "consumption": "1",
         "contributors": [{"serial": "RETIRED", "consumption": "1",
                           "provenance": "measured"}]},
        {"date": "2026-01-03", "consumption": "2",
         "contributors": [{"serial": "ACTIVE", "consumption": "2",
                           "provenance": "measured"}]},
    ]
    original = [
        {"date": "2026-01-02", "measured": "1", "estimated": "0",
         "total": "1", "contributions": [
             {"serial": "RETIRED", "measured": "1", "estimated": "0",
              "decision_refs": []}]},
        {"date": "2026-01-03", "measured": "2", "estimated": "0",
         "total": "2", "contributions": [
             {"serial": "ACTIVE", "measured": "2", "estimated": "0",
              "decision_refs": []}]},
    ]
    proof = {
        "schema": "history_36_native_attempt_proof_v1",
        "status": "observed_persisted_exactly",
        "mode": "native_scoped_readback_not_global_fencing",
        "statistic_id": STAT, "logical_id": LOGICAL, "revision": 2, "attempt": 1,
        "scope": {"lot": LOT, "fluid": FLUID, "kind": "consolidated",
                  "serial": None, "variant": "selected_physical_consumption"},
        "unit": "m³", "snapshot_hash": ROWS_HASH,
        "journal_disk_verified": True,
        "scoped_recorder_persistence_verified": True,
        "recorder_sql_metadata_readback_verified": True,
        "recorder_sql_snapshot_hash_verified": True,
        "scoped_double_readback_observed": True,
        "native_decision_store_crosscheck_verified": True,
        "daily_approval_refs": original,
        "independent_future_writer_exclusion_verified": False,
        "energy_exclusivity_verified": False,
        "quarantined_or_uncertain_attempt_ids": [],
    }
    return choice, physical, proof


def evaluate(bundle):
    return native.audit_native_attempt_link_37(*bundle)


class NativeRecorderLink37Tests(unittest.TestCase):
    def test_successive_meters_match_separately_without_an_energy_permit(self):
        result = evaluate(fixture())
        self.assertEqual(result["selected_days_compared"], 2)
        self.assertTrue(result["native_sql_observed"])
        self.assertNotIn("native_attempt_physical_amount_mismatch", result["blockers"])
        self.assertIn("native_36_scoped_selection_v2_not_issued", result["blockers"])
        self.assertIn("native_attempt_future_writer_exclusion_unverified", result["blockers"])
        self.assertFalse(result["eligible_for_l6"])
        self.assertFalse(result["writes"])

    def test_native_v1_never_promoted_even_when_flags_claim_positive(self):
        bundle = fixture()
        bundle[2]["independent_future_writer_exclusion_verified"] = True
        bundle[2]["energy_exclusivity_verified"] = True
        result = evaluate(bundle)
        self.assertIn("native_36_scoped_selection_v2_not_issued", result["blockers"])
        self.assertFalse(result["history_36_scoped_selection_v2_issued"])
        self.assertFalse(result["energy_activation_authorized"])

    def test_stale_statistic_or_revision_is_rejected(self):
        for field, value, expected in (
            ("statistic_id", "trybatec:other", "native_attempt_statistic_or_physical_scope_mismatch"),
            ("revision", 1, "native_attempt_exact_revision_or_nonce_mismatch"),
            ("snapshot_hash", "9" * 64, "native_attempt_persisted_rows_hash_mismatch"),
        ):
            with self.subTest(field=field):
                bundle = fixture()
                bundle[2][field] = value
                self.assertIn(expected, evaluate(bundle)["blockers"])

    def test_cross_generation_redistribution_is_detected(self):
        bundle = fixture()
        bundle[2]["daily_approval_refs"][1]["contributions"][0]["serial"] = "RETIRED"
        result = evaluate(bundle)
        self.assertIn("native_attempt_physical_generation_mismatch", result["blockers"])

    def test_consolidated_total_mismatch_is_detected(self):
        bundle = fixture()
        bundle[2]["daily_approval_refs"][1]["total"] = "200"
        result = evaluate(bundle)
        self.assertIn("native_attempt_consolidation_or_daily_total_mismatch", result["blockers"])

    def test_duplicate_recorder_day_is_detected(self):
        bundle = fixture()
        bundle[2]["daily_approval_refs"].append(
            deepcopy(bundle[2]["daily_approval_refs"][1])
        )
        self.assertIn("recorder_day_duplicate", evaluate(bundle)["blockers"])

    def test_missing_day_stays_absent_but_lacks_native_v1_approval(self):
        bundle = fixture()
        bundle[1].pop()
        bundle[2]["daily_approval_refs"].pop()
        bundle[0]["accepted_missing_days"] = ["2026-01-03"]
        result = evaluate(bundle)
        self.assertIn(
            "native_attempt_accepted_missing_day_receipts_unavailable",
            result["blockers"],
        )

    def test_estimated_day_needs_same_exact_decision_revision(self):
        bundle = fixture()
        source = bundle[1][1]["contributors"][0]
        source.update({
            "provenance": "estimated_linear_confirmed",
            "decision_attribution": "day_revision_candidate_unverified",
            "decision_fingerprint": "SYNTHETIC-APPROVAL-REF",
            "revision_fingerprint": REV,
        })
        second = bundle[2]["daily_approval_refs"][1]
        second["measured"], second["estimated"] = "0", "2"
        second["contributions"][0].update({
            "measured": "0", "estimated": "2",
            "decision_refs": [{
                "reference": "SYNTHETIC-APPROVAL-REF",
                "decision_fingerprint": REV,
                "updated_at": "2026-01-03T10:00:00+00:00",
            }],
        })
        result = evaluate(bundle)
        self.assertNotIn("native_attempt_day_revision_not_cross_attested", result["blockers"])
        stale = deepcopy(bundle)
        stale[2]["daily_approval_refs"][1]["contributions"][0]["decision_refs"][0][
            "decision_fingerprint"
        ] = "f" * 64
        self.assertIn("native_attempt_day_revision_not_cross_attested",
                      evaluate(stale)["blockers"])

    def test_estimate_cannot_be_relabelled_as_vendor_measurement(self):
        bundle = fixture()
        bundle[2]["daily_approval_refs"][1]["estimated"] = "2"
        bundle[2]["daily_approval_refs"][1]["measured"] = "0"
        bundle[2]["daily_approval_refs"][1]["contributions"][0][
            "estimated"
        ] = "2"
        bundle[2]["daily_approval_refs"][1]["contributions"][0][
            "measured"
        ] = "0"
        self.assertIn("native_attempt_provenance_relabelled", evaluate(bundle)["blockers"])

    def test_unsupported_or_missing_native_receipt_is_not_positive(self):
        bundle = fixture()
        bundle[2]["schema"] = "history_36_scoped_selection_v2"
        result = evaluate(bundle)
        self.assertIn("native_36_scoped_selection_v2_not_issued", result["blockers"])
        self.assertIn("native_36_attempt_schema_mismatch", result["blockers"])

    def test_unselected_physical_period_not_required_for_v1_comparison(self):
        bundle = fixture()
        bundle[1].insert(0, {
            "date": "2025-12-01", "consumption": "999",
            "contributors": [{"serial": "RETIRED", "consumption": "999",
                              "provenance": "measured"}],
        })
        result = evaluate(bundle)
        self.assertEqual(result["selected_days_compared"], 2)
        self.assertNotIn("native_attempt_selected_day_set_mismatch",
                         result["blockers"])

    def test_native_recorder_day_outside_selected_scope_is_rejected(self):
        bundle = fixture()
        row = deepcopy(bundle[2]["daily_approval_refs"][0])
        row["date"] = "2026-01-04"
        bundle[2]["daily_approval_refs"].append(row)
        result = evaluate(bundle)
        self.assertIn("native_attempt_recorder_day_outside_selection",
                      result["blockers"])



if __name__ == "__main__":
    unittest.main()
