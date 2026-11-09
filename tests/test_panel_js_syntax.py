"""Prevent a broken standalone panel script from passing Python-only CI.

The HA runtime tests are normally headless; this checks source syntax with
Node.js when available and protects against regression in template assembly.
"""
from pathlib import Path
import shutil
import subprocess

import pytest

PANEL = Path(__file__).resolve().parents[1] / "custom_components/trybatec/panel/trybatec-panel.js"


def test_trybatec_panel_javascript_syntax():
    assert PANEL.is_file(), "The installed Trybatec panel module is missing"
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is unavailable; dedicated JS CI must validate syntax")
    result = subprocess.run(
        [node, "--check", str(PANEL)],
        capture_output=True, text=True, check=False, timeout=15,
    )
    assert result.returncode == 0, (
        "Trybatec frontend JavaScript has a syntax error: " + result.stderr
    )


def test_trybatec_panel_keeps_additive_navigation_sections():
    source = PANEL.read_text(encoding="utf-8")
    assert '["overview", "Vue d’ensemble"' in source
    assert '["meters", "Compteurs"' in source
    assert '["history", "Historique & lissage"' in source
    assert '["tariffs", "Tarifs"' in source
    assert '["energy", "Énergie & versions"' in source
    assert '["diagnostics", "Diagnostics"' in source
    assert 'data-openOptions' in source


def test_trybatec_recorder_workflow_requires_explicit_bounded_actions():
    """The frontend delegates to HA's already admin-guarded service handlers."""
    source = PANEL.read_text(encoding="utf-8")
    for service in (
        "preview_b15", "import_b15", "verify_b15",
        "preview_b15_energy", "activate_b15_energy",
    ):
        assert '"' + service + '"' in source
    assert 'type:"call_service"' in source
    assert "return_response:true" in source
    assert "backup_confirmed:true" in source
    assert "plan_fingerprint:plan.plan_fingerprint" in source
    assert "before_fingerprint:p.before_fingerprint" in source
    assert "this._versionImportBackup" in source
    assert "this._versionEnergyBackup" in source
    assert "window.confirm(" in source



def test_trybatec_before_after_does_not_zero_fill_missing_daily_measurements():
    """Daily blanks must remain unknown even when smoothed totals are shown."""
    source = PANEL.read_text(encoding="utf-8")
    assert "this._historyComparison(proposal)" in source
    assert "before_observed_consumption===null?'—'" in source
    assert "cumulative_after" in source
    assert "Un nouvel index mesuré" not in source
    assert "Cumul après" in source
