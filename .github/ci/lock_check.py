"""Verify complete pinned package inventories in isolated CI test environments.

Offline fail-closed check. Pins package versions, not distribution SHA256 hashes.
Intentionally excludes only pip / setuptools / wheel bootstrap distributions.
"""
from __future__ import annotations

from importlib import metadata
from pathlib import Path
import re
import sys

PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==([0-9][A-Za-z0-9_.!+~-]*)$")
BOOTSTRAP = {"pip", "setuptools", "wheel"}
MAX_PACKAGES = 400


def normalize(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def parse_snapshot(source: str) -> dict[str, str]:
    expected: dict[str, str] = {}
    for raw in source.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = PIN.fullmatch(line)
        if match is None:
            raise ValueError("Invalid lock constraint syntax")
        name = normalize(match.group(1))
        if name in BOOTSTRAP or name in expected:
            raise ValueError("Duplicate/bootstrap package in snapshot")
        expected[name] = match.group(2)
        if len(expected) > MAX_PACKAGES:
            raise ValueError("Unexpectedly large dependency snapshot")
    if not expected:
        raise ValueError("Empty dependency snapshot")
    return expected


def validate_inventory(expected: dict[str, str], installed: dict[str, str]) -> list[str]:
    issues: list[str] = []
    for name in sorted(set(expected) | set(installed)):
        if name in BOOTSTRAP:
            continue
        if name not in expected:
            issues.append("unexpected distribution: " + name)
        elif name not in installed:
            issues.append("missing distribution: " + name)
        elif installed[name] != expected[name]:
            issues.append("version mismatch: " + name)
    return issues


def actual_inventory() -> dict[str, str]:
    inventory: dict[str, str] = {}
    for distribution in metadata.distributions():
        display_name = distribution.metadata.get("Name")
        if not display_name:
            raise ValueError("Distribution missing name metadata")
        name = normalize(display_name)
        if name in inventory and inventory[name] != distribution.version:
            raise ValueError("More than one version installed: " + name)
        inventory[name] = distribution.version
    return inventory


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("Usage: lock_check.py constraints-file.txt", file=sys.stderr)
        return 2
    try:
        path = Path(args[0]).resolve(strict=True)
        if not path.is_file() or path.suffix != ".txt":
            raise ValueError("Expected one readable constraints .txt file")
        expected = parse_snapshot(path.read_text(encoding="utf-8"))
        errors = validate_inventory(expected, actual_inventory())
    except (OSError, UnicodeError, ValueError) as exc:
        print("Invalid dependency snapshot: " + str(exc), file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print("Dependency snapshot drift: " + error, file=sys.stderr)
        return 1
    print(f"Verified {len(expected)} CI dependency versions against snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
