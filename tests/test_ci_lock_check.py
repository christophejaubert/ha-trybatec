"""Fail-closed regression tests for complete, version-pinned CI inventories."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / ".github/ci/lock_check.py"
SPEC = spec_from_file_location("trybatec_ci_lock_guard", PATH)
assert SPEC and SPEC.loader
LOCK = module_from_spec(SPEC)
SPEC.loader.exec_module(LOCK)


def test_checked_in_dependency_snapshots():
    names_and_minimums = (
        ("constraints-pure.txt", 16),
        ("constraints-lint.txt", 1),
        ("constraints-ha-runtime.txt", 100),
        ("constraints-ha-persistence.txt", 80),
    )
    for name, minimum in names_and_minimums:
        data = LOCK.parse_snapshot((PATH.parent / name).read_text(encoding="utf-8"))
        assert len(data) >= minimum


@pytest.mark.parametrize("invalid", [
    "", "pytest>=9.0", "pytest==9.0\npytest==9.1",
    "pip==26.0", "pytest==9.0 --index-url https://example.invalid",
    "https://example.invalid", "pytest==not_a_version",
])
def test_malformed_constraints_fail_closed(invalid):
    with pytest.raises(ValueError):
        LOCK.parse_snapshot(invalid)


def test_missing_extra_and_wrong_versions_detected():
    expected = LOCK.parse_snapshot("pytest==9.2.0\nattrs==26.1.0")
    assert LOCK.validate_inventory(expected, {
        "pytest": "9.2.0", "attrs": "26.1.0", "pip": "25.0"
    }) == []
    assert LOCK.validate_inventory(expected, {
        "pytest": "9.1.0", "unapproved": "1.0"
    }) == [
        "missing distribution: attrs",
        "version mismatch: pytest",
        "unexpected distribution: unapproved",
    ]


def test_normalization_matches_python_distribution_metadata():
    assert LOCK.normalize("pytest_homeassistant.custom-component") == "pytest-homeassistant-custom-component"
    assert LOCK.normalize("Jinja2") == "jinja2"
