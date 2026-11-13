"""FR/EN: synthetic final continuity and Energy handoff regressions for #37.

No vendor data, network, Recorder or Home Assistant writes.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "trybatec"
PKG = "lineage37_final_isolated"
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


meter_mod = load("meter_lineage_37")
bridge = load("lineage_history_bridge_37")
handoff = load("lineage_energy_handoff_37")
BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def physical(serial, start=0, fluid="EF", retired=False, fingerprint=None, value=1):
    first = BASE + timedelta(days=start)
    last = first + timedelta(days=2)
    return {
        "lot": "LOT-FICTIF", "fluid": fluid, "serial": serial,
        "retired": retired, "source_fingerprint": fingerprint or serial * 64,
        "reviewed_readings": [(first, 100), (last, 100 + value)],
        "conflicts": 0, "decreases": 0,
    }


def variant(meter, start=0, value=1, unit=None):
    fluid = meter["fluid"]
    day = (BASE + timedelta(days=start + 1)).date()
    return {
        "lot": meter["lot"], "fluid": fluid, "serial": meter["serial"],
        "source_fingerprint": meter["source_fingerprint"],
        "status": "preview_only", "normalized_unit": unit or
        ("kWh" if fluid == "CET" else "m³"),
        "selected_gap_fingerprints": [],
        "raw": {day: value}, "smoothed": {day: value},
    }


def snapshot(meter, deposed=False):
    return {
        "lot": meter["lot"], "fluid": meter["fluid"], "serial": meter["serial"],
        "deposed": deposed, "service_status_known": True,
    }


def link(a, b):
    return {
        "lot": a["lot"], "fluid": a["fluid"],
        "from_serial": a["serial"], "to_serial": b["serial"],
        "from_fingerprint": a["source_fingerprint"],
        "to_fingerprint": b["source_fingerprint"],
        "evidence_reference": "fictitious-approved-link",
    }


def make(meters, selections=None, *, current=None, archived=None, links=(), parallel=None):
    selections = selections or [
        variant(m, int((m["reviewed_readings"][0][0] - BASE).days))
        for m in meters
    ]
    return bridge.prepare_physical_continuity_37(
        "ACCOUNT-FICTIF",
        {"__physical_meters__": {
            (m["lot"], m["fluid"], m["serial"]): m for m in meters
        }},
        {"meters": selections}, current=current, archived=archived,
        confirmed_links=links, approved_parallel=parallel,
    )


class FinalLineage37Tests(unittest.TestCase):
    def test_three_generations_preserve_physical_identity_and_total(self):
        a = physical("A", 0, retired=True)
        b = physical("B", 5, retired=True, value=2)
        c = physical("C", 10, value=3)
        evidence = make(
            [a, b, c],
            selections=[variant(a, 0, 1), variant(b, 5, 2), variant(c, 10, 3)],
            current={"C": snapshot(c)},
            links=[link(a, b), link(b, c)],
        )
        group = evidence["groups"][0]
        self.assertEqual(group["total"], "6")
        self.assertEqual([x["relation"] for x in group["lineage"]],
                         ["confirmed_successor", "confirmed_successor"])
        self.assertEqual([x["serial"] for x in group["physical_meters"]], ["A", "B", "C"])
        self.assertEqual([x["status"] for x in group["physical_meters"]],
                         ["depose", "depose", "en_service"])
        self.assertEqual(len(group["unobserved_intervals"]), 2)
        self.assertTrue(all(x["consumption"] is None and
                            x["service_transition_proven"] is False
                            for x in group["unobserved_intervals"]))
        self.assertFalse(group["full_historical_coverage_verified"])
        self.assertEqual([x["consumption"] for x in group["rows"]],
                         ["1", "2", "3"])

    def test_overlap_blocks_without_evidence_and_parallel_remains_readonly(self):
        a = physical("A", retired=True)
        b = physical("B")
        plain = make([a, b])
        self.assertEqual(plain["groups"][0]["rows"], [])
        self.assertIn("duplicate_or_ambiguous_consumption_day",
                      plain["groups"][0]["blockers"])
        keys = frozenset((("LOT-FICTIF", "EF", "A"), ("LOT-FICTIF", "EF", "B")))
        parallel = make([a, b], parallel={keys})
        group = parallel["groups"][0]
        self.assertEqual(group["total"], "2")
        self.assertTrue(group["parallel_meter_approval_requires_independent_review"])
        self.assertFalse(parallel["energy_activation_authorized"])

    def test_unknown_replacement_has_no_invented_start_or_consumption(self):
        a = physical("A", retired=True)
        b = physical("B", 25)
        group = make([a, b])["groups"][0]
        self.assertEqual(group["total"], "2")
        self.assertIn("unverified_successor_link", group["blockers"])
        self.assertIsNone(group["physical_meters"][0]["service_end"])
        self.assertIsNone(group["unobserved_intervals"][0]["consumption"])
        self.assertEqual(len(group["rows"]), 2)

    def test_cache_only_generation_blocks_all_output(self):
        a = physical("A")
        b = physical("B")
        outcome = make([a], current={"A": snapshot(a), "B": snapshot(b)})
        self.assertEqual(outcome["meter_count"], 2)
        self.assertEqual(outcome["groups"][0]["rows"], [])
        self.assertEqual(outcome["groups"][0]["status"], "blocked_incomplete_physical_series")
        report = handoff.prepare_energy_lineage_handoff_37(outcome)
        self.assertIsNone(report["groups"][0]["total"])
        self.assertFalse(report["physical_inventory_complete"])

    def test_contradictory_retired_status_blocks(self):
        a = physical("A", retired=True)
        result = make([a], current={"A": snapshot(a)})
        self.assertEqual(result["inventory"][0]["status"], "inconnu")
        self.assertIn("source_status_conflict", result["groups"][0]["blockers"])
        self.assertEqual(result["groups"][0]["rows"], [])

    def test_unknown_unit_blocks_without_guessing(self):
        a = physical("A")
        broken = variant(a, unit="kWh")
        result = make([a], selections=[broken])
        self.assertIn("unverified_normalized_unit", result["groups"][0]["blockers"])
        self.assertEqual(result["groups"][0]["rows"], [])

    def test_index_decrease_excludes_generation(self):
        a = physical("A")
        a["decreases"] = 1
        result = make([a])
        self.assertEqual(result["groups"][0]["rows"], [])
        self.assertIn("unresolved_physical_source_anomaly", result["groups"][0]["blockers"])

    def test_cross_fluid_same_serial_does_not_merge(self):
        a = physical("A", fluid="EF")
        heating = physical("A", fluid="CET")
        result = make([a, heating], current={"a": snapshot(a), "b": snapshot(heating)})
        self.assertEqual({g["fluid"] for g in result["groups"]}, {"EF", "CET"})
        self.assertEqual({g["unit"] for g in result["groups"]}, {"m³", "kWh"})

    def test_foreign_confirmed_link_fails_closed(self):
        a = physical("A")
        b = physical("B")
        with self.assertRaisesRegex(ValueError, "Foreign or incomplete"):
            make([a], links=[link(a, b)])

    def test_foreign_parallel_reference_fails_closed(self):
        a = physical("A")
        with self.assertRaisesRegex(ValueError, "Foreign parallel"):
            make([a], parallel={frozenset((
                ("LOT-FICTIF", "EF", "A"), ("LOT-FICTIF", "EF", "MISSING")
            ))})

    def test_multiple_estimates_use_set_fingerprint_not_first_approval(self):
        raw = {date(2026, 1, 2): 1}
        smooth = {date(2026, 1, 2): 2}
        result = bridge._daily(raw, smooth, selected="smoothed",
                               decisions=["approved-gap-B", "approved-gap-A"])
        proof = result["2026-01-02"]["decision_fingerprint"]
        self.assertTrue(proof.startswith("decision_set:"))
        self.assertNotEqual(proof, "approved-gap-B")
        self.assertEqual(proof, bridge._daily(raw, smooth, selected="smoothed",
                         decisions=["approved-gap-A", "approved-gap-B"])
                         ["2026-01-02"]["decision_fingerprint"])

    def test_handoff_digest_changes_on_same_total_different_days(self):
        a = physical("A")
        first = make([a], current={"A": snapshot(a)})
        different = deepcopy(first)
        different["groups"][0]["rows"][0]["date"] = "2026-01-03"
        one = handoff.prepare_energy_lineage_handoff_37(first)
        two = handoff.prepare_energy_lineage_handoff_37(different)
        self.assertNotEqual(one["fingerprint"], two["fingerprint"])
        self.assertNotEqual(one["groups"][0]["daily_evidence_fingerprint"],
                            two["groups"][0]["daily_evidence_fingerprint"])

    def test_handoff_digest_binds_fingerprint_and_source_status(self):
        a = physical("A")
        first = make([a], current={"A": snapshot(a)})
        altered = deepcopy(first)
        altered["inventory"][0]["source_fingerprint"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "source or selection drift"):
            handoff.prepare_energy_lineage_handoff_37(altered)
        # Source audit changes must not produce the same admissibility hash.
        changed = deepcopy(first)
        changed["inventory"][0]["status"] = "inconnu"
        changed["groups"][0]["physical_meters"][0]["status"] = "inconnu"
        d1 = handoff.prepare_energy_lineage_handoff_37(first)
        d2 = handoff.prepare_energy_lineage_handoff_37(changed)
        self.assertNotEqual(d1["fingerprint"], d2["fingerprint"])

    def test_references_are_observed_not_exhaustive_or_authorized(self):
        a = physical("A")
        result = make([a])
        versions = {("LOT-FICTIF", "EF"): [
            "trybatec:logical_ef_v1", "trybatec:logical_ef_v2"
        ]}
        selected = {("LOT-FICTIF", "EF"): [
            "trybatec:logical_ef_v1", "trybatec:logical_ef_v2"
        ]}
        output = handoff.prepare_energy_lineage_handoff_37(
            result, known_statistic_versions=versions,
            selected_energy_sources=selected,
        )
        group = output["groups"][0]
        self.assertIn("competing_energy_sources_selected", group["blockers"])
        self.assertTrue(group["statistic_reference_catalog_observed"])
        self.assertEqual(len(group["observed_competing_statistic_ids"]), 2)
        self.assertFalse(output["competing_versions_exhausted"])
        self.assertFalse(output["energy_activation_authorized"])

    def test_existing_energy_source_outside_observed_versions_flags(self):
        a = physical("A")
        report = handoff.prepare_energy_lineage_handoff_37(
            make([a]),
            known_statistic_versions={("LOT-FICTIF", "EF"): ["stat-v2"]},
            selected_energy_sources={("LOT-FICTIF", "EF"): ["legacy-stat-v1"]},
        )
        self.assertIn("selected_energy_source_outside_observed_versions",
                      report["groups"][0]["blockers"])

    def test_reference_catalog_duplicates_and_foreign_lot_rejected(self):
        a = physical("A")
        p = make([a])
        with self.assertRaisesRegex(ValueError, "Duplicated statistic"):
            handoff.prepare_energy_lineage_handoff_37(
                p, known_statistic_versions={("LOT-FICTIF", "EF"): ["a", "a"]})
        with self.assertRaisesRegex(ValueError, "Foreign or malformed"):
            handoff.prepare_energy_lineage_handoff_37(
                p, selected_energy_sources={("WRONG-LOT", "EF"): ["a"]})

    def test_handoff_rejects_noncanonical_daily_dates(self):
        a = physical("A")
        p = make([a])
        p["groups"][0]["rows"][0]["date"] = "not-a-date"
        with self.assertRaisesRegex(ValueError, "calendar date"):
            handoff.prepare_energy_lineage_handoff_37(p)

    def test_reload_and_idempotence_are_json_stable(self):
        a = physical("A", retired=True)
        b = physical("B", 5)
        value = make([a, b], current={"B": snapshot(b)}, links=[link(a, b)])
        first = handoff.prepare_energy_lineage_handoff_37(value)
        disk_simulated = json.loads(json.dumps(first, sort_keys=True))
        second = handoff.prepare_energy_lineage_handoff_37(deepcopy(value))
        self.assertEqual(first, disk_simulated)
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertFalse(first["writes"])

    def test_nonadjacent_generations_overlap_even_on_distinct_days(self):
        def meter(serial, first, last):
            return {
                "lot": "LOT-FICTIF", "fluid": "EF", "serial": serial,
                "status": "depose" if serial != "C" else "en_service",
                "first_observed_at": f"2026-01-{first:02d}T12:00:00+00:00",
                "last_observed_at": f"2026-01-{last:02d}T12:00:00+00:00",
                "service_start": None, "service_end": None,
                "unit": "m³", "source_fingerprint": serial * 64,
            }

        meters = [meter("A", 1, 15), meter("B", 5, 10), meter("C", 11, 13)]
        selected = {(m["lot"], m["fluid"], m["serial"]): "raw" for m in meters}

        def daily(m, day):
            return {
                "kind": "consumption", "lot": m["lot"], "fluid": m["fluid"],
                "serial": m["serial"], "unit": "m³", "variant": "raw",
                "source_fingerprint": m["source_fingerprint"],
                "daily": {f"2026-01-{day:02d}": {
                    "amount": "1", "provenance": "measured"
                }},
            }

        sources = [daily(meters[0], 2), daily(meters[1], 6), daily(meters[2], 12)]
        key_a = ("LOT-FICTIF", "EF", "A")
        key_b = ("LOT-FICTIF", "EF", "B")
        key_c = ("LOT-FICTIF", "EF", "C")
        a_b = frozenset((key_a, key_b))
        preview = meter_mod.preview_lineage(
            "ACCOUNT-FICTIF", meters, sources, selected,
            approved_parallel={a_b},
        )
        self.assertIn("unverified_physical_period_overlap",
                      preview["groups"][0]["blockers"])
        self.assertEqual(preview["groups"][0]["rows"], [])
        fully_reviewed = meter_mod.preview_lineage(
            "ACCOUNT-FICTIF", meters, sources, selected,
            approved_parallel={a_b, frozenset((key_a, key_c))},
        )
        self.assertEqual(fully_reviewed["groups"][0]["total"], "3")
        self.assertFalse(fully_reviewed["energy_activation_authorized"])

    def test_nul_delimiter_cannot_alias_another_logical_scope(self):
        with self.assertRaisesRegex(ValueError, "Invalid physical identity"):
            meter_mod.preview_lineage("ACCOUNT" + chr(0) + "FICTIF", [], [], {})

    def test_handoff_never_accepts_claimed_authority(self):
        a = physical("A")
        value = make([a])
        value["energy_version_exclusivity_proven"] = True
        with self.assertRaisesRegex(ValueError, "unactivated"):
            handoff.prepare_energy_lineage_handoff_37(value)


if __name__ == "__main__":
    unittest.main()
