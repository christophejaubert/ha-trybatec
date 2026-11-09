"""b15 alternate per-physical meter previews, never additive source indexes."""
from datetime import date

import pytest

from custom_components.trybatec.history import build_history
from custom_components.trybatec.history_reconstruction import preview_sparse_intervals, consolidate_consumptions
from custom_components.trybatec.history_variants_b15 import variants_preview


def row(serial, indexes, *, deposed=True):
    return {
        "compteur": serial, "fluide": "EF", "lot": "SYNTHETIC-LOT",
        "depose": deposed,
        "indexes": [
            {"date": timestamp, "value": value} for timestamp, value in indexes
        ],
    }


def example():
    payload = {"lines": [
        row("OLD", [
            ("2022-01-31T12:00:00+01:00", 100),
            ("2022-12-01T12:00:00+01:00", 404),
        ]),
        row("NEW", [
            ("2023-01-01T12:00:00+01:00", 2),
            ("2023-01-02T12:00:00+01:00", 4),
        ], deposed=False),
    ]}
    history = build_history(
        [payload], date(2022, 1, 1), date(2023, 2, 1),
        allowed_lots={"SYNTHETIC-LOT"},
    )
    units = {key: "m³" for key in history["__physical_meters__"]}
    return history, units


def test_alternatives_preserve_old_meter_and_do_not_add_raw_indexes():
    history, units = example()
    gaps = preview_sparse_intervals(history, units)
    assert gaps["total_sparse_intervals"] == 1
    choice = {gaps["intervals"][0]["interval_key"]: {
        "mode": "linear", "reason": "manual_periodic",
    }}
    preview = variants_preview(history, units, choice)
    assert preview["mode"] == "read_only_no_recorder_energy_or_source_changes"
    old, new = preview["meters"]
    assert old["serial"] == "NEW" or old["serial"] == "OLD"
    by_name = {x["serial"]: x for x in preview["meters"]}
    assert by_name["OLD"]["retired"]
    assert not by_name["NEW"]["retired"]
    assert by_name["OLD"]["raw_total"] == 0
    assert by_name["OLD"]["smoothed_total"] == 304
    assert by_name["NEW"]["raw_total"] == 2
    assert by_name["NEW"]["smoothed_total"] == 2
    source_rows = []
    for record in preview["meters"]:
        for variant in ("raw", "smoothed"):
            source_rows.append({
                "lot": record["lot"], "fluid": record["fluid"],
                "serial": record["serial"], "variant": variant,
                "unit": record["normalized_unit"], "daily": record[variant],
            })
    # Consolidation adds per-day consumption, never 404 + 4 source indexes.
    plan = consolidate_consumptions(
        "synthetic-account", "SYNTHETIC-LOT", "EF",
        source_rows, {"OLD": "smoothed", "NEW": "raw"},
    )
    assert plan["total"] == pytest.approx(306.0)
    assert plan["selected_meters"] == {"NEW": "raw", "OLD": "smoothed"}


def test_unapproved_gap_is_not_interpolated():
    history, units = example()
    output = variants_preview(history, units)
    by_name = {r["serial"]: r for r in output["meters"]}
    assert by_name["OLD"]["smoothed_total"] == 0
    assert output["selected_intervals"] == 0


def test_uncertified_or_foreign_interval_fails_closed():
    history, units = example()
    units = {key: unit for key, unit in units.items() if key[2] == "NEW"}
    view = variants_preview(history, units)
    assert any(x["status"] == "blocked_unverified_unit" for x in view["meters"])
    with pytest.raises(ValueError, match="foreign"):
        variants_preview(history, units, {"a" * 32: {"mode": "linear", "reason": "other"}})


def test_user_selected_linear_requires_reason():
    history, units = example()
    key = preview_sparse_intervals(history, units)["intervals"][0]["interval_key"]
    with pytest.raises(ValueError, match="reason"):
        variants_preview(history, units, {key: {"mode": "linear"}})
