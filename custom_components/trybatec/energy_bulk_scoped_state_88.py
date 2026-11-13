"""#88: assemble an atomic L7 plan from independently issued scoped L6 proofs.

Only an authenticated *server owner* may call this with #36/#37 native
envelopes and Energy preferences read from HA. The module is pure and is NOT
registered on WebSocket. It cannot mint an actual #36 immutable certificate
or guess a gap approval; the existing production collector does not supply
the required v2 proofs and thus cannot reach positive admission.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .energy_bulk_scoped_l6_88 import assess_scoped_selection_l6_88
from .energy_bulk_transaction import EnergyTransactionRefused, ServerEnergyState
from .energy_switch import preferences_fingerprint

_SCOPED_SCHEMA = "2026.11.1"
_UNITS = {"EF": "m³", "ECS": "m³", "CET": "kWh"}
_FIELDS = (
    "account_lot_verified", "unit_verified", "recorder_verified",
    "recorder_has_sum", "recorder_has_data", "historical_coverage_verified",
    "physical_meter_coverage_verified", "version_exclusivity_verified",
    "alternatives_complete", "energy_schema_verified",
)


def build_native_scoped_energy_state_88(
    preferences: dict[str, Any],
    native_proofs: list[Mapping[str, Any]],
    *,
    account: str,
    lot: str,
    schema_version: str,
) -> ServerEnergyState:
    """Verify *selected* v2 proof envelopes and build L7 candidates.

    These arguments must be collected inside the server: never call this on
    browser-submitted provenance/approval flags. Checks here enforce internal
    cross-owner consistency but cannot authenticate the *origin* of a fake
    pure Python mapping; only separately connected #36/#37 producers can.
    """
    if (schema_version != _SCOPED_SCHEMA
            or not isinstance(account, str) or not account
            or not isinstance(lot, str) or not lot
            or not isinstance(preferences, dict)
            or not isinstance(native_proofs, list)
            or not 1 <= len(native_proofs) <= 3):
        raise EnergyTransactionRefused("Native scoped plan prerequisites invalid")
    try:
        fingerprint = preferences_fingerprint(preferences)
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise EnergyTransactionRefused("Native Energy preferences invalid") from exc
    fluids: dict[str, dict[str, Any]] = {
        name: {"status": "not_selected", "reasons": []} for name in _UNITS
    }
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    reports = []
    for envelope in native_proofs:
        if not isinstance(envelope, Mapping):
            raise EnergyTransactionRefused("Malformed independent L6 envelope")
        choice = envelope.get("selection")
        if not isinstance(choice, Mapping):
            raise EnergyTransactionRefused("Trusted selected scope missing")
        fluid = choice.get("fluid")
        if (fluid not in _UNITS or fluid in seen
                or choice.get("account") != account or choice.get("lot") != lot):
            raise EnergyTransactionRefused("Wrong or duplicated selected fluid")
        seen.add(fluid)
        audit = envelope.get("energy_audit")
        if not isinstance(audit, Mapping):
            raise EnergyTransactionRefused("Native Energy source audit missing")
        try:
            if (preferences_fingerprint(audit["live"]) != fingerprint
                    or preferences_fingerprint(audit["persisted"]) != fingerprint):
                raise ValueError("Native audit does not match selected Energy version")
        except (KeyError, ValueError, TypeError, OverflowError) as exc:
            raise EnergyTransactionRefused(
                "Concurrent or foreign Energy preference version"
            ) from exc
        report = assess_scoped_selection_l6_88(
            choice, envelope.get("history_36"), envelope.get("lineage_37"),
            audit,
        )
        reports.append(deepcopy(dict(envelope)))
        if report["status"] != "eligible_for_scoped_review":
            fluids[fluid] = {"status": "blocked", "reasons": report["blockers"]}
            continue
        selected = choice["statistic_id"]
        alt = audit["alternative_ids"]
        if (not isinstance(alt, list) or selected not in alt
                or len(set(alt)) != len(alt)):
            fluids[fluid] = {
                "status": "blocked",
                "reasons": ["selected_version_alternatives_invalid"],
            }
            continue
        candidates.append({
            "account": account, "lot": lot, "fluid": fluid,
            "statistic_id": selected, "kind": "consolidated",
            "unit": _UNITS[fluid],
            "recorder_device_class": (
                "water" if fluid in ("EF", "ECS") else "energy"
            ),
            "competing_statistic_ids": [value for value in alt if value != selected],
            # This candidate is constructed by a trusted backend *only*
            # after reconciling independent v2 proofs. The flags remain
            # planner compatibility fields, not independent attestations.
            **dict.fromkeys(_FIELDS, True),
            "thermal_category_approved": False,
        })
        fluids[fluid] = {"status": "admissible", "reasons": []}
    if any(value["status"] == "blocked" for value in fluids.values()):
        # Bulk is atomic: never silently admit a subset after a refused fluid.
        candidates.clear()
    result = {
        "scoped_mode": "native_server_selected_scope_v2",
        "preferences_fingerprint": fingerprint,
        "fluids": fluids,
        "scoped_selections_v2": reports,
        "writes": False, "activation_authorized": False,
    }
    return ServerEnergyState(
        deepcopy(preferences), result, tuple(deepcopy(candidates)), schema_version,
    )
