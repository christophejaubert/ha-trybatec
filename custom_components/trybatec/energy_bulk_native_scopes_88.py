"""#88: authentic read-only selected-scope HA/Recorder/lineage inventory.

This collector reads *existing native evidence* and never upgrades partial
B15 v1 history to an immutable per-attempt #36 certificate or claims total
supplier completeness. It cannot by itself make an Energy source eligible.
No browser-provided serial, evidence, ID, date or approval enters this path.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from hashlib import sha256
from typing import Any

from .const import DOMAIN
from .energy_bulk_evidence_ha import (
    _energy_without_initializing, _meter_rows, _read_store_data,
)
from .energy_switch import _selected_references, preferences_fingerprint
from .energy_bulk_transaction import EnergyTransactionRefused

_FLUIDS = ("EF", "ECS", "CET")
_UNITS = {"EF": "m³", "ECS": "m³", "CET": "kWh"}
_MAX_SERIES = 300
_MAX_VERSIONS = 500


def _ledger_scoped_summary(ledger: Any, lot: str) -> dict[str, dict[str, Any]]:
    """Only bound, validated B15 version evidence; never issue a v2 permit."""
    result = {
        fluid: {
            "status": "blocked", "reasons": [],
            "known_versions": 0, "verified_versions": 0,
            "quarantined_attempts": 0, "meter_generations_observed": 0,
            "metadata_verified": False, "selected_statistic_id": None,
            "known_generation_ids": [], "native_attempts": {},
        } for fluid in _FLUIDS
    }
    if (not isinstance(ledger, dict) or ledger.get("schema") != 1
            or not isinstance(ledger.get("series"), dict)
            or len(ledger["series"]) > _MAX_SERIES
            or not isinstance(ledger.get("pending", {}), dict)):
        for item in result.values():
            item["reasons"].append("native_recorder_ledger_missing_or_invalid")
        return result
    # A ledger is scoped to one authenticated account, but contains multiple
    # lots. A reused statistic ID in another lot is still a collision.
    global_ids = []
    for record in ledger["series"].values():
        if not isinstance(record, dict) or not isinstance(record.get("versions"), list):
            for item in result.values():
                item["reasons"].append("cross_lot_version_ledger_invalid")
            return result
        for version in record["versions"]:
            if not isinstance(version, dict):
                for item in result.values():
                    item["reasons"].append("cross_lot_version_ledger_invalid")
                return result
            if isinstance(version.get("statistic_id"), str):
                global_ids.append(version["statistic_id"])
    if len(global_ids) != len(set(global_ids)):
        for item in result.values():
            item["reasons"].append("statistic_id_reused_across_account_lots")

    physical = Counter()
    consolidated: dict[str, list[tuple[str, dict[str, Any], dict[str, Any]]]] = {
        fluid: [] for fluid in _FLUIDS
    }
    every_id: set[str] = set()
    for logical, record in ledger["series"].items():
        if (not isinstance(logical, str) or not isinstance(record, dict)
                or not isinstance(record.get("scope"), dict)
                or not isinstance(record.get("versions"), list)):
            for item in result.values():
                item["reasons"].append("native_recorder_ledger_scope_invalid")
            return result
        scope = record["scope"]
        if scope.get("lot") != lot:
            continue
        fluid, kind = scope.get("fluid"), scope.get("kind")
        if fluid not in _FLUIDS or kind not in ("physical", "consolidated"):
            for item in result.values():
                item["reasons"].append("native_recorder_ledger_scope_invalid")
            return result
        if record.get("unit") != _UNITS[fluid]:
            result[fluid]["reasons"].append("native_recorder_unit_mismatch")
        versions = record["versions"]
        if len(versions) > _MAX_VERSIONS:
            result[fluid]["reasons"].append("native_recorder_version_inventory_unbounded")
            continue
        for version in versions:
            stat = version.get("statistic_id") if isinstance(version, dict) else None
            state = version.get("state") if isinstance(version, dict) else None
            if (not isinstance(stat, str) or not stat.startswith("trybatec:")
                    or len(stat) > 256 or stat in every_id
                    or state not in (
                        "prepared", "imported", "verified", "active", "archived",
                        "quarantined", "abandoned",
                    )
                    or type(version.get("number")) is not int
                    or version["number"] < 1
                    or type(version.get("rows")) is not int
                    or version["rows"] < 1
                    or any(
                        not isinstance(version.get(field), str)
                        or len(version[field]) != 64
                        or any(c not in "0123456789abcdef" for c in version[field])
                        for field in ("snapshot_hash", "source_fingerprint")
                    )):
                result[fluid]["reasons"].append("native_recorder_version_id_or_state_invalid")
                continue
            every_id.add(stat)
            result[fluid]["known_versions"] += 1
            if state in ("verified", "active"):
                result[fluid]["verified_versions"] += 1
            if state in ("quarantined", "abandoned"):
                result[fluid]["quarantined_attempts"] += 1
        if kind == "physical":
            serial = scope.get("serial")
            if not isinstance(serial, str) or not serial:
                result[fluid]["reasons"].append("native_physical_generation_identity_missing")
            else:
                physical[(fluid, serial)] += 1
        else:
            consolidated[fluid].append((logical, record, scope))
    for fluid, row in result.items():
        row["known_generation_ids"] = sorted(
            serial for (f, serial) in physical if f == fluid
        )
        row["meter_generations_observed"] = len(row["known_generation_ids"])
        if any(count > 1 for (f, _), count in physical.items() if f == fluid):
            row["reasons"].append("physical_generation_scope_duplicated")
        groups = consolidated[fluid]
        if len(groups) != 1:
            row["reasons"].append("consolidated_series_not_unique_in_scope")
            continue
        logical, record, _scope = groups[0]
        versions = record["versions"]
        selected = [
            v for v in versions
            if isinstance(v, dict) and v.get("state") in ("verified", "active")
        ]
        if len(selected) != 1:
            row["reasons"].append("selected_version_not_unique_or_unverified")
            continue
        candidate = selected[0]
        if logical in ledger["pending"]:
            row["reasons"].append("native_recorder_import_unresolved")
        if any(v.get("state") in ("prepared", "imported")
               for v in versions if isinstance(v, dict)):
            row["reasons"].append("native_recorder_attempt_pending")
        row["selected_statistic_id"] = candidate["statistic_id"]
        row["reasons"].append("immutable_attempt_proof_and_full_bucket_readback_missing")
    return result


def _selected_intents(
    selections: Any, groups: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Validate browser *intent* only against already observed server IDs.

    This must not interpret a selected scope, date or user flag as approval,
    physical coverage, Recorder persistence or global history completeness.
    """
    if selections is None:
        return {}
    if not isinstance(selections, list) or len(selections) > len(_FLUIDS):
        raise EnergyTransactionRefused("Invalid bounded Energy scope selection")
    output = {}
    for item in selections:
        if not isinstance(item, dict) or set(item) != {
            "fluid", "start", "end", "statistic_id", "generation_ids",
        }:
            raise EnergyTransactionRefused("Malformed Energy selection intent")
        fluid = item["fluid"]
        if fluid not in _FLUIDS or fluid in output:
            raise EnergyTransactionRefused("Duplicate or unknown selected fluid")
        row = groups[fluid]
        try:
            first, last = date.fromisoformat(item["start"]), date.fromisoformat(item["end"])
        except (ValueError, TypeError, KeyError) as exc:
            raise EnergyTransactionRefused("Invalid selected calendar range") from exc
        if (first.isoformat() != item["start"] or last.isoformat() != item["end"]
                or not 1 <= (last - first).days + 1 <= 3660):
            raise EnergyTransactionRefused("Selected historical window is unbounded")
        ids = item["generation_ids"]
        known = row["known_generation_ids"]
        attempt = row.get("native_attempts", {}).get(item["statistic_id"])
        valid_native = (
            isinstance(attempt, dict)
            and attempt.get("state") == "verified"
            and attempt.get("start") == first.isoformat()
            and attempt.get("end") == last.isoformat()
            and ids == attempt.get("generations")
        )
        valid_b15 = (
            row["selected_statistic_id"] is not None
            and item["statistic_id"] == row["selected_statistic_id"]
        )
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 300
                or any(not isinstance(v, str) or v not in known for v in ids)
                or len(set(ids)) != len(ids)
                or not (valid_native or valid_b15)):
            raise EnergyTransactionRefused(
                "Selected statistic or physical generation is not in native ledger"
            )
        output[fluid] = {
            "start": first.isoformat(), "end": last.isoformat(),
            "selected_generation_count": len(ids),
            "native_ledger_ids_match": True,
            "approval_and_daily_readback_verified": False,
            "native_attempt_already_verified": valid_native,
        }
    return output


