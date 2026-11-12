"""L6 additional read-only B15/#37/#120 cross-checks; NEVER a write permit.

Inputs must be reconstructed inside a privileged HA backend, not from the UI.
The B15 ledger, retired inventory and current coordinator cache are not by
construction an exhaustive historical inventory. This module never claims one.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from .energy_bulk_evidence import _ledger_scopes

_FLUIDS = ("EF", "ECS", "CET")
_EXPECTED = {"EF": "m³", "ECS": "m³", "CET": "kWh"}
_MAX_METERS = 3000


def _digest(parts: Any) -> str:
    return sha256(json.dumps(parts, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _meter_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    key = row.get("lot"), row.get("fluid"), row.get("serial")
    if any(not isinstance(v, str) or not v or len(v) > 512 for v in key):
        raise ValueError("Invalid physical meter identity")
    if key[1] not in _FLUIDS:
        raise ValueError("Unsupported fluid")
    return key


def crosscheck_36_37_120(
    *, ledger: Mapping[str, Any] | None, retired: Mapping[str, Any] | None,
    observed: list[dict[str, Any]] | None, account: str, lot: str,
) -> dict[str, Any]:
    """Find contradictions; report missing proofs as UNKNOWN, never absent.

    Explicitly does not read Recorder or assert stable entity ownership. A
    verified B15 version state alone is insufficient evidence of persistency.
    """
    report: dict[str, Any] = {
        "mode": "energy_l6_historical_crosscheck",
        "writes": False, "activation_authorized": False,
        "complete": False, "admissible": False,
        "fluids": {f: {"status": "insufficient_evidence", "blockers": [],
                        "known_physical_meters": 0, "retired_meters": 0,
                        "consolidated_statistic": None} for f in _FLUIDS},
        "dependencies": ["#36_persisted_all_recorder_buckets", "#37_full_year_inventory",
                         "#120_stable_identity_without_migration", "historical_alternatives_inventory"],
    }
    if not isinstance(account, str) or not account.strip() or not isinstance(lot, str) or not lot.strip():
        raise ValueError("Server account and lot required")
    if not isinstance(ledger, Mapping):
        for f in _FLUIDS:
            report["fluids"][f]["blockers"].append("b15_ledger_unavailable")
        return report
    try:
        series, _ = _ledger_scopes(dict(ledger))
    except (ValueError, TypeError, OverflowError, KeyError):
        for f in _FLUIDS:
            report["fluids"][f]["status"] = "blocked"
            report["fluids"][f]["blockers"].append("invalid_b15_version_ledger")
        return report

    observed_keys: set[tuple[str, str, str]] = set()
    retired_keys: set[tuple[str, str, str]] = set()
    if observed is None or not isinstance(observed, list) or len(observed) > _MAX_METERS:
        for f in _FLUIDS:
            report["fluids"][f]["blockers"].append("current_meter_inventory_unknown")
    else:
        for row in observed:
            try:
                key = _meter_key(row)
                if key in observed_keys or type(row.get("retired")) is not bool:
                    raise ValueError("Duplicate or ambiguous physical meter")
                observed_keys.add(key)
                if row["retired"]:
                    retired_keys.add(key)
            except (TypeError, ValueError, AttributeError):
                for f in _FLUIDS:
                    report["fluids"][f]["status"] = "blocked"
                    report["fluids"][f]["blockers"].append("physical_identity_ambiguous")
                return report
    if retired is None or not isinstance(retired, Mapping) or retired.get("schema") != 1 or not isinstance(retired.get("meters"), dict) or len(retired["meters"]) > _MAX_METERS:
        for f in _FLUIDS:
            report["fluids"][f]["blockers"].append("retired_inventory_unavailable")
    else:
        for identifier, row in retired["meters"].items():
            try:
                key = _meter_key(row)
                expected_key = sha256(json.dumps([*key], separators=(",", ":")).encode()).hexdigest()[:48]
                if identifier != expected_key or row.get("retired") is not True:
                    raise ValueError("Archive ownership not independently proven")
                if key in retired_keys:
                    # Same physical meter in current cache and archive is normal.
                    continue
                retired_keys.add(key)
            except (TypeError, ValueError, AttributeError, KeyError, ImportError):
                for f in _FLUIDS:
                    report["fluids"][f]["status"] = "blocked"
                    report["fluids"][f]["blockers"].append("retired_inventory_identity_invalid")
                return report
    known = observed_keys | retired_keys
    for fluid in _FLUIDS:
        record = report["fluids"][fluid]
        physical = [s for s in series if s["scope"]["lot"] == lot and s["scope"]["fluid"] == fluid and s["scope"]["kind"] == "physical"]
        consolidated = [s for s in series if s["scope"]["lot"] == lot and s["scope"]["fluid"] == fluid and s["scope"]["kind"] == "consolidated"]
        members = {m for m in known if m[:2] == (lot, fluid)}
        ledger_members = { (lot, fluid, s["scope"]["serial"]) for s in physical }
        record["known_physical_meters"] = len(members)
        record["retired_meters"] = sum(m in retired_keys for m in members)
        if members - ledger_members:
            record["status"] = "blocked"
            record["blockers"].append("observed_or_retired_meter_missing_from_b15")
        if ledger_members - members:
            record["blockers"].append("b15_meter_not_in_bounded_inventory")
        if len(consolidated) > 1:
            record["status"] = "blocked"
            record["blockers"].append("multiple_logical_consolidations")
        elif len(consolidated) == 1:
            candidate = consolidated[0]
            selected = [v for v in candidate["versions"] if v["state"] in ("verified", "active")]
            if len(selected) != 1:
                record["status"] = "blocked"
                record["blockers"].append("ambiguous_persisted_version_selection")
            elif candidate["unit"] != _EXPECTED[fluid]:
                record["status"] = "blocked"
                record["blockers"].append("consolidation_unit_incompatible")
            else:
                record["consolidated_statistic"] = selected[0]["statistic_id"]
        else:
            record["blockers"].append("no_consolidated_history_in_b15")
        # No definitive exhaustive year scan, fingerprinted per-meter selection,
        # complete Recorder bucket readback or third-party variant check here.
        record["blockers"].append("historical_coverage_not_independently_attested")
        record["blockers"] = sorted(set(record["blockers"]))
    report["inventory_fingerprint"] = _digest([
        sorted(list(known)), sorted(retired_keys),
        [(r["logical_id"], r["scope"], r["unit"],
          [(v["statistic_id"], v["state"]) for v in r["versions"]]) for r in series],
    ])
    return report
