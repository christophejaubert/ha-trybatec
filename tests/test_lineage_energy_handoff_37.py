"""FR/EN: synthetic #37 -> #88 evidence contract regressions."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec"
PKG = "lineage37_handoff_tests"
module = types.ModuleType(PKG)
module.__path__ = [str(ROOT)]
sys.modules.setdefault(PKG, module)


def load(name):
    fullname = f"{PKG}.{name}"
    spec = importlib.util.spec_from_file_location(fullname, ROOT / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    sys.modules[fullname] = result
    spec.loader.exec_module(result)
    return result


load("meter_lineage_37")
bridge = load("lineage_history_bridge_37")
handoff = load("lineage_energy_handoff_37")


def fixture():
    meter = {
        "lot": "TEST-LOT", "fluid": "EF", "serial": "TEST-METER",
        "retired": True, "source_fingerprint": "a" * 64,
        "reviewed_readings": [
            (datetime(2026, 1, 1, tzinfo=timezone.utc), 100),
            (datetime(2026, 1, 3, tzinfo=timezone.utc), 102),
        ], "conflicts": 0, "decreases": 0,
    }
    variant = {
        "lot": meter["lot"], "fluid": meter["fluid"], "serial": meter["serial"],
        "source_fingerprint": meter["source_fingerprint"], "normalized_unit": "m³",
        "status": "preview_only", "selected_gap_fingerprints": [],
        "raw": {date(2026, 1, 2): 2}, "smoothed": {date(2026, 1, 2): 2},
    }
    return bridge.prepare_physical_continuity_37(
        "TEST-ACCOUNT",
        {"__physical_meters__": {("TEST-LOT", "EF", "TEST-METER"): meter}},
        {"meters": [variant]},
    )


class HandoffTests(unittest.TestCase):
    def test_retired_and_cumulative_conservation(self):
        envelope = handoff.prepare_energy_lineage_handoff_37(fixture())
        self.assertEqual(envelope["groups"][0]["retired_meter_count"], 1)
        self.assertEqual(envelope["groups"][0]["total"], "2")
        self.assertEqual(envelope["groups"][0]["contributors_observed"], 1)

    def test_all_energy_guards_remain_false_even_if_scope_claimed(self):
        result = handoff.prepare_energy_lineage_handoff_37(fixture(), account_scope_verified=True)
        self.assertTrue(result["account_scope_observed"])
        for key in ("physical_inventory_complete", "recorder_persistence_verified",
                    "competing_versions_exhausted", "energy_activation_authorized", "writes"):
            self.assertFalse(result[key])
        self.assertFalse(result["groups"][0]["physical_coverage_proven"])

    def test_no_duplicate_physical_identity(self):
        f = fixture()
        f["inventory"].append(deepcopy(f["inventory"][0]))
        f["meter_count"] = 2
        with self.assertRaisesRegex(ValueError, "duplicate physical"):
            handoff.prepare_energy_lineage_handoff_37(f)

    def test_inconsistent_sum_rejected(self):
        f = fixture()
        f["groups"][0]["rows"][0]["cumulative"] = "300"
        with self.assertRaisesRegex(ValueError, "cumulative sum"):
            handoff.prepare_energy_lineage_handoff_37(f)

    def test_missing_meter_link_rejected(self):
        f = fixture()
        f["groups"][0]["physical_meters"] = []
        with self.assertRaisesRegex(ValueError, "cover all physical"):
            handoff.prepare_energy_lineage_handoff_37(f)

    def test_unknown_contributor_rejected(self):
        f = fixture()
        f["groups"][0]["rows"][0]["contributors"][0]["serial"] = "OTHER"
        with self.assertRaisesRegex(ValueError, "contributor"):
            handoff.prepare_energy_lineage_handoff_37(f)

    def test_untrusted_prevalidated_ready_input_rejected(self):
        f = fixture()
        f["energy_activation_authorized"] = True
        with self.assertRaisesRegex(ValueError, "unactivated"):
            handoff.prepare_energy_lineage_handoff_37(f)

    def test_deterministic_fingerprint(self):
        f = fixture()
        a = handoff.prepare_energy_lineage_handoff_37(f)
        b = handoff.prepare_energy_lineage_handoff_37(deepcopy(f))
        self.assertEqual(a["fingerprint"], b["fingerprint"])


if __name__ == "__main__":
    unittest.main()