async def _read_native_attempt_catalog_88(
    hass: Any, entry_id: str, lot: str,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Only validated on-disk #36 immutable attempts; never create/verify one."""
    from .history_recorder_native_attempt_36 import _validate_journal

    suffix = sha256(entry_id.encode("utf-8")).hexdigest()[:20]
    try:
        journal = await _read_store_data(
            hass, f"trybatec.history_attempts_36_{suffix}"
        )
    except FileNotFoundError:
        return {}
    states = _validate_journal(journal, entry_id)
    scoped: dict[str, dict[str, dict[str, Any]]] = {}
    for attempt in journal["attempts"]:
        scope = attempt["scope"]
        if scope["lot"] != lot:
            continue
        fluid = scope["fluid"]
        if (fluid not in _FLUIDS or scope["kind"] != "consolidated"
                or attempt["unit"] != _UNITS[fluid]):
            raise ValueError("Native #36 attempt has invalid scoped fluid/unit")
        serials = set()
        dates = []
        for day in attempt["daily"]:
            if not isinstance(day, dict) or not isinstance(day.get("contributions"), list):
                raise ValueError("Missing source-bound physical generation")
            dates.append(day.get("date"))
            for contribution in day["contributions"]:
                if not isinstance(contribution, dict):
                    raise ValueError("Invalid source-bound physical contribution")
                serial = contribution.get("serial")
                if not isinstance(serial, str) or not serial:
                    raise ValueError("Missing source-bound physical identity")
                serials.add(serial)
        if not dates or any(not isinstance(v, str) for v in dates):
            raise ValueError("Native attempt period unavailable")
        stat = attempt["statistic_id"]
        catalog = scoped.setdefault(fluid, {})
        if stat in catalog:
            raise ValueError("Duplicated native attempt statistic ID")
        catalog[stat] = {
            "state": states[stat], "generations": sorted(serials),
            "start": min(dates), "end": max(dates),
            "unit": attempt["unit"], "revision": attempt["revision"],
            "snapshot_hash": attempt["snapshot_hash"],
        }
    return scoped


async def async_read_recorder_metadata_88(
    hass: Any, statistic_id: str, *, fluid: str, unit: str,
) -> None:
    """Delegate to #36's strict native metadata reader, never a mock in HA."""
    from .history_recorder_b15 import _check_persisted_metadata

    await _check_persisted_metadata(
        hass, statistic_id, fluid=fluid, unit=unit,
    )


async def async_collect_native_scopes_88(
    hass: Any, coordinator: Any, *, actor: Any, lot: str,
    selections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Verify HA administrator, native account/lot, B15, Recorder and Energy.

    All disk reads are raw bounded read-only HA storage reads; no Store.load,
    provider scan, backup, write, initialization, or optimistic admission.
    """
    if not isinstance(getattr(actor, "id", None), str):
        raise PermissionError("Native authenticated HA administrator required")
    native = await hass.auth.async_get_user(actor.id)
    if native is None or native.id != actor.id or native.is_admin is not True:
        raise PermissionError("Native HA administrator authorization failed")
    entry = getattr(coordinator, "entry", None)
    if (entry is None or not isinstance(getattr(entry, "entry_id", None), str)
            or not isinstance(getattr(entry, "unique_id", None), str)
            or hass.data.get(DOMAIN, {}).get(entry.entry_id) is not coordinator
            or not isinstance(lot, str) or not lot or len(lot) > 128
            or not isinstance(getattr(coordinator, "data", None), dict)
            or not isinstance(coordinator.data.get("lots"), (list, tuple, set))
            or lot not in coordinator.data["lots"]):
        raise EnergyTransactionRefused("Selected native account or lot not present")
    facts = _meter_rows(coordinator)
    native_prefs = await _energy_without_initializing(hass)
    live, disk = native_prefs.get("live"), native_prefs.get("persisted")
    same_preferences = False
    selected_references: list[tuple[str, int, str, str]] = []
    if isinstance(live, dict) and isinstance(disk, dict):
        try:
            same_preferences = (
                preferences_fingerprint(live) == preferences_fingerprint(disk)
            )
            selected_references = _selected_references(live)
        except (ValueError, TypeError, KeyError, OverflowError):
            pass
    digest = sha256(entry.entry_id.encode("utf-8")).hexdigest()[:20]
    try:
        ledger = await _read_store_data(
            hass, f"trybatec.history_versions_b15_{digest}"
        )
        groups = _ledger_scoped_summary(ledger, lot)
    except (OSError, ValueError, KeyError, TypeError, FileNotFoundError):
        groups = _ledger_scoped_summary(None, lot)
    # #36 also owns a separate append-only one-shot attempt journal: B15
    # alone cannot identify these immutable per-revision statistic IDs.
    try:
        attempts = await _read_native_attempt_catalog_88(
            hass, entry.entry_id, lot,
        )
    except (OSError, ValueError, KeyError, TypeError, RuntimeError,
            ImportError):
        attempts = {}
        for group in groups.values():
            group["reasons"].append("native_36_attempt_catalog_unavailable")
    for fluid, journal_versions in attempts.items():
        group = groups[fluid]
        group["native_attempts"] = journal_versions
        group["native_attempt_versions_observed"] = len(journal_versions)
        group["quarantined_attempts"] += sum(
            v["state"] == "quarantined" for v in journal_versions.values()
        )
        group["known_generation_ids"] = sorted(set(
            group["known_generation_ids"]
        ).union(
            serial for v in journal_versions.values()
            for serial in v["generations"]
        ))
        group["meter_generations_observed"] = len(group["known_generation_ids"])
        if any(v["state"] in ("reserved", "enqueue_intent")
               for v in journal_versions.values()):
            group["reasons"].append("native_36_unresolved_attempt_exists")
        if (group["selected_statistic_id"] is not None
                and group["selected_statistic_id"] in journal_versions):
            group["reasons"].append(
                "statistic_id_reused_across_b15_and_native_attempt"
            )
    # Read #37's persisted retired-meter observations independently of
    # today's cache. A missing archive is unknown, not an empty inventory.
    retired: dict[str, Any] | None = None
    try:
        archive = await _read_store_data(
            hass, f"trybatec.b15_retired_inventory_{digest}"
        )
        if (isinstance(archive, dict) and archive.get("schema") == 1
                and isinstance(archive.get("meters"), dict)
                and len(archive["meters"]) <= _MAX_SERIES):
            retired = archive["meters"]
    except (OSError, ValueError, TypeError, KeyError, FileNotFoundError):
        pass

    meters = facts.get("items")
    for fluid, group in groups.items():
        if not same_preferences:
            group["reasons"].append("native_energy_memory_disk_not_equal")
        if not isinstance(meters, list):
            group["reasons"].append("native_observed_meters_unavailable")
        else:
            known = [row for row in meters
                     if isinstance(row, dict)
                     and row.get("lot") == lot and row.get("fluid") == fluid]
            group["observed_meters_in_loaded_cache"] = len(known)
            if any(row.get("identity_collision") for row in known):
                group["reasons"].append("native_meter_identity_collision")
            # The cache is observational; it cannot establish all-time
            # physical inventory or authenticate user-reviewed gaps.
        if retired is None:
            group["reasons"].append("native_retired_inventory_unavailable")
        else:
            known_retired = [
                item for item in retired.values()
                if isinstance(item, dict) and item.get("lot") == lot
                and item.get("fluid") == fluid and item.get("retired") is True
            ]
            group["retired_meters_observed_in_archive"] = len(known_retired)
            if any(not isinstance(item.get("serial"), str)
                   or not item["serial"] for item in known_retired):
                group["reasons"].append("native_retired_generation_identity_missing")
            # A physical ledger's count cannot independently certify that
            # all retired generations exist: report only observed comparisons.
            if group["meter_generations_observed"] < len(known_retired):
                group["reasons"].append("known_retired_generations_not_all_in_ledger")
        stat = group["selected_statistic_id"]
        if stat:
            if any(ref[3] == stat for ref in selected_references):
                group["reasons"].append("selected_version_already_in_energy")
            # Native Recorder metadata is a real observed fact, not proof of
            # the complete immutable series or an all-writer exclusion.
            try:
                await async_read_recorder_metadata_88(
                    hass, stat, fluid=fluid, unit=_UNITS[fluid],
                )
                group["metadata_verified"] = True
            except (ImportError, OSError, RuntimeError, TypeError,
                    ValueError, KeyError, AttributeError):
                group["reasons"].append("native_recorder_metadata_not_verified")
        group["reasons"] = sorted(set(group["reasons"]))
        group["status"] = "observed_not_admissible"
        # Metadata and an old ledger never certify approved selected days,
        # independent #37 selected generations or owner-unique immutable IDs.
        group["independent_36_37_v2_attested"] = False
    intents = _selected_intents(selections, groups)
    # When one immutable native attempt is explicitly selected, verify
    # each persisted SQL bucket and approval store, never mutate #36.
    if selections:
        from .energy_bulk_native_recorder_readback_88 import (
            async_read_verified_native_attempt_88,
        )
        for choice in selections:
            fluid, stat = choice["fluid"], choice["statistic_id"]
            if intents[fluid]["native_attempt_already_verified"]:
                try:
                    proof = await async_read_verified_native_attempt_88(
                        hass, entry.entry_id, stat,
                    )
                    if proof["rows_hash"] != (
                        groups[fluid]["native_attempts"][stat]["snapshot_hash"]
                    ):
                        raise ValueError("Native #36 content revision changed")
                    intents[fluid]["native_recorder_sql_readback_verified"] = True
                    intents[fluid]["native_attempt_selected_version_hash"] = (
                        proof["rows_hash"]
                    )
                except (OSError, ValueError, TypeError, RuntimeError, KeyError):
                    groups[fluid]["reasons"].append(
                        "selected_native_recorder_hourly_readback_failed"
                    )
                    intents[fluid]["native_recorder_sql_readback_verified"] = False
    # Do not expose physical serials or private ledger IDs in a compact UI
    # status response; only count and verified-match indicators.
    for fluid, group in groups.items():
        group["selection_intent"] = intents.get(fluid)
        group["known_generation_ids"] = []
        group["native_attempts"] = {}
        group["reasons"] = sorted(set(group["reasons"]))
    return {
        "schema": "energy_bulk_native_scopes_88_v1",
        "mode": "authenticated_native_read_only",
        "lot_bound": True, "account_bound": True,
        "energy_memory_disk_equal": same_preferences,
        "other_energy_references_observed": len(selected_references),
        "fluids": groups,
        "supplier_history_exhaustiveness_claimed": False,
        "activation_authorized": False, "writes": False,
    }
