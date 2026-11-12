"""Model partial Recorder failures without any database or Energy writes."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from custom_components.trybatec.history_recorder_recovery_l2 import preview_pending_recovery


def rows():
    start = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    return [[(start + timedelta(days=i)).isoformat(), float(i)] for i in range(3)]


def ledger():
    data = {"schema": 1, "series": {}, "pending": {}}
    for ident in ("a", "b"):
        logical = f"trybatec:logical_ef_{ident}"
        stat = f"{logical}_v2"
        data["series"][logical] = {"versions": [
            {"statistic_id": f"{logical}_v1", "state": "active"},
            {"statistic_id": stat, "state": "imported"},
        ]}
        data["pending"][logical] = {"statistic_id": stat, "snapshot": rows()}
    return data


def observed(snap):
    return [{"start": x[0], "sum": x[1]} for x in snap]


def test_exact_persistence_never_requeues():
    l = ledger()
    before = deepcopy(l)
    rb = {v["statistic_id"]: {"complete": True, "rows": observed(v["snapshot"])}
          for v in l["pending"].values()}
    outcome = preview_pending_recovery(l, rb, queue_quiescent=True)
    assert outcome["all_persisted"]
    assert not outcome["safe_to_offer_retry"]
    assert outcome["retry_only_these_statistic_ids"] == []
    assert l == before
    assert outcome["audit_fingerprint"] == preview_pending_recovery(l, rb, queue_quiescent=True)["audit_fingerprint"]


def test_partial_batch_retries_only_missing_after_quiescence():
    l = ledger()
    a, b = [v["statistic_id"] for v in l["pending"].values()]
    rb = {a: {"complete": True, "rows": observed(rows())},
          b: {"complete": True, "rows": []}}
    pending = preview_pending_recovery(l, rb, queue_quiescent=False)
    assert not pending["safe_to_offer_retry"]
    ready = preview_pending_recovery(l, rb, queue_quiescent=True)
    assert ready["safe_to_offer_retry"]
    assert ready["retry_only_these_statistic_ids"] == [b]
    assert ready["decisions"][0]["outcome"] == "persisted_verified_no_requeue"


def test_partial_or_corrupt_data_blocks_entire_retry_batch():
    l = ledger()
    a, b = [v["statistic_id"] for v in l["pending"].values()]
    rb = {a: {"complete": True, "rows": observed(rows()[:2])},
          b: {"complete": True, "rows": []}}
    result = preview_pending_recovery(l, rb, queue_quiescent=True)
    assert not result["safe_to_offer_retry"]
    assert result["retry_only_these_statistic_ids"] == []
    assert a in result["blocked_statistic_ids"]


def test_unknown_readback_or_missing_version_is_denied():
    l = ledger()
    with pytest.raises(ValueError):
        preview_pending_recovery(l, {"trybatec:logical_ef_foreign_v1": {"complete": True, "rows": []}})
    l["series"]["trybatec:logical_ef_a"]["versions"][1]["state"] = "verified"
    with pytest.raises(ValueError, match="inconsistent"):
        preview_pending_recovery(l, {})


def test_unavailable_readback_does_not_authorize_requeue():
    a = preview_pending_recovery(ledger(), {}, queue_quiescent=True)
    assert all(x["outcome"] == "readback_incomplete_no_retry" for x in a["decisions"])
    assert not a["safe_to_offer_retry"]


def test_duplicate_bucket_blocks_retry():
    l = ledger()
    ids = [v["statistic_id"] for v in l["pending"].values()]
    duplicated = observed(rows()) + [observed(rows())[1]]
    a = preview_pending_recovery(l, {
        ids[0]: {"complete": True, "rows": duplicated},
        ids[1]: {"complete": True, "rows": []},
    }, queue_quiescent=True)
    assert a["decisions"][0]["outcome"] == "conflicting_readback_no_retry"
    assert a["retry_only_these_statistic_ids"] == []


def test_v3_pending_does_not_archive_prior_v2_or_activate_energy():
    l = ledger()
    original = deepcopy(l)
    for logical, record in l["series"].items():
        record["versions"][1]["state"] = "active"
        record["versions"].append({
            "statistic_id": f"{logical}_v3", "state": "imported",
        })
        l["pending"][logical]["statistic_id"] = f"{logical}_v3"
    before = deepcopy(l)
    result = preview_pending_recovery(l, {}, queue_quiescent=True)
    assert not result["all_persisted"]
    assert not result["safe_to_offer_retry"]
    assert result["energy_writes"] is False
    assert result["recorder_writes"] is False
    assert l == before
    assert original["series"] != before["series"]


def test_mismatched_sum_is_not_considered_persisted():
    l = ledger()
    stat = next(iter(l["pending"].values()))["statistic_id"]
    observed_rows = observed(rows())
    observed_rows[-1]["sum"] = 999
    result = preview_pending_recovery(l, {stat: {"complete": True, "rows": observed_rows}})
    assert result["decisions"][0]["outcome"] == "partial_or_mismatched_no_retry"
