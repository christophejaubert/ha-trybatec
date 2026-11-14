"""Synthetic #37 bounded user-review proofs; no Home Assistant or provider access."""
from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec"
PKG = "lineage37_selected_scope_isolated"
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


scope = load("lineage_selected_scope_37")
ACCOUNT = "FAKE-ACCOUNT-ONLY"
LOT, FLUID = "FAKE-LOT", "EF"


def meter(serial):
    return {
        "lot": LOT, "fluid": FLUID, "serial": serial,
        "source_fingerprint": ("a" if serial == "OLD" else "b") * 64,
        "status": "depose" if serial == "OLD" else "en_service",
        "service_start": None, "service_end": None,
    }


def measured(serial, day, amount="1"):
    return {
        "date": day, "consumption": amount,
        "contributors": [{
            "serial": serial, "provenance": "measured", "consumption": amount,
        }],
    }


def estimate(serial="NEW", *, decision="decision-revision-A", revision="c" * 64):
    return {
        "date": "2026-01-03", "consumption": "1.5",
        "contributors": [{
            "serial": serial, "provenance": "mixed", "consumption": "1.5",
            "measured": "1", "estimated": "0.5",
            "decision_fingerprint": decision,
            "revision_fingerprint": revision,
            "decision_attribution": "day_revision_candidate_unverified",
        }],
    }


def preview(rows=None, blockers=None):
    return {
        "mode": "read_only_37_history_bridge",
        "writes": False, "energy_activation_authorized": False,
        "historical_inventory_proven_complete": False,
        "inventory": [meter("OLD"), meter("NEW")],
        "groups": [{
            "lot": LOT, "fluid": FLUID, "unit": "m³",
            "blockers": blockers or [],
            "rows": rows if rows is not None else [
                measured("OLD", "2026-01-01"),
                measured("NEW", "2026-01-03"),
            ],
        }],
    }


def request(p, *, start="2026-01-01", end="2026-01-03",
            serials=None, gaps=None):
    serials = serials or ["OLD", "NEW"]
    return {
        "lot": LOT, "fluid": FLUID, "start": start, "end": end,
        "serials": serials,
        "expected_snapshot_fingerprint": scope.selected_snapshot_37(
            ACCOUNT, p, lot=LOT, fluid=FLUID, start=start, end=end,
            serials=serials,
        ),
        "decision_reference": "synthetic-user-review-001",
        "accepted_missing_days": gaps if gaps is not None else ["2026-01-02"],
    }


def verify_user(record):
    return record["decision_reference"] == "synthetic-user-review-001"


def verify_36(record):
    return (
        record["date"] == "2026-01-03"
        and record["serial"] == "NEW"
        and record["revision_fingerprint"] == "c" * 64
        and record["estimated"] == "0.5"
        and record["source_fingerprint"] == "b" * 64
    )


