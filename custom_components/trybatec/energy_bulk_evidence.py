"""L3 — fail-closed, server-side Energy bulk-enrollment evidence assessment.

Pure: no Home Assistant import, network call, storage, or mutation. Snapshots MUST
be built by the privileged, read-only server adapter, never from websocket
arguments or browser flags. Every result is evidence, NEVER apply permission.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any, Mapping

SUPPORTED_HA = "2026.11.1"
# Only these patch versions have been verified byte-identical for the used HA APIs.
SUPPORTED_HA_VERSIONS = frozenset({"2026.11.0", SUPPORTED_HA})
FLUIDS = {"EF": ("m³", "volume", "water"),
          "ECS": ("m³", "volume", "water"),
          "CET": ("kWh", "energy", "energy")}
MAX_METERS = 1500
MAX_SERIES = 1500
MAX_VERSIONS = 100
MAX_STAT_IDS = 500
MAX_BYTES = 1024 * 1024


def _hash_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         allow_nan=False, default=_no_json).encode("utf-8")
    if len(encoded) > MAX_BYTES:
        raise ValueError("Evidence snapshot exceeds size limit")
    return sha256(encoded).hexdigest()


def _no_json(value: Any) -> Any:
    raise TypeError("Evidence snapshot is not JSON safe")


def _ok_string(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 256 and bool(value.strip())


def _inventory(status: str, *, items: int = 0, complete: bool = False,
               reason: str | None = None) -> dict[str, Any]:
    return {"status": status, "observed": items, "complete": complete,
            "reason": reason}


def _ledger_scopes(ledger: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Enumerate *stored B15* series; do not imply this is all past history."""
    if not isinstance(ledger, dict) or ledger.get("schema") != 1:
        raise ValueError("Missing or incompatible B15 version ledger")
    raw = ledger.get("series")
    if not isinstance(raw, dict) or len(raw) > MAX_SERIES:
        raise ValueError("Invalid or truncated B15 series inventory")
    rows: list[dict[str, Any]] = []
    stat_ids: set[str] = set()
    for logical, series in raw.items():
        if not _ok_string(logical) or not logical.startswith("trybatec:logical_"):
            raise ValueError("Invalid B15 logical series identity")
        if not isinstance(series, dict) or not isinstance(series.get("scope"), dict):
            raise ValueError("B15 series scope absent")
        scope, versions = series["scope"], series.get("versions")
        if not isinstance(versions, list) or len(versions) > MAX_VERSIONS:
            raise ValueError("B15 versions missing or unbounded")
        if not versions:
            raise ValueError("Empty B15 version chain")
        if not _ok_string(scope.get("lot")) or not isinstance(scope.get("fluid"), str) or scope["fluid"] not in FLUIDS:
            raise ValueError("B15 series missing dwelling/fluid")
        if scope.get("kind") not in ("physical", "consolidated"):
            raise ValueError("Unknown B15 series kind")
        if scope["kind"] == "physical" and not _ok_string(scope.get("serial")):
            raise ValueError("Physical B15 meter lacks serial identity")
        if scope["kind"] == "consolidated" and scope.get("serial") is not None:
            raise ValueError("Consolidated B15 series cannot be physical")
        active = 0
        for index, v in enumerate(versions, 1):
            if (not isinstance(v, dict) or v.get("number") != index or
                v.get("state") not in ("prepared", "imported", "verified", "active", "archived") or
                not _ok_string(v.get("statistic_id")) or
                v["statistic_id"] != f"{logical}_v{index}" or
                not isinstance(v.get("snapshot_hash"), str) or
                not isinstance(v.get("source_fingerprint"), str)):
                raise ValueError("Invalid B15 version identity/state")
            if v["statistic_id"] in stat_ids:
                raise ValueError("Duplicate B15 statistic ID")
            stat_ids.add(v["statistic_id"])
            if v["state"] == "active":
                active += 1
        if active > 1:
            raise ValueError("Multiple active versions of one series")
        rows.append({"logical_id": logical, "scope": deepcopy(scope),
                     "unit": series.get("unit"), "versions": deepcopy(versions)})
    if len(stat_ids) > MAX_STAT_IDS:
        raise ValueError("Too many known B15 statistics for bounded audit")
    pending = ledger.get("pending", {})
    if not isinstance(pending, dict):
        raise ValueError("Invalid pending Recorder imports")
    return rows, sorted(stat_ids)


