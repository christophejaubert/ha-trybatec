"""Contract tests for CI-only advisory reporting, not security certification."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location("trybatec_security_audit", ROOT / "scripts/ci_supply_chain_audit.py")
assert SPEC is not None and SPEC.loader is not None
AUDIT = module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_valid_and_invalid_pip_audit_reports():
    valid = {"dependencies": [
        {"name": "pytest", "version": "9.2.0", "vulns": []},
        {"name": "bad-lib", "version": "1.0", "vulns": [{"id": "PYSEC-example"}]},
    ]}
    assert AUDIT.parse_findings(json.dumps(valid))[1] == 1
    for invalid in ({}, [], {"dependencies": {}},
                    {"dependencies": [{"name": "bad/lib", "vulns": []}]},
                    {"dependencies": [{"name": "lib", "vulns": 42}]}):
        with pytest.raises((ValueError, TypeError)):
            AUDIT.parse_findings(json.dumps(invalid))


def test_safety_bounds_and_fixed_inventory_names():
    assert len(AUDIT.FILES) == 5
    assert ".github/ci/constraints-audit.txt" in AUDIT.FILES
    assert all(name.startswith(".github/ci/constraints-") for name in AUDIT.FILES)
    assert AUDIT.MAX_OUTPUT <= 6 * 1024 * 1024
    assert AUDIT.MAX_FINDINGS <= 1200


def test_missing_ci_context_refuses_execution(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert AUDIT.main(["dependencies"]) == 2
    assert AUDIT.main(["workflows"]) == 2


def test_scan_failures_are_not_misclassified_as_clean(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    monkeypatch.setattr(AUDIT, "run_command", lambda args, timeout=180: (2, "", "error"))
    assert AUDIT.main(["workflows"]) == 1


def test_zizmor_advisory_findings_are_visible(monkeypatch, capsys):
    monkeypatch.setattr(AUDIT, "run_command",
                        lambda args, timeout=180: (14, "::warning file=a.yml::finding", ""))
    assert AUDIT.audit_workflows() == 0
    out = capsys.readouterr().out
    assert "finding" in out and "exit 14" in out
