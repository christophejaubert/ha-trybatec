"""Synthetic documentation evidence for #37; not real supplier attestation."""
from __future__ import annotations

from hashlib import sha256
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec"
PKG = "lineage37_documentary_test_isolated"
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


load("meter_lineage_37")
att = load("lineage_scope_attestation_37")
ACCOUNT = "ONLY-A-FICTITIOUS-ACCOUNT"
LOT = "SAMPLE-LOT"


def observed(serial="X", *, status="en_service"):
    return {
        "lot": LOT, "fluid": "EF", "serial": serial, "status": status,
        "first_observed_at": "2026-03-01T12:00:00+00:00",
        "last_observed_at": "2026-03-31T12:00:00+00:00",
        "service_start": None, "service_end": None,
    }


def preview(*items):
    return {
        "mode": "read_only_37_history_bridge",
        "inventory": list(items),
        "writes": False, "energy_activation_authorized": False,
        "historical_inventory_proven_complete": False,
    }


def requested():
    return [{"lot": LOT, "fluid": "EF",
             "start": "2026-03-01", "end": "2026-03-31"}]


def document(serials=("X",), *, kind="supplier_register", closed=True):
    return {
        "reference": "FAKE-DOCUMENT-ONLY",
        "kind": kind,
        "account_digest": sha256(ACCOUNT.encode()).hexdigest(),
        "lot": LOT, "fluid": "EF",
        "start": "2026-03-01", "end": "2026-03-31",
        "population_closed": closed,
        "physical_meters": [{
            "lot": LOT, "fluid": "EF", "serial": serial,
            "status": "en_service",
            "service_start": "2026-03-01",
            "service_end": "2026-03-31",
        } for serial in serials],
    }


class OptionalDocumentaryEvidenceTests(unittest.TestCase):
    def test_no_supplier_document_stays_partial_and_non_authorizing(self):
        p = att.qualify_physical_periods_37(ACCOUNT, preview(observed()), requested())
        self.assertEqual(p["periods"][0]["qualification"], "partielle")
        self.assertFalse(p["periods"][0]["supplier_population_candidate_for_period"])
        self.assertIn("no_authoritative_register_for_requested_period",
                      p["periods"][0]["blockers"])
        self.assertFalse(p["energy_activation_authorized"])

    def test_unverified_document_does_not_make_supplier_attestation(self):
        p = att.qualify_physical_periods_37(
            ACCOUNT, preview(observed()), requested(), [document()]
        )
        self.assertNotEqual(p["periods"][0]["qualification"], "attestee")
        self.assertFalse(p["periods"][0]["supplier_population_candidate_for_period"])
        self.assertFalse(p["documentary_authenticity_independently_certified_by_this_module"])

    def test_fictitious_independent_checker_is_not_real_world_authority(self):
        p = att.qualify_physical_periods_37(
            ACCOUNT, preview(observed()), requested(), [document()],
            independent_document_verifier=lambda _: True,
        )
        self.assertEqual(p["periods"][0]["qualification"], "attestee")
        self.assertTrue(p["periods"][0]["supplier_population_candidate_for_period"])
        self.assertFalse(p["complete_account_history_verified"])
        self.assertFalse(p["recorder_persistence_verified"])
        self.assertFalse(p["energy_activation_authorized"])
        self.assertFalse(p["writes"])

    def test_supplier_omits_observed_generation_is_contradiction(self):
        p = att.qualify_physical_periods_37(
            ACCOUNT, preview(observed(), observed("Y", status="depose")),
            requested(), [document()],
            independent_document_verifier=lambda _: True,
        )
        self.assertEqual(p["periods"][0]["qualification"], "contradictoire")
        self.assertIn("authoritative_register_omits_observed_generation",
                      p["periods"][0]["blockers"])

    def test_intervention_report_cannot_claim_closed_population(self):
        with self.assertRaisesRegex(ValueError, "closed population"):
            att.qualify_physical_periods_37(
                ACCOUNT, preview(observed()), requested(),
                [document(kind="intervention_report")],
            )


if __name__ == "__main__":
    unittest.main()