def assess_energy_evidence(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Inspect native read snapshots. Unknown is NEVER converted to True.

    `snapshot` is an internal server boundary, NOT a deserializable browser
    contract. Caller authenticates and constructs it from trusted HA readers.
    """
    result: dict[str, Any] = {
        "mode": "read_only_energy_evidence_l3",
        "status": "incomplete",
        "writes": False,
        "activation_authorized": False,
        "prepared_under_assertions": False,
        "blocked": True,
        "requires_trusted_backend_checks": True,
        "schema_version": None,
        "inventories": {}, "candidates": [], "blockers": [],
        "integration_ready": False,
    }
    if not isinstance(snapshot, Mapping) or snapshot.get("origin") != "ha_server_internal":
        result["blockers"].append("server_evidence_origin_unverified")
        return result

    scopes = result["inventories"]
    identity = snapshot.get("identity")
    current = snapshot.get("current_meters")
    ledger = snapshot.get("ledger")
    energy = snapshot.get("energy")
    recorder = snapshot.get("recorder")
    ha = snapshot.get("ha")
    boundary = snapshot.get("boundary")
    lot = snapshot.get("lot")

    if (not isinstance(identity, dict) or not _ok_string(identity.get("entry_id"))
        or not _ok_string(identity.get("account")) or
        not _ok_string(identity.get("deal_id")) or
        not _ok_string(lot) or identity.get("server_entry_matches") is not True or
        not isinstance(identity.get("lots"), list) or lot not in identity["lots"]):
        scopes["identity"] = _inventory("unverified", reason="account_lot_identity_unverified")
        result["blockers"].append("account_lot_identity_unverified")
        identity_ok = False
    else:
        identity_ok = True
        scopes["identity"] = _inventory("verified_current_scope", items=1, complete=True)

    meters: list[dict[str, Any]] = []
    if isinstance(current, dict) and isinstance(current.get("items"), list) and len(current["items"]) <= MAX_METERS:
        seen: set[tuple[str, str, str]] = set()
        metering_valid = True
        for row in current["items"]:
            if not isinstance(row, dict) or not isinstance(row.get("fluid"), str) or row["fluid"] not in FLUIDS or not _ok_string(row.get("lot")) or not _ok_string(row.get("serial")):
                metering_valid = False
                break
            key = (row["lot"], row["fluid"], row["serial"])
            if key in seen or type(row.get("retired")) is not bool:
                metering_valid = False
                break
            seen.add(key)
            meters.append(row)
        if metering_valid:
            scopes["physical_meters"] = _inventory(
                "observed_current_cache_only", items=len(meters), complete=False,
                reason="current_year_cache_is_not_all_historical_meters")
        else:
            scopes["physical_meters"] = _inventory("contradictory", reason="invalid_meter_identity")
            result["blockers"].append("invalid_meter_identity")
            meters = []
    else:
        scopes["physical_meters"] = _inventory("unverified", reason="meter_inventory_unavailable_or_truncated")
        result["blockers"].append("meter_inventory_unavailable_or_truncated")

    all_series: list[dict[str, Any]] = []
    if isinstance(ledger, dict) and ledger.get("error") is None:
        try:
            all_series, all_stat_ids = _ledger_scopes(ledger.get("data"))
            scopes["b15_versions"] = _inventory("b15_ledger_read", items=len(all_stat_ids), complete=True)
        except (ValueError, TypeError, OverflowError):
            scopes["b15_versions"] = _inventory("unverified", reason="ledger_invalid_or_incomplete")
            result["blockers"].append("ledger_invalid_or_incomplete")
    else:
        scopes["b15_versions"] = _inventory("unverified", reason="ledger_missing_or_read_failed")
        result["blockers"].append("ledger_missing_or_read_failed")

    # B15 ledger covers its own entries only. Legacy V4, entity-registry
    # references and unknown historical variants are NOT guaranteed present.
    legacy = snapshot.get("legacy_v5")
    if (isinstance(legacy, dict) and legacy.get("error") is None and
            isinstance(legacy.get("data"), dict) and
            isinstance(legacy["data"].get("series"), dict) and
            len(legacy["data"]["series"]) <= MAX_SERIES):
        scopes["legacy_v5"] = _inventory("known_v5_ledger_read",
            items=len(legacy["data"]["series"]), complete=False,
            reason="v5_scope_cannot_be_mapped_unambiguously_to_all_physical_meters")
    else:
        scopes["legacy_v5"] = _inventory("unverified", complete=False,
            reason="v5_ledger_missing_invalid_or_unavailable")
    scopes["historical_variants"] = _inventory(
        "partially_observed_b15_and_v5", items=len(all_series), complete=False,
        reason="legacy_and_future_versions_not_exhaustively_enumerated_or_scoped")
    scopes["retired_coverage"] = _inventory(
        "not_proven", complete=False,
        reason="no_verified_consolidation_to_all_physical_meters_link")

    prefs: dict[str, Any] | None = None
    if (isinstance(energy, dict) and isinstance(energy.get("live"), dict)
        and isinstance(energy.get("persisted"), dict)):
        try:
            from .energy_switch import _selected_references, preferences_fingerprint
            live = deepcopy(energy["live"])
            persisted = deepcopy(energy["persisted"])
            selected = _selected_references(live)
            if preferences_fingerprint(live) != preferences_fingerprint(persisted):
                raise ValueError("Live and persisted Energy preferences differ")
            prefs = live
            scopes["energy_preferences"] = _inventory("live_matches_persisted", items=len(selected), complete=True)
        except (ValueError, TypeError, KeyError, OverflowError):
            scopes["energy_preferences"] = _inventory("unverified", reason="energy_settings_unreadable_or_changed")
            result["blockers"].append("energy_settings_unreadable_or_changed")
    else:
        scopes["energy_preferences"] = _inventory("unverified", reason="energy_manager_or_persistence_unavailable")
        result["blockers"].append("energy_manager_or_persistence_unavailable")
    scopes["energy_references"] = _inventory(
        "known_fields_only" if prefs is not None else "unverified",
        items=scopes["energy_preferences"]["observed"], complete=False,
        reason="unknown_future_fields_and_other_consumers_not_exhaustively_proven")

    version = ha.get("version") if isinstance(ha, dict) else None
    result["schema_version"] = version
    if version in SUPPORTED_HA_VERSIONS and ha.get("energy_schema_checked") is True:
        scopes["ha_schema"] = _inventory("native_schema_checked", items=1, complete=True)
    else:
        scopes["ha_schema"] = _inventory("unverified", reason="ha_schema_version_or_validation_unverified")
        result["blockers"].append("ha_schema_version_or_validation_unverified")

    if not (isinstance(boundary, dict) and isinstance(boundary.get("before"), str)
            and len(boundary["before"]) == 64 and boundary.get("before") == boundary.get("after")):
        scopes["concurrency"] = _inventory("unverified", reason="source_changed_during_collection")
        result["blockers"].append("source_changed_during_collection")
    else:
        scopes["concurrency"] = _inventory("two_snapshots_identical", items=2, complete=True)

    if not isinstance(recorder, dict) or recorder.get("complete") is not True or not isinstance(recorder.get("metadata"), dict) or not isinstance(recorder.get("samples"), dict):
        scopes["recorder"] = _inventory("unverified", reason="recorder_read_failed_or_truncated")
        result["blockers"].append("recorder_read_failed_or_truncated")
        recorder = {"metadata": {}, "samples": {}}
    else:
        scopes["recorder"] = _inventory("bounded_metadata_and_samples", items=len(recorder["metadata"]), complete=False,
            reason="persisted_sample_is_not_full_historical_coverage")

    target_rows = [s for s in all_series if s["scope"]["lot"] == lot and s["scope"]["kind"] == "consolidated"]
    for fluid in FLUIDS:
        matches = [series for series in target_rows if series["scope"]["fluid"] == fluid]
        if not matches:
            continue  # No implicit candidate for a fluid never recorded.
        row = {"account": identity.get("account") if isinstance(identity, dict) else None,
               "lot": lot, "fluid": fluid, "status": "unverified", "blockers": []}
        if len(matches) != 1:
            row["blockers"].append("multiple_consolidated_logical_series")
            result["candidates"].append(row)
            continue
        series = matches[0]
        eligible = [v for v in series["versions"] if v["state"] in ("verified", "active")]
        # Do not pick 'last' if there are multiple equally valid choices.
        if len(eligible) != 1:
            row["blockers"].append("one_verified_consolidated_version_not_selected")
            result["candidates"].append(row)
            continue
        target = eligible[0]
        stat_id = target["statistic_id"]
        expected_unit, expected_class, _class_alias = FLUIDS[fluid]
        meta = recorder["metadata"].get(stat_id) if isinstance(recorder["metadata"], dict) else None
        sample = recorder["samples"].get(stat_id) if isinstance(recorder["samples"], dict) else None
        row.update({"statistic_id": stat_id,
                    "unit": series["unit"],
                    "recorder_unit": meta.get("unit_of_measurement") if isinstance(meta, dict) else None,
                    "recorder_unit_class": meta.get("unit_class") if isinstance(meta, dict) else None,
                    "recorder_has_sum": meta.get("has_sum") if isinstance(meta, dict) else None,
                    "persisted_sample_observed": sample is True,
                    "known_b15_alternatives": sorted({v["statistic_id"] for s in all_series
                        if s["scope"]["lot"] == lot and s["scope"]["fluid"] == fluid for v in s["versions"]})})
        if not identity_ok:
            row["blockers"].append("account_lot_identity_unverified")
        if series["unit"] != expected_unit or not isinstance(meta, dict) or meta.get("unit_of_measurement") != expected_unit:
            row["blockers"].append("unit_unverified_or_incompatible")
        if not isinstance(meta, dict) or meta.get("unit_class") != expected_class:
            row["blockers"].append("recorder_class_unverified_or_incompatible")
        if not isinstance(meta, dict) or meta.get("has_sum") is not True:
            row["blockers"].append("recorder_sum_not_proven")
        if sample is not True:
            row["blockers"].append("recorder_persisted_rows_not_proven")
        # Observed meter properties remain limited to the current cache.
        # A serial reused across physical scopes needs #81's stable identity.
        observed_fluid = [m for m in meters if m["lot"] == lot and m["fluid"] == fluid]
        if any(m.get("identity_collision") is True for m in observed_fluid):
            row["blockers"].append("physical_identity_collision_unresolved")
        valid_source_units = ("m³", "L") if fluid in ("EF", "ECS") else ("kWh", "MWh", "GJ")
        if any(m.get("verified_unit") is None for m in observed_fluid):
            row["blockers"].append("observed_physical_unit_not_verified")
        if any(m.get("verified_unit") is not None and
               m["verified_unit"] not in valid_source_units for m in observed_fluid):
            row["blockers"].append("observed_physical_unit_incompatible")
        retired_seen = {
            (m["lot"], m["fluid"], m["serial"])
            for m in meters if m.get("retired") is True
        }
        physical_b15 = {
            (s["scope"]["lot"], s["scope"]["fluid"], s["scope"]["serial"])
            for s in all_series if s["scope"]["kind"] == "physical"
        }
        if any(m[0] == lot and m[1] == fluid and m not in physical_b15
               for m in retired_seen):
            row["blockers"].append("known_retired_meter_missing_from_b15_ledger")
        # Deliberately never grant these assertions from the current cache or
        # B15 version ledger alone. #36/#37/#81 must provide durable proof.
        row["blockers"].extend(("full_physical_meter_coverage_unverified",
                                "full_historical_coverage_unverified",
                                "alternatives_and_references_incomplete"))
        if fluid == "CET":
            row["blockers"].append("thermal_category_approval_not_proven")
        if prefs is None:
            row["blockers"].append("energy_preferences_unverified")
        else:
            from .energy_bulk_plan import _find_reference_paths
            competing = set(row["known_b15_alternatives"])
            matches_prefs = _find_reference_paths(prefs, competing)
            if matches_prefs:
                row["energy_references"] = matches_prefs
                if any(ref_id != stat_id for ref_id, _path in matches_prefs):
                    row["blockers"].append("competing_energy_statistic_already_selected")
                if len(matches_prefs) > 1:
                    row["blockers"].append("duplicate_energy_references")
        row["status"] = "refused_pending_independent_proofs"
        result["candidates"].append(row)

    if not result["candidates"]:
        result["blockers"].append("no_verified_consolidated_candidates_in_ledger")
    # These missing guarantees are universal to the current L3 data sources.
    result["blockers"].extend(("full_historical_coverage_unverified",
                               "full_physical_meter_coverage_unverified",
                               "alternatives_and_references_incomplete"))
    result["blockers"] = sorted(set(result["blockers"]))
    result["status"] = "blocked"
    return result


def preview_bulk_with_l3_evidence(
    evidence: Mapping[str, Any], preferences: dict[str, Any],
) -> dict[str, Any]:
    """L3-to-#92 diagnostic handoff, deliberately incapable of activation.

    Never use evidence returned to a browser as input to this function. It is
    intended for a future admin-only server handler with fresh native reads.
    Current physical/history/alternatives sources are incomplete, so their
    proof flags stay False even if a caller sends an apparent 'verified' flag.
    """
    from .energy_bulk_plan import preview_bulk_energy_insertion

    if not isinstance(evidence, Mapping) or evidence.get("mode") != "read_only_energy_evidence_l3":
        raise ValueError("L3 server evidence is required")
    if not isinstance(preferences, dict):
        raise ValueError("Live Energy preferences are required")
    items = []
    for row in evidence.get("candidates", []):
        if (not isinstance(row, dict) or not _ok_string(row.get("account"))
                or not _ok_string(row.get("lot"))
                or row.get("fluid") not in FLUIDS
                or not _ok_string(row.get("statistic_id"))):
            continue
        fluid = row["fluid"]
        expected_unit, expected_class, planner_class = FLUIDS[fluid]
        items.append({
            "account": row["account"], "lot": row["lot"],
            "fluid": fluid, "kind": "consolidated",
            "statistic_id": row["statistic_id"], "unit": row.get("unit"),
            "recorder_device_class": (
                planner_class if row.get("recorder_unit_class") == expected_class
                else None
            ),
            # Local observations may substantiate individual points, but
            # never certify the incomplete historical/variant inventory.
            "account_lot_verified": evidence.get("inventories", {}).get("identity", {}).get("complete") is True,
            "unit_verified": row.get("unit") == expected_unit and row.get("recorder_unit") == expected_unit,
            "recorder_verified": row.get("persisted_sample_observed") is True,
            "recorder_has_sum": row.get("recorder_has_sum") is True,
            "recorder_has_data": row.get("persisted_sample_observed") is True,
            "historical_coverage_verified": False,
            "physical_meter_coverage_verified": False,
            "version_exclusivity_verified": False,
            "alternatives_complete": False,
            "energy_schema_verified": False,
            "thermal_category_approved": False,
            "competing_statistic_ids": list(row.get("known_b15_alternatives", [])),
        })
    plan = preview_bulk_energy_insertion(
        deepcopy(preferences), items, schema_version=evidence.get("schema_version")
    )
    # Treat any unexpected change in the preflight contract as a hard failure.
    if (plan.get("proposal_status") != "blocked"
            or plan.get("proposed") != plan.get("previous")
            or plan.get("activation_authorized") is not False
            or plan.get("writes") is not False):
        raise ValueError("L3 may not prepare or activate Energy insertion")
    return plan
