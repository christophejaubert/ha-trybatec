"""Issue #37 -> #88: non-authoritative, read-only lineage evidence envelope.

Only a server-side collector may independently attest to complete portal coverage,
Recorder persistence and Energy preference exclusivity. This envelope never
authorizes activating or replacing Energy references.
"""
from __future__ import annotations

from hashlib import sha256
import json
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

MAX_GROUPS = 3000
MAX_ROWS = 100000


def _number(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, str):
        raise ValueError("Consumption evidence requires exact decimal strings")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal evidence") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("Invalid nonnegative finite consumption")
    return result


def prepare_energy_lineage_handoff_37(
    preview: Mapping[str, Any],
    *,
    account_scope_verified: bool = False,
) -> dict[str, Any]:
    """Describe retained physical contributions; never assert #88 admission.

    The boolean is *advisory*, not a trusted assertion. The #88 backend must
    independently compare trusted inventory, Recorder, versions and preferences.
    """
    if (not isinstance(preview, Mapping) or preview.get("writes") is not False
            or preview.get("energy_activation_authorized") is not False
            or preview.get("historical_inventory_proven_complete") is not False
            or preview.get("recorder_persistence_proven") is not False):
        raise ValueError("Input must be an unactivated #37 history bridge preview")
    inventory = preview.get("inventory")
    groups = preview.get("groups")
    if (not isinstance(inventory, list) or not isinstance(groups, list)
            or len(inventory) > MAX_GROUPS or len(groups) > MAX_GROUPS
            or len(inventory) != preview.get("meter_count")):
        raise ValueError("Malformed #37 physical inventory")
    identities = set()
    physical = {}
    for row in inventory:
        if not isinstance(row, Mapping):
            raise ValueError("Invalid inventory row")
        key = (row.get("lot"), row.get("fluid"), row.get("serial"))
        if any(not isinstance(v, str) or not v or len(v) > 128 for v in key) or key in identities:
            raise ValueError("Invalid or duplicate physical identity")
        identities.add(key)
        physical[key] = row
    rendered = []
    accounted = set()
    total_rows = 0
    for group in groups:
        if not isinstance(group, Mapping):
            raise ValueError("Invalid logical meter scope")
        lot, fluid = group.get("lot"), group.get("fluid")
        scoped = {k for k in physical if k[:2] == (lot, fluid)}
        if not scoped or (lot, fluid) in accounted:
            raise ValueError("Duplicate or foreign logical scope")
        accounted.add((lot, fluid))
        blocked = group.get("status") == "blocked_incomplete_physical_series"
        member_rows = group.get("physical_meters") if not blocked else []
        if not blocked:
            if not isinstance(member_rows, list) or {
                (row.get("lot", lot), row.get("fluid", fluid), row.get("serial"))
                for row in member_rows if isinstance(row, Mapping)
            } != scoped:
                raise ValueError("Logical series does not cover all physical meters")
        rows = group.get("rows")
        if not isinstance(rows, list):
            raise ValueError("Malformed consolidated consumption rows")
        if blocked and rows:
            raise ValueError("Blocked coverage must not provide consolidated rows")
        total_rows += len(rows)
        if total_rows > MAX_ROWS:
            raise ValueError("Excessive consolidated consumption rows")
        seen_days = set()
        cumulative = Decimal(0)
        contributions = set()
        for item in rows:
            if not isinstance(item, Mapping):
                raise ValueError("Invalid daily row")
            day = item.get("date")
            if not isinstance(day, str) or day in seen_days:
                raise ValueError("Invalid or duplicate daily date")
            seen_days.add(day)
            delta = _number(item.get("consumption"))
            cumulative += delta
            if _number(item.get("cumulative")) != cumulative:
                raise ValueError("Consolidated cumulative sum is inconsistent")
            members = item.get("contributors")
            if not isinstance(members, list) or not members:
                raise ValueError("Missing physical contribution provenance")
            daily_contributions = Decimal(0)
            seen_members = set()
            for contributor in members:
                if not isinstance(contributor, Mapping):
                    raise ValueError("Invalid physical contributor")
                key = (lot, fluid, contributor.get("serial"))
                if key not in scoped or key in seen_members or contributor.get("provenance") not in (
                    "measured", "mixed", "estimated_linear_confirmed"
                ):
                    raise ValueError("Unknown or duplicate physical contributor/provenance")
                seen_members.add(key)
                daily_contributions += _number(contributor.get("consumption"))
                contributions.add(key)
            if daily_contributions != delta:
                raise ValueError("Physical contributions do not conserve daily consumption")
        if not blocked and _number(group.get("total")) != cumulative:
            raise ValueError("Logical total differs from daily sums")
        all_blockers = sorted(set(group.get("blockers", [])))
        rendered.append({
            "lot": lot, "fluid": fluid,
            "physical_meters_observed": len(scoped),
            "retired_meter_count": sum(physical[k].get("status") == "depose" for k in scoped),
            "unknown_meter_count": sum(physical[k].get("status") == "inconnu" for k in scoped),
            "contributors_observed": len(contributions),
            "rows_observed": len(rows),
            "total": str(cumulative) if not blocked else None,
            "logical_id": group.get("logical_id") if not blocked else None,
            "blockers": sorted(set(all_blockers + (
                ["historical_series_incomplete"] if blocked else []
            ))),
            "physical_coverage_proven": False,
            "recorder_series_persisted": False,
            "energy_version_exclusivity_proven": False,
        })
    if accounted != {k[:2] for k in identities}:
        raise ValueError("Some physical scopes have no logical series")
    canonical = json.dumps(rendered, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return {
        "schema": "lineage_37_energy_handoff_v1",
        "mode": "read_only_non_authoritative",
        "account_scope_observed": account_scope_verified is True,
        "groups": rendered,
        "fingerprint": sha256(canonical.encode()).hexdigest(),
        "physical_inventory_complete": False,
        "recorder_persistence_verified": False,
        "competing_versions_exhausted": False,
        "energy_activation_authorized": False,
        "writes": False,
    }
