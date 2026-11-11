"""Non-destructive checks for the version presented in the Trybatec panel."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "custom_components" / "trybatec" / "panel" / "trybatec-panel.js"
API = ROOT / "custom_components" / "trybatec" / "panel_api.py"
MANIFEST = ROOT / "custom_components" / "trybatec" / "manifest.json"


def test_manifest_matches_candidate_notes_and_frontend_gets_installed_version() -> None:
    version = json.loads(MANIFEST.read_text(encoding="utf-8"))["version"]
    notes = (ROOT / "RELEASE_NOTES_BETA.md").read_text(encoding="utf-8")
    assert isinstance(version, str) and version
    assert notes.startswith(f"# {version} —"), "Update candidate notes when bumping the manifest"
    source = API.read_text(encoding="utf-8")
    assert '(Path(__file__).parent / "manifest.json").read_text' in source
    assert '"version": await hass.async_add_executor_job(_installed_version)' in source
    assert '"version": _installed_version()' not in source
    assert 'module_url=f"{_PANEL_ASSETS}/trybatec-panel.js?v={cache_token}"' in source
    assert 'installed = await hass.async_add_executor_job(_installed_version)' in source
    assert 'trybatec/panel_snapshot' in source
    panel = PANEL.read_text(encoding="utf-8")
    assert 'const version=this._data?.version;' in panel
    assert 'Version installée' in panel
    assert 'encodeURIComponent(version)' in panel


def test_version_not_invented_on_api_error() -> None:
    source = API.read_text(encoding="utf-8")
    assert 'except (OSError, TypeError, ValueError):' in source
    assert 'return None' in source
    panel = PANEL.read_text(encoding="utf-8")
    assert '<span class="badge">Bêta</span>' in panel
