"""#36 synthetic contract for assigning confirmed interval decisions to days.

Pure evidence *projection*, NOT an independent attestation of portal readings,
physical meter generations, Recorder persistence or Energy selection.
No raw index mutation, HA service, Store, Recorder, or Energy writes.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from typing import Any, Mapping

from .history_smoothing_store import validate_choice

_KEY = re.compile(r"^[0-9a-f]{32}$")
_SOURCE = re.compile(r"^[0-9a-f]{64}$")
_EPS = Decimal("0.000001")


def _amount(value: Any) -> Decimal:
    if type(value) not in (int, float, Decimal):
        raise ValueError("Non-numeric day consumption")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid consumption") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("Negative or non-finite consumption")
    return result


def project_interval_day_decisions(
    *,
    interval_key: str,
    source_fingerprint: str,
    confirmed_choice: Mapping[str, Any],
    reconstruction_preview: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind each supplied day to an explicit decision without fabricating cause.

    The caller must independently validate that preview/interval_key derive
    from the exact current raw source. The result deliberately asserts no
    independent supplier/lineage/admissibility proof.
    """
    if not isinstance(interval_key, str) or not _KEY.fullmatch(interval_key):
        raise ValueError("Invalid source-bound interval key")
    if not isinstance(source_fingerprint, str) or not _SOURCE.fullmatch(source_fingerprint):
        raise ValueError("Invalid source fingerprint")
    choice = validate_choice(dict(confirmed_choice))
    report = reconstruction_preview
    if not isinstance(report, Mapping) or (
        report.get("status") != "preview_only_not_authorized_for_import"
        or report.get("mode") != choice["mode"]
        or report.get("origin") not in ("observed", "estimated_confirmed")
    ):
        raise ValueError("Unconfirmed or mismatched reconstruction")
    try:
        first = date.fromisoformat(report["start_date"])
        last = date.fromisoformat(report["end_date"])
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError("Missing interval calendar bounds") from exc
    day_count = (last - first).days
    if not 1 <= day_count <= 3660:
        raise ValueError("Invalid interval duration")
    allocations = report.get("allocations")
    if not isinstance(allocations, list) or len(allocations) > day_count:
        raise ValueError("Invalid bounded daily allocations")
    measured, estimated = Decimal(0), Decimal(0)
    assigned = set()
    proof = []
    for row in allocations:
        if not isinstance(row, Mapping) or set(row) != {
            "date", "quantity", "provenance"
        }:
            raise ValueError("Invalid day provenance fields")
        try:
            day = date.fromisoformat(row["date"])
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError("Invalid daily date") from exc
        if not first < day <= last or day in assigned:
            raise ValueError("Duplicate or out-of-range calendar day")
        assigned.add(day)
        value = _amount(row["quantity"])
        label = row["provenance"]
        if label == "measured":
            measured += value
        elif label == "estimated_linear" and choice["mode"] == "linear":
            estimated += value
        else:
            raise ValueError("Unsupported or unjustified day provenance")
        token = json.dumps(
            [interval_key, source_fingerprint, choice, day.isoformat(),
             str(value), label, report["origin"]],
            sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        )
        proof.append({
            "date": day.isoformat(),
            "quantity": float(value),
            "provenance": label,
            "is_estimate": label == "estimated_linear",
            "interval_origin_reason": (
                "unknown" if choice["reason"] == "undetermined_confirmed"
                else choice["reason"]
            ),
            "interval_reason_was_explicitly_confirmed": True,
            "estimated_initial_bound_not_supplier_reading": (
                report["origin"] == "estimated_confirmed"
            ),
            "day_decision_fingerprint": sha256(token.encode("utf-8")).hexdigest(),
        })
    if proof != sorted(proof, key=lambda d: d["date"]):
        raise ValueError("Allocations must follow calendar order")
    expected_measured = _amount(report.get("measured_total"))
    expected_estimated = _amount(report.get("estimated_total"))
    unallocated = _amount(report.get("unallocated_total"))
    total = _amount(report.get("total"))
    if (abs(measured - expected_measured) > _EPS
            or abs(estimated - expected_estimated) > _EPS
            or abs(total - measured - estimated - unallocated) > _EPS):
        raise ValueError("Reconstruction daily totals do not conserve raw interval")
    missing = sorted({
        (first + timedelta(days=i)).isoformat() for i in range(1, day_count + 1)
    } - {d["date"] for d in proof})
    return {
        "schema": "history_36_interval_day_decisions_v1",
        "mode": "synthetic_projection_read_only",
        "interval_key": interval_key,
        "source_fingerprint": source_fingerprint,
        "method": choice["mode"],
        "decision_reason": choice["reason"],
        "explicit_unknown_origin": choice["reason"] == "undetermined_confirmed",
        "estimated_initial_bound_not_supplier_reading": (
            report["origin"] == "estimated_confirmed"
        ),
        "daily": proof,
        "missing_days": missing,
        "measured_total": float(measured),
        "estimated_total": float(estimated),
        "unallocated_total": float(unallocated),
        "raw_interval_total": float(total),
        "supplier_observations_independently_attested": False,
        "physical_lineage_independently_attested": False,
        "recorder_persistence_attested": False,
        "energy_activation_authorized": False,
        "recorder_writes": False,
        "energy_writes": False,
    }
