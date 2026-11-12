"""Fictitious standalone regression suite for #37; no HA or vendor calls."""
import copy
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "custom_components/trybatec/meter_lineage_37.py"
spec = importlib.util.spec_from_file_location("meter_lineage_37", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def meter(serial="M-A", status="en_service", first="2026-01-01T12:00:00+01:00", last="2026-01-03T12:00:00+01:00", unit="m³", start="2026-01-01", end="2026-01-03"):
    return {"lot": "LOT-FICTIF", "fluid": "EF", "serial": serial, "status": status,
            "first_observed_at": first, "last_observed_at": last,
            "service_start": start, "service_end": end, "unit": unit,
            "source_fingerprint": "f-" + serial}


def series(m, daily=None, variant="raw"):
    daily = daily or {"2026-01-02": "1.5"}
    return {"kind": "consumption", "lot": m["lot"], "fluid": m["fluid"],
            "serial": m["serial"], "variant": variant, "unit": m["unit"],
            "source_fingerprint": m["source_fingerprint"], "daily": {
                day: {"amount": amount, "provenance": "measured"} for day, amount in daily.items()}}


def key(m):
    return m["lot"], m["fluid"], m["serial"]


def link(a, b):
    return {"lot": a["lot"], "fluid": a["fluid"], "from_serial": a["serial"],
            "to_serial": b["serial"], "from_fingerprint": a["source_fingerprint"],
            "to_fingerprint": b["source_fingerprint"], "evidence_reference": "decision-fictive-1"}


class Lineage37Tests(unittest.TestCase):
    def preview(self, meters, data, links=(), **kw):
        return mod.preview_lineage("compte-fictif", meters, data, {key(m): "raw" for m in meters}, confirmed_links=links, **kw)

    def test_one_active_meter(self):
        a = meter()
        g = self.preview([a], [series(a)])["groups"][0]
        self.assertEqual(g["total"], "1.5")
        self.assertEqual(len(g["physical_meters"]), 1)
        self.assertFalse(g["energy_activation_authorized"])

    def test_successive_generations_and_distinct_indexes(self):
        a = meter(last="2026-01-03T12:00:00+01:00", status="depose")
        b = meter("M-B", first="2026-01-05T12:00:00+01:00", last="2026-01-07T12:00:00+01:00", start="2026-01-05", end="2026-01-07")
        g = self.preview([a, b], [series(a), series(b, {"2026-01-06": "2"})], links=[link(a, b)])["groups"][0]
        self.assertEqual(g["lineage"][0]["relation"], "confirmed_successor")
        self.assertEqual(g["total"], "3.5")
        self.assertEqual([m["status"] for m in g["physical_meters"]], ["depose", "en_service"])

    def test_replacement_gap_is_not_invented(self):
        a = meter(status="depose")
        b = meter("M-B", first="2026-02-01T12:00:00+01:00", last="2026-02-03T12:00:00+01:00", start="2026-02-01", end="2026-02-03")
        g = self.preview([a, b], [series(a), series(b, {"2026-02-02": "4"})], links=[link(a, b)])["groups"][0]
        self.assertEqual([row["date"] for row in g["rows"]], ["2026-01-02", "2026-02-02"])

    def test_replacement_overlap_blocks_consolidated_rows(self):
        a = meter(status="depose")
        b = meter("M-B", first="2026-01-02T12:00:00+01:00")
        g = self.preview([a, b], [series(a), series(b)])["groups"][0]
        self.assertIn("unverified_physical_period_overlap", g["blockers"])
        self.assertIn("duplicate_or_ambiguous_consumption_day", g["blockers"])
        self.assertEqual(g["rows"], [])

    def test_different_initial_indexes_are_not_summed(self):
        a = meter(status="depose")
        b = meter("M-B", first="2026-01-05T12:00:00+01:00", last="2026-01-07T12:00:00+01:00", start="2026-01-05", end="2026-01-07")
        g = self.preview([a, b], [series(a, {"2026-01-02": "3"}), series(b, {"2026-01-06": "1"})], links=[link(a, b)])["groups"][0]
        self.assertEqual(g["total"], "4")

    def test_unknown_status_not_changed_to_active(self):
        a = meter(status="inconnu")
        g = self.preview([a], [series(a)])["groups"][0]
        self.assertEqual(g["physical_meters"][0]["status"], "inconnu")
        self.assertIn("physical_service_status_unknown", g["blockers"])

    def test_retired_meter_retains_own_rows_and_references(self):
        a = meter(status="depose")
        original = (copy.deepcopy(a), copy.deepcopy(series(a)))
        g = self.preview([a], [series(a)])["groups"][0]
        self.assertEqual(g["rows"][0]["contributors"][0]["serial"], a["serial"])
        self.assertEqual(a, original[0])
        self.assertEqual(series(a), original[1])

    def test_no_double_counting_of_two_variants(self):
        a = meter()
        selected = mod.preview_lineage("c", [a], [series(a), series(a, {"2026-01-02": "9"}, variant="smoothed")], {key(a): "raw"})
        self.assertEqual(selected["groups"][0]["total"], "1.5")

    def test_rejects_index_instead_of_consumption(self):
        a = meter()
        s = series(a)
        s["kind"] = "index"
        with self.assertRaises(ValueError):
            self.preview([a], [s])

    def test_rejects_stale_physical_fingerprint(self):
        a = meter()
        s = series(a)
        s["source_fingerprint"] = "old"
        with self.assertRaises(ValueError):
            self.preview([a], [s])

    def test_missing_service_dates_does_not_infer_them(self):
        a = meter(start=None, end=None)
        g = self.preview([a], [series(a)])["groups"][0]
        self.assertIsNone(g["physical_meters"][0]["service_start"])
        self.assertIn("service_dates_not_proven", g["blockers"])

    def test_unapproved_or_unproven_smoothing_is_rejected(self):
        a = meter()
        s = series(a)
        s["daily"]["2026-01-02"]["provenance"] = "estimated_linear_confirmed"
        with self.assertRaises(ValueError):
            self.preview([a], [s])

    def test_deterministic_nonregression_reload(self):
        a = meter()
        s = series(a)
        x = self.preview([a], [s])
        y = self.preview(copy.deepcopy([a]), copy.deepcopy([s]))
        self.assertEqual(x, y)
        self.assertEqual(x["mode"], "read_only_no_registry_recorder_energy_writes")

    def test_incomplete_inventory_is_rejected(self):
        a = meter()
        with self.assertRaises(ValueError):
            self.preview([a], [series(a)], expected_physical_keys=set())

    def test_cross_lot_series_rejected(self):
        a = meter()
        s = series(a)
        s["lot"] = "AUTRE-LOT"
        with self.assertRaises(ValueError):
            self.preview([a], [s])

    def test_declared_parallel_meters_same_day(self):
        a = meter(status="depose")
        b = meter("M-B", first="2026-01-02T12:00:00+01:00")
        g = self.preview([a, b], [series(a), series(b)], approved_parallel={frozenset((key(a), key(b)))})["groups"][0]
        self.assertEqual(g["total"], "3.0")
        self.assertFalse(g["energy_activation_authorized"])

    def test_no_implicit_successor_confirmation(self):
        a = meter(status="depose")
        b = meter("M-B", first="2026-01-05T12:00:00+01:00", last="2026-01-07T12:00:00+01:00", start="2026-01-05", end="2026-01-07")
        g = self.preview([a, b], [series(a), series(b, {"2026-01-06": "1"})])["groups"][0]
        self.assertIn("unverified_successor_link", g["blockers"])

    def test_verified_source_unit_required(self):
        a = meter(unit=None)
        with self.assertRaises(ValueError):
            self.preview([a], [series(a)])

    def test_stale_nonadjacent_approval_rejected(self):
        a = meter(status="depose")
        b = meter("M-B", first="2026-01-05T12:00:00+01:00", last="2026-01-07T12:00:00+01:00")
        c = meter("M-C", first="2026-01-10T12:00:00+01:00", last="2026-01-12T12:00:00+01:00")
        with self.assertRaisesRegex(ValueError, "not an adjacent"):
            self.preview([a, b, c], [series(a), series(b), series(c)], links=[link(a, c)])

    def test_parallel_approval_rejects_cross_lot(self):
        a = meter()
        b = meter("M-B")
        b["lot"] = "AUTRE-LOT"
        with self.assertRaisesRegex(ValueError, "parallel-meter"):
            self.preview([a, b], [series(a), series(b)], approved_parallel={frozenset((key(a), key(b)))})


if __name__ == "__main__":
    unittest.main()
