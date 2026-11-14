"""Explicit Trybatec-owned writer contract; never a universal HA write fence."""
from __future__ import annotations

from collections.abc import Mapping
import re

OWNED_MODE = "native_trybatec_owned_readback"
OWNED_STATE = "verified_trybatec_once"
OWNED_CONTRACT = "trybatec_owned_writers_v1"


def owned_recorder_contract_verified(proof: Mapping) -> bool:
    """Validate a server receipt's shape, not authenticate browser evidence.

    Only the native #36 producer may issue this receipt. Consumers still bind
    account, period, physical lineage, selection digest and exact SQL rows.
    """
    stat = proof.get("statistic_id")
    contract = proof.get("writer_contract")
    return (
        isinstance(stat, str)
        and re.fullmatch(r"trybatec:logical_[a-z0-9_]+_v[1-9][0-9]*_a[1-9][0-9]*_[0-9a-f]{32}", stat) is not None
        and proof.get("mode") == OWNED_MODE
        and proof.get("selected_version_state") == OWNED_STATE
        and proof.get("independent_future_writer_exclusion_verified") is False
        and isinstance(contract, Mapping)
        and contract.get("schema") == OWNED_CONTRACT
        and contract.get("scope") == "trybatec_owned_writers_only"
        and contract.get("external_writes_prevented") is False
        and contract.get("external_drift_policy") == "refuse_and_quarantine_no_repair"
        and all(contract.get(key) is True for key in (
            "durable_intent_before_enqueue", "once_only_enqueue",
            "stable_attempt_id_never_reused", "journal_disk_verified",
            "current_sql_readback_verified", "owned_catalog_verified",
        ))
        and isinstance(contract.get("journal_hash"), str)
        and re.fullmatch(r"[0-9a-f]{64}", contract["journal_hash"]) is not None
    )