class ScopedBusinessAcceptanceTests(unittest.TestCase):
    def test_known_replacement_without_date_inference_and_gap_accepted(self):
        p = preview()
        result = scope.assess_selected_scope_37(
            ACCOUNT, p, [request(p)], verify_user_approval=verify_user,
        )
        q = result["periods"][0]
        self.assertEqual(q["qualification"], "partielle")
        self.assertEqual(q["accepted_missing_days"], ["2026-01-02"])
        self.assertEqual(q["unaccepted_missing_days"], [])
        self.assertTrue(q["candidate_for_independent_88_admission_review"])
        self.assertEqual(q["api_trybatec_attestation"], "non_atteste_par_api_trybatec")
        self.assertFalse(q["bounded_period_continuity_proven"])
        self.assertFalse(result["global_history_exhaustiveness_proven"])
        self.assertFalse(result["energy_activation_authorized"])
        self.assertFalse(result["writes"])
        self.assertIsNone(p["inventory"][0]["service_end"])
        self.assertIsNone(p["inventory"][1]["service_start"])

    def test_user_decision_without_independent_authentication_is_refused(self):
        p = preview()
        q = scope.assess_selected_scope_37(ACCOUNT, p, [request(p)])["periods"][0]
        self.assertFalse(q["candidate_for_independent_88_admission_review"])
        self.assertIn("user_approval_not_independently_authenticated", q["blockers"])

    def test_unaccepted_missing_day_is_refused_not_zero_filled(self):
        p = preview()
        q = scope.assess_selected_scope_37(
            ACCOUNT, p, [request(p, gaps=[])],
            verify_user_approval=verify_user,
        )["periods"][0]
        self.assertIn("2026-01-02", q["unaccepted_missing_days"])
        self.assertFalse(q["candidate_for_independent_88_admission_review"])

    def test_accepted_gap_cannot_overlap_daily_contribution(self):
        p = preview()
        with self.assertRaisesRegex(ValueError, "overlaps observed"):
            scope.assess_selected_scope_37(
                ACCOUNT, p, [request(p, gaps=["2026-01-01"])],
                verify_user_approval=verify_user,
            )

    def test_global_approval_without_exact_revision_not_promoted(self):
        p = preview([measured("OLD", "2026-01-01"), estimate(revision="invalid")])
        q = scope.assess_selected_scope_37(
            ACCOUNT, p, [request(p)],
            verify_user_approval=verify_user,
            verify_daily_decision_36=verify_36,
        )["periods"][0]
        self.assertFalse(q["candidate_for_independent_88_admission_review"])
        self.assertIn("estimated_day_without_exact_revision", q["blockers"])

    def test_estimate_verified_exact_day_revision_in_scoped_candidate(self):
        p = preview([measured("OLD", "2026-01-01"), estimate()])
        q = scope.assess_selected_scope_37(
            ACCOUNT, p, [request(p)],
            verify_user_approval=verify_user,
            verify_daily_decision_36=verify_36,
        )["periods"][0]
        self.assertTrue(q["candidate_for_independent_88_admission_review"])
        self.assertEqual(q["estimated_contributors"], 1)
        self.assertEqual(q["exact_day_revision_matches_from_supplied_verifier"], 1)
        self.assertEqual(q["api_trybatec_attestation"], "non_atteste_par_api_trybatec")

    def test_mismatched_36_revision_is_contradiction(self):
        p = preview([measured("OLD", "2026-01-01"), estimate(decision="forged")])
        q = scope.assess_selected_scope_37(
            ACCOUNT, p, [request(p)],
            verify_user_approval=verify_user,
            verify_daily_decision_36=lambda _: False,
        )["periods"][0]
        self.assertEqual(q["qualification"], "contradictoire")
        self.assertIn("36_day_or_revision_mismatch", q["blockers"])

    def test_double_counting_across_generations_is_not_user_waivable(self):
        p = preview([{
            "date": "2026-01-01", "consumption": "2",
            "contributors": [
                measured("OLD", "2026-01-01")["contributors"][0],
                measured("NEW", "2026-01-01")["contributors"][0],
            ],
        }, measured("NEW", "2026-01-03")])
        q = scope.assess_selected_scope_37(
            ACCOUNT, p, [request(p)],
            verify_user_approval=verify_user,
        )["periods"][0]
        self.assertTrue(q["double_count_risk"])
        self.assertFalse(q["candidate_for_independent_88_admission_review"])
        self.assertEqual(q["qualification"], "contradictoire")

    def test_unknown_meter_provenance_cannot_be_accepted_by_user(self):
        p = preview([measured("OLD", "2026-01-01"), measured("NEW", "2026-01-03")])
        p["groups"][0]["rows"][0]["contributors"][0]["serial"] = "FORGED"
        q = scope.assess_selected_scope_37(
            ACCOUNT, p, [request(p)],
            verify_user_approval=verify_user,
        )["periods"][0]
        self.assertTrue(q["provenance_unknown"])
        self.assertFalse(q["candidate_for_independent_88_admission_review"])

    def test_stale_source_review_rejected(self):
        p = preview()
        decision = request(p)
        altered = deepcopy(p)
        altered["groups"][0]["rows"][1]["consumption"] = "7"
        with self.assertRaisesRegex(ValueError, "Stale selected"):
            scope.assess_selected_scope_37(
                ACCOUNT, altered, [decision], verify_user_approval=verify_user,
            )

    def test_contradictory_source_not_waived_by_user(self):
        p = preview(blockers=["unresolved_physical_source_anomaly"])
        q = scope.assess_selected_scope_37(
            ACCOUNT, p, [request(p)], verify_user_approval=verify_user,
        )["periods"][0]
        self.assertEqual(q["qualification"], "contradictoire")
        self.assertFalse(q["candidate_for_independent_88_admission_review"])

    def test_overlapping_selection_windows_rejected(self):
        p = preview()
        with self.assertRaisesRegex(ValueError, "Overlapping selected periods"):
            scope.assess_selected_scope_37(
                ACCOUNT, p, [request(p), request(p)],
                verify_user_approval=verify_user,
            )

    def test_no_selected_daily_rows_remain_unknown(self):
        p = preview([])
        q = scope.assess_selected_scope_37(
            ACCOUNT, p, [request(p, gaps=[
                "2026-01-01", "2026-01-02", "2026-01-03",
            ])], verify_user_approval=verify_user,
        )["periods"][0]
        self.assertEqual(q["qualification"], "inconnue")
        self.assertFalse(q["candidate_for_independent_88_admission_review"])


if __name__ == "__main__":
    unittest.main()
