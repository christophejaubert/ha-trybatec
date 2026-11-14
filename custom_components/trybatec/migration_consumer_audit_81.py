"""Bounded read-only reference scanner for issue #81 migration evidence.

This is a diagnostic tool, not an attestation that all third-party
consumers have been inventoried. It is never registered as a HA action,
and its output cannot unlock the one-time migration executor.
Only synthetic fixtures belong in tests or public documentation.
"""
from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

IDENTIFIER_TYPES = ("entity_id", "unique_id", "device_id", "statistic_id")
SURFACES = (
    "entity_registry", "device_registry", "recorder", "energy",
    "automations", "scripts", "scenes", "dashboards",
    "groups", "config_entries", "other_integrations", "third_party",
)
_MAX_TARGETS = 5000
_MAX_NODES_PER_SURFACE = 200_000
_MAX_RESULTS = 2000
_MAX_DEPTH = 64


def scan_consumer_snapshots(
    targets: Mapping[str, list[str]],
    snapshots: Mapping[str, Any],
) -> dict[str, Any]:
    """Return opaque locations of observed references, never a permit.

    Caller supplies independently retrieved read-only snapshots. The absence
    of an identifier in any snapshot is not evidence that a consumer cannot
    reference it outside the snapshot. Completeness is ALWAYS false,
    regardless of caller-supplied values or flags.
    Paths use numbered mapping keys so private values/keys cannot leak.
    """
    if not isinstance(targets, Mapping) or not isinstance(snapshots, Mapping):
        raise ValueError("Invalid consumer audit input")
    if set(targets) != set(IDENTIFIER_TYPES) or any(
        not isinstance(rows, list) or not rows for rows in targets.values()
    ):
        raise ValueError("All four identifier classes require exact targets")
    tokens: list[tuple[str, str, str, re.Pattern[str]]] = []
    total = 0
    for kind in IDENTIFIER_TYPES:
        values = targets[kind]
        if any(not isinstance(value, str) or not value or len(value) > 512
               or value != value.strip() for value in values):
            raise ValueError("Invalid reference target")
        if len(values) != len(set(values)):
            raise ValueError("Duplicate reference targets")
        for idx, value in enumerate(values):
            total += 1
            if total > _MAX_TARGETS:
                raise ValueError("Reference target inventory exceeds limit")
            # Exact identifier boundaries, even inside JSON or Jinja,
            # but never a prefix of another ID ending in _2.
            pattern = re.compile(
                r"(?<![A-Za-z0-9_.-])" + re.escape(value)
                + r"(?![A-Za-z0-9_.-])"
            )
            tokens.append((kind, f"{kind}:{idx + 1}", value, pattern))

    if set(snapshots) - set(SURFACES):
        raise ValueError("Unknown audit surface")
    results: list[dict[str, str]] = []
    inspected: list[str] = []
    unknown: list[str] = []
    overflow: list[str] = []
    for surface in SURFACES:
        if surface not in snapshots or snapshots[surface] is None:
            unknown.append(surface)
            continue
        inspected.append(surface)
        visited = 0
        stack: list[tuple[Any, str, int]] = [(snapshots[surface], "$", 0)]
        truncated = False
        while stack:
            node, path, depth = stack.pop()
            visited += 1
            if visited > _MAX_NODES_PER_SURFACE or depth > _MAX_DEPTH:
                truncated = True
                break
            if isinstance(node, Mapping):
                if len(node) > _MAX_NODES_PER_SURFACE:
                    truncated = True
                    break
                for i, (key, value) in enumerate(node.items()):
                    stack.append((value, f"{path}.v{i}", depth + 1))
                    if isinstance(key, str):
                        stack.append((key, f"{path}.k{i}", depth + 1))
            elif isinstance(node, (list, tuple)):
                if len(node) > _MAX_NODES_PER_SURFACE:
                    truncated = True
                    break
                for i, value in enumerate(node):
                    stack.append((value, f"{path}[{i}]", depth + 1))
            elif isinstance(node, str):
                for kind, target, exact, pattern in tokens:
                    if pattern.search(node):
                        results.append({
                            "surface": surface, "kind": kind,
                            "target": target, "path": path,
                            "match": "exact" if node == exact else "embedded",
                        })
                        if len(results) >= _MAX_RESULTS:
                            truncated = True
                            break
                if truncated:
                    break
        if truncated:
            overflow.append(surface)
    return {
        "status": "read_only_incomplete_external_dependency_audit",
        "surfaces_inspected": inspected,
        "surfaces_unavailable": unknown,
        "surfaces_truncated": overflow,
        "matches": results,
        "matched_reference_count": len(results),
        "absence_of_matches_is_not_proof": True,
        "dependency_inventory_complete": False,
        "safe_to_apply": False,
        "writes_performed": False,
    }
