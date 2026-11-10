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



def test_reviewed_reading_links_to_exact_preceding_smoothing_interval():
    source = PANEL.read_text(encoding="utf-8")
    assert 'data-reading-smoothing' in source
    assert 'match.meter_serial!==item.meter_serial' in source
    assert 'match.source_end_at!==item.source_date' in source
    assert 'Aucun intervalle précédent vérifiable' in source
    assert 'aucune décision enregistrée' in source
    assert 'this._historySelected=match.interval_key' in source


def test_estimated_origin_panel_requires_separate_confirmed_save():
    """An estimated assumption must be previewed, confirmed and kept out of Recorder."""
    source = PANEL.read_text(encoding="utf-8")
    assert 'type:"trybatec/panel_estimated_origin_preview"' in source
    assert 'type:"trybatec/panel_estimated_origin_save"' in source
    assert 'data-origin-save' in source
    assert 'expected_fingerprint:preview.approval_fingerprint' in source
    assert 'confirm:true,confirm_revision:this._originRevision' in source
    assert "saved.source_indices_unchanged!==true" in source
    assert "saved.recorder_writes!==false" in source
    assert "saved.energy_writes!==false" in source
    assert "Motif déclaré pour cette hypothèse" in source
    assert "l’index initial n’est pas un relevé" not in source


def test_annual_cost_preview_uses_readonly_yearly_source():
    """Annual price view requests a verified read-only preview, not Recorder writes."""
    source = PANEL.read_text(encoding="utf-8")
    assert 'data-cost-preview' in source
    assert 'service:"preview_costs"' in source
    assert 'include_cold_water:true,include_hot_water:true,include_heating:true' in source
    assert 'result?.mode!=="read_only_historical_cost_estimates"' in source
    assert 'result.currency!=="EUR"' in source
    assert 'result.persisted!==false' in source
    assert 'result.start_date!==start_date || result.end_date!==end_date' in source
    assert 'this._costPreview=null;this._costYear=null;' in source
    assert 'x.estimated_cost===null?"Indisponible"' in source
    assert 'p.withheld_total' in source
    assert 'm.estimated_cost===null?"coût indisponible"' in source
    assert 'fmt(m.quantity)' in source
    assert 'Aucun autre exercice n’est utilisé pour remplacer un tarif manquant.' in source


def test_trybatec_panel_english_labels_are_local_and_safe():
    """UI translation operates on rendered text, never on source data or services."""
    source = PANEL.read_text(encoding="utf-8")
    assert "function localizeTrybatecPanel(root, language)" in source
    assert 'if (!/^en(?:$|[-_])/i.test(String(language||"")))' in source
    assert "NodeFilter.SHOW_TEXT" in source
    assert 'tag!=="STYLE" && tag!=="SCRIPT"' in source
    assert "localizeTrybatecPanel(this.shadowRoot,this._hass?.language)" in source
    for fr, en in (
        ("Vue d’ensemble", "Overview"),
        ("Compteurs", "Meters"),
        ("Historique & lissage", "History & smoothing"),
        ("Tarifs", "Tariffs"),
        ("Énergie & versions", "Energy & versions"),
        ("Diagnostics", "Diagnostics"),
        ("Réglages", "Settings"),
        ("Tarif commun du fluide", "Default fluid rate"),
        ("Coût estimé", "Estimated cost"),
        ("Aucune borne antérieure fiable : simuler une origine estimée",
         "No reliable earlier baseline: simulate an estimated origin"),
    ):
        assert f'["{fr}","{en}"]' in source
