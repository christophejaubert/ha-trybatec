"""FR/EN: public brand asset routing and accessible logo alt contract (#70).

Static contract only: HA's actual served response/cache still needs acceptance.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL_API = ROOT / "custom_components/trybatec/panel_api.py"
PANEL_JS = ROOT / "custom_components/trybatec/panel/trybatec-panel.js"


def test_logo_endpoint_targets_canonical_asset() -> None:
    source = PANEL_API.read_text(encoding="utf-8")
    assert 'f"{_PANEL_ASSETS}/logo.png"' in source
    assert 'str(Path(__file__).parent / "brand" / "icon.png")' in source
    assert "cache_headers=True" in source


def test_panel_uses_logo_endpoint_with_text_alternative() -> None:
    source = PANEL_JS.read_text(encoding="utf-8")
    assert '/api/trybatec_panel/logo.png' in source
    assert 'alt="Trybatec"' in source
    assert "cache+" in source
    # No test claims the actual browser downloaded the correct bytes.
