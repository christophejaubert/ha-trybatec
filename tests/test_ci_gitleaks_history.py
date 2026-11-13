"""Non-secret, read-only security contract checks for scheduled/PR/push scanning.

FR : ne pas divulguer la valeur de l'UUID de test.
EN: do not expose the original fixture UUID.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FINGERPRINT = (
    "5bb9d8d120c44693806117d4387760f447a3a328:"
    "integration_tests/test_panel_options_parity_b1.py:generic-api-key:61"
)
ENERGY_STORAGE_FINGERPRINT = (
    "5de2f7291555ba0e6a058f6265498876ee562fd4:"
    "custom_components/trybatec/energy_bulk_native_port_l7.py:generic-api-key:55"
)


def test_single_scoped_historical_gitleaks_exception():
    lines = (ROOT / ".gitleaksignore").read_text(encoding="utf-8").splitlines()
    active = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    assert active == [FINGERPRINT, ENERGY_STORAGE_FINGERPRINT]
    assert len(active) == len(set(active))
    assert all(not line.startswith('#') for line in active)
    assert re.fullmatch(r"[a-f0-9]{40}:[a-zA-Z0-9_./-]+:[a-zA-Z0-9_-]+:[1-9][0-9]*", active[0])


def test_gitleaks_incremental_and_full_history_scan_remain_enforced():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    job = workflow.split("\n  secrets:\n", 1)[1].split("\n  homeassistant-runtime-tests:\n", 1)[0]
    assert "name: gitleaks" in job
    assert "fetch-depth: 0" in job
    assert "gitleaks/gitleaks-action@" in job
    assert 'GITLEAKS_ENABLE_UPLOAD_ARTIFACT: "false"' in job
    assert "Recheck reachable Git history (schedule parity)" in job
    assert "github.event_name == 'pull_request' || github.event_name == 'push'" in job
    assert "gitleaks detect --redact --exit-code=2 --log-level=warn" in job
    assert job.index("gitleaks/gitleaks-action@") < job.index("Recheck reachable Git history")
    assert "continue-on-error:" not in job
    assert "Assert synthetic Git credentials are rejected" in job
    assert "scan_code" not in job  # Do not silently change the historical scan outcome.
    assert "gitleaks detect --source" in job
    assert 'if [[ "$synthetic_scan_code" -ne 2 ]]' in job
