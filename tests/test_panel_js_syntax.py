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
