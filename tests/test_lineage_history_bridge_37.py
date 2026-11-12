"""FR/EN: tests fictifs du contrat historique #36 → filiation #37."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec"
PACKAGE = "lineage37_isolated_tests"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules.setdefault(PACKAGE, package)


def load(filename):
    name = f"{PACKAGE}.{filename}"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{filename}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


load("meter_lineage_37")
bridge = load("lineage_history_bridge_37")


def source(serial="A", retired=False, fingerprint=None):
    return {
        "lot": "LOT-FICTIF", "fluid": "EF", "serial": serial,
        "retired": retired, "conflicts": 0, "decreases": 0,
        "source_fingerprint": fingerprint or "a" * 64,
        "reviewed_readings": [
            (datetime(2026, 1, 1, tzinfo=timezone.utc), 100),
            (datetime(2026, 1, 3, tzinfo=timezone.utc), 101),
        ],
    }


def variant(s, raw=None, smoothed=None, approvals=None):
    raw = raw if raw is not None else {date(2026, 1, 2): Decimal("1")}
    return {
        "lot": s["lot"], "fluid": s["fluid"], "serial": s["serial"],
        "source_fingerprint": s["source_fingerprint"],
        "normalized_unit": "m³", "status": "preview_only",
        "selected_gap_fingerprints": approvals or [],
        "raw": raw, "smoothed": smoothed if smoothed is not None else dict(raw),
    }


def snapshot(serial="A", deposed=False, known=True):
    return {
        "lot": "LOT-FICTIF", "fluid": "EF", "serial": serial,
        "deposed": deposed, "service_status_known": known,
    }


def run(sources, variants, **kwargs):
    return bridge.prepare_physical_continuity_37(
        "compte-fictif",
        {"__physical_meters__": {
            (s["lot"], s["fluid"], s["serial"]): s for s in sources
        }},
        {"meters": variants},
        **kwargs,
    )


class Bridge37Tests(unittest.TestCase):
    def test_active_meter_and_source_total(self):
        a = source()
        value = run([a], [variant(a)], current={"A": snapshot()})
        self.assertEqual(value["groups"][0]["total"], "1")
        self.assertEqual(value["inventory"][0]["status"], "en_service")
        self.assertFalse(value["energy_activation_authorized"])

    def test_deposed_meter_remains_historical(self):
        a = source(retired=True)
        value = run([a], [variant(a)])
        self.assertEqual(value["inventory"][0]["status"], "depose")
        self.assertTrue(value["inventory"][0]["historical_reading_only"])
        self.assertEqual(value["groups"][0]["total"], "1")

    def test_uncertain_status_is_not_assumed_active(self):
        a = source()
        value = run([a], [variant(a)])
        self.assertEqual(value["inventory"][0]["status"], "inconnu")
        self.assertIn("physical_service_status_unknown", value["groups"][0]["blockers"])

    def test_measured_plus_estimated_same_day(self):
        a = source()
        v = variant(a, smoothed={date(2026, 1, 2): Decimal("1.25")},
                    approvals=["decision-fictive"])
        value = run([a], [v])
        self.assertEqual(value["groups"][0]["total"], "1.25")
        self.assertEqual(value["groups"][0]["rows"][0]["contributors"][0]["provenance"], "mixed")

    def test_estimated_only_day_has_provenance(self):
        a = source()
        v = variant(a, smoothed={
            date(2026, 1, 2): Decimal("1"),
            date(2026, 1, 3): Decimal("0.5"),
        }, approvals=["decision-fictive"])
        value = run([a], [v])
        self.assertEqual(value["groups"][0]["total"], "1.5")
        self.assertEqual(value["groups"][0]["rows"][1]["contributors"][0]["provenance"], "estimated_linear_confirmed")

    def test_unapproved_estimate_rejected(self):
        a = source()
        v = variant(a, smoothed={date(2026, 1, 2): Decimal("2")})
        # With no selected decisions, the raw measured series remains selected.
        self.assertEqual(run([a], [v])["groups"][0]["total"], "1")
        with self.assertRaises(ValueError):
            bridge._daily(v["raw"], v["smoothed"], selected="smoothed", decisions=[])

    def test_mismatched_archive_fingerprint_blocks(self):
        a = source(retired=True)
        archive = dict(snapshot(deposed=True), retired=True, source_fingerprint="b" * 64)
        value = run([a], [variant(a)], archived={"A": archive})
        self.assertEqual(value["groups"][0]["status"], "blocked_incomplete_physical_series")
        self.assertIn("archive_source_fingerprint_changed", value["groups"][0]["blockers"])

    def test_current_only_meter_blocks_complete_group(self):
        a = source()
        value = run([a], [variant(a)], current={
            "A": snapshot(), "B": snapshot("B")
        })
        self.assertEqual(value["groups"][0]["status"], "blocked_incomplete_physical_series")
        self.assertEqual(value["groups"][0]["rows"], [])

    def test_cross_scope_history_is_not_consolidated(self):
        a = source()
        b = source("B")
        b["lot"] = "AUTRE-LOT"
        value = run([a, b], [variant(a), variant(b)])
        self.assertEqual(len(value["groups"]), 2)
        self.assertTrue(all(g["total"] == "1" for g in value["groups"]))

    def test_declining_indexes_block_group(self):
        a = source()
        a["decreases"] = 1
        value = run([a], [variant(a)])
        self.assertEqual(value["groups"][0]["rows"], [])
        self.assertIn("unresolved_physical_source_anomaly", value["groups"][0]["blockers"])

    def test_source_drift_blocks_group(self):
        a = source()
        v = variant(a)
        v["source_fingerprint"] = "b" * 64
        value = run([a], [v])
        self.assertIn("variant_source_fingerprint_changed", value["groups"][0]["blockers"])

    def test_no_real_energy_activation_or_recorder_writes(self):
        a = source(retired=True)
        value = run([a], [variant(a)])
        self.assertFalse(value["writes"])
        self.assertFalse(value["recorder_persistence_proven"])
        self.assertFalse(value["historical_inventory_proven_complete"])
        self.assertFalse(value["energy_activation_authorized"])


if __name__ == "__main__":
    unittest.main()
