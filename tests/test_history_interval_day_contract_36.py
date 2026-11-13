"""#36 synthetic day-attribution proof; external source completeness not asserted."""
from copy import deepcopy
from datetime import date, datetime, timezone

import pytest

from custom_components.trybatec.history_interval_day_contract_36 import (
    project_interval_day_decisions,
)
from custom_components.trybatec.history_reconstruction import propose_interval

KEY, SOURCE = "a" * 32, "b" * 64
STAMP = "2026-11-13T12:00:00+00:00"


def _choice(reason="undetermined_confirmed", mode="linear"):
    choice = {"mode": mode, "reason": reason, "updated_at": STAMP}
    if reason == "undetermined_confirmed":
        choice["confirmed_unknown_origin"] = True
    return choice


def _preview(mode="linear", *, estimated_origin=False):
    args = {
        "start_reading": (
            None if estimated_origin
            else (datetime(2026, 1, 1, 12, tzinfo=timezone.utc), 10.0)
        ),
        "end_reading": (datetime(2026, 1, 4, 12, tzinfo=timezone.utc), 18.0),
        "measured_by_day": {date(2026, 1, 2): 2.0, date(2026, 1, 4): 1.0},
        "mode": mode,
    }
    if estimated_origin:
        args["estimated_start_date"] = date(2026, 1, 1)
        args["estimated_start_index"] = 10.0
        args["confirm_estimated_start"] = True
    return propose_interval(**args)


def _contract(report=None, reason="undetermined_confirmed", mode="linear"):
    return project_interval_day_decisions(
        interval_key=KEY, source_fingerprint=SOURCE,
        confirmed_choice=_choice(reason=reason, mode=mode),
        reconstruction_preview=_preview(mode) if report is None else report,
    )


def test_confirmed_unknown_reason_does_not_turn_estimates_into_measurements():
    original = _preview()
    before = deepcopy(original)
    result = _contract(original)
    assert original == before
    assert result["explicit_unknown_origin"] is True
    assert result["decision_reason"] == "undetermined_confirmed"
    assert result["measured_total"] == 3.0
    assert result["estimated_total"] == 5.0
    assert result["raw_interval_total"] == 8.0
    assert result["unallocated_total"] == 0.0
    assert len(result["daily"]) == 3
    assert {d["provenance"] for d in result["daily"]} == {
        "measured", "estimated_linear",
    }
    assert all(d["interval_origin_reason"] == "unknown" for d in result["daily"])
    assert sum(d["is_estimate"] for d in result["daily"]) == 1
    assert len({d["day_decision_fingerprint"] for d in result["daily"]}) == 3
    assert not result["supplier_observations_independently_attested"]
    assert not result["energy_activation_authorized"]
    assert not result["recorder_writes"]


def test_reject_unconfirmed_draft_unknown_reason():
    with pytest.raises(ValueError, match="Unsupported sparse interval"):
        project_interval_day_decisions(
            interval_key=KEY, source_fingerprint=SOURCE,
            confirmed_choice={"mode": "linear", "reason": "undetermined",
                              "updated_at": STAMP},
            reconstruction_preview=_preview(),
        )


def test_declining_smoothing_leaves_residual_unallocated():
    result = _contract(_preview("none"), mode="none")
    assert result["estimated_total"] == 0
    assert result["unallocated_total"] == 5
    assert result["missing_days"] == ["2026-01-03"]
    assert all(row["provenance"] == "measured" for row in result["daily"])
    assert result["energy_activation_authorized"] is False


def test_estimated_initial_index_is_never_mislabeled_as_vendor_reading():
    report = _preview(estimated_origin=True)
    result = _contract(report)
    assert result["estimated_initial_bound_not_supplier_reading"] is True
    assert all(
        row["estimated_initial_bound_not_supplier_reading"]
        for row in result["daily"]
    )
    assert result["raw_interval_total"] == 8


@pytest.mark.parametrize("tamper", [
    lambda p: p["allocations"].append(deepcopy(p["allocations"][0])),
    lambda p: p["allocations"][0].update(provenance="observed_supplier"),
    lambda p: p["allocations"][0].update(quantity=1000),
    lambda p: p["allocations"][0].update(date="2026-01-01"),
    lambda p: p.update(estimated_total=0),
    lambda p: p.update(origin="invented_observed"),
    lambda p: p.update(status="persisted_to_recorder"),
    lambda p: p.update(total=9000),
    lambda p: p.update(mode="none"),
])
def test_conflicting_or_fabricated_daily_proof_is_rejected(tamper):
    report = _preview()
    tamper(report)
    with pytest.raises(ValueError):
        _contract(report)


def test_day_fingerprint_changes_when_reason_is_known():
    unknown = _contract()
    known = _contract(reason="telemetry_failure")
    assert [r["date"] for r in unknown["daily"]] == [
        r["date"] for r in known["daily"]
    ]
    assert all(r["interval_origin_reason"] == "telemetry_failure"
               for r in known["daily"])
    assert [r["day_decision_fingerprint"] for r in unknown["daily"]] != [
        r["day_decision_fingerprint"] for r in known["daily"]
    ]
