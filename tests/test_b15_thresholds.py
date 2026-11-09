"""b15 thresholds are configurable and do not alter source index data."""
from datetime import date, datetime, timedelta, timezone

import pytest

from custom_components.trybatec.history import build_history
from custom_components.trybatec.history_review import review_candidates


def meter(values, base=datetime(2026, 1, 1, 12, tzinfo=timezone.utc)):
    points = {base + timedelta(days=i): v for i, v in enumerate(values)}
    return {("synthetic-lot", "EF", "synthetic-meter"): {
        "lot": "synthetic-lot", "fluid": "EF", "serial": "synthetic-meter",
        "indexes": points, "conflict_times": set(),
    }}


def test_zero_episode_one_review_on_first_day():
    candidates = review_candidates(meter([3, 0, 0, 0]), {}, zero_review_days=1)
    flagged = [c for c in candidates if "index_zero" in c["reasons"]]
    assert len(flagged) == 1
    assert flagged[0]["index"] == 0


def test_zero_episode_threshold_two_consecutive_calendar_days():
    candidates = review_candidates(meter([3, 0, 0, 0]), {}, zero_review_days=2)
    flagged = [c for c in candidates if "index_zero" in c["reasons"]]
    assert len(flagged) == 1
    assert flagged[0]["source_date"].startswith("2026-01-03")


def test_zero_review_disabled_does_not_report_zero_as_decrease():
    candidates = review_candidates(meter([3, 0, 0]), {}, zero_review_days=0)
    assert all("index_zero" not in c["reasons"] for c in candidates)
    assert all("index_decrease" not in c["reasons"] for c in candidates)


def test_sparse_threshold_controls_review():
    p = meter([10, 11])
    first = list(p.values())[0]
    first["indexes"] = {
        datetime(2026, 1, 1, 12, tzinfo=timezone.utc): 10,
        datetime(2026, 1, 3, 12, tzinfo=timezone.utc): 11,
    }
    assert any("sparse_interval" in c["reasons"]
               for c in review_candidates(p, {}, sparse_hours=27))
    assert review_candidates(p, {}, sparse_hours=49) == []


def test_history_daily_admission_uses_same_sparse_threshold():
    payload = {"lines": [{
        "lot": "synthetic-lot", "fluide": "EF",
        "compteur": "synthetic-meter",
        "indexes": [
            {"date": "2026-01-01T12:00:00+00:00", "value": 10},
            {"date": "2026-01-03T12:00:00+00:00", "value": 12},
        ],
    }]}
    start, end = date(2026, 1, 1), date(2026, 1, 3)
    a = build_history([payload], start, end, sparse_interval_hours=27)
    b = build_history([payload], start, end, sparse_interval_hours=49)
    assert a["EF"]["importable_consumption"] == 0
    assert b["EF"]["importable_consumption"] == 2
    assert any("sparse_interval" in c["reasons"]
               for c in a["__review_candidates__"])
    assert not any("sparse_interval" in c["reasons"]
                   for c in b["__review_candidates__"])


@pytest.mark.parametrize("sparse, zeros", [(0, 1), (27, -1), (87601, 1)])
def test_invalid_review_thresholds_fail_closed(sparse, zeros):
    with pytest.raises(ValueError):
        review_candidates(meter([1, 2]), {}, sparse_hours=sparse, zero_review_days=zeros)
