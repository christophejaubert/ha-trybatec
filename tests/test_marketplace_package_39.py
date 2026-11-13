"""Offline package/readiness checks for #39. No account or HA network access.

FR/EN: only repository files and synthetic/static contracts are inspected.
Passing these tests is not a real Home Assistant, HACS, or hassfest acceptance.
"""

from __future__ import annotations

import json
import re
import struct
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ROOT / "custom_components"
DOMAIN = "trybatec"
COMPONENT = COMPONENTS / DOMAIN
READY = ROOT / "docs" / "MARKETPLACE_READINESS.md"
GUIDE = ROOT / "docs" / "MARKETPLACE_INSTALLATION_FR_EN.md"
MANIFEST = COMPONENT / "manifest.json"
HACS = ROOT / "hacs.json"

REQUIRED_MANIFEST_KEYS = {
    "domain", "name", "version", "documentation", "issue_tracker",
    "codeowners", "config_flow", "integration_type", "iot_class",
    "requirements", "dependencies", "after_dependencies", "categories",
}
EXPECTED_CATEGORIES = {"water.meters_leak_detection", "energy.meters_monitoring"}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_single_installable_integration_and_required_entrypoints() -> None:
    assert COMPONENTS.is_dir()
    assert sorted(p.name for p in COMPONENTS.iterdir() if p.is_dir()) == [DOMAIN]
    for path in (
        ROOT / "README.md", HACS, MANIFEST, COMPONENT / "__init__.py",
        COMPONENT / "config_flow.py", COMPONENT / "sensor.py",
        ROOT / "LICENSE", READY, GUIDE,
    ):
        assert path.is_file(), f"Missing distribution file: {path.relative_to(ROOT)}"


def test_manifest_hacs_identity_and_metadata_contract() -> None:
    manifest = _json(MANIFEST)
    hacs = _json(HACS)
    assert REQUIRED_MANIFEST_KEYS <= manifest.keys()
    assert list(manifest)[:2] == ["domain", "name"]
    assert list(manifest)[2:] == sorted(list(manifest)[2:])
    assert manifest["domain"] == DOMAIN
    assert manifest["name"] == hacs["name"]
    assert "Unofficial Beta" in manifest["name"]  # pre-stable status
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:a\d+|b\d+|rc\d+)?", manifest["version"])
    assert manifest["config_flow"] is True
    assert manifest["integration_type"] == "hub"
    assert manifest["iot_class"] == "cloud_polling"
    assert manifest["codeowners"] == ["@christophejaubert"]
    assert manifest["documentation"] == (
        "https://github.com/christophejaubert/ha-trybatec"
    )
    assert manifest["issue_tracker"].startswith(
        "https://github.com/christophejaubert/ha-trybatec/issues"
    )
    assert isinstance(manifest["requirements"], list)
    assert isinstance(manifest["dependencies"], list)
    assert isinstance(manifest["after_dependencies"], list)
    assert isinstance(hacs["name"], str) and hacs["name"]
    assert "homeassistant" not in hacs  # no untested minimum version claim
    assert "zip_release" not in hacs  # current delivery uses repository files


def test_marketplace_categories_have_verified_taxonomy_values() -> None:
    categories = _json(MANIFEST)["categories"]
    assert isinstance(categories, list)
    assert 1 <= len(categories) <= 3
    assert len(categories) == len(set(categories))
    assert set(categories) == EXPECTED_CATEGORIES


@pytest.mark.parametrize(("name", "side"), [("icon.png", 256), ("icon@2x.png", 512)])
def test_existing_local_brand_assets_have_valid_png_header(name: str, side: int) -> None:
    data = (COMPONENT / "brand" / name).read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    assert struct.unpack(">II", data[16:24]) == (side, side)
    # Detailed alpha/CRC/raster checks live in tests/test_brand_asset_audit.py.


def test_package_size_file_count_and_symlink_safety() -> None:
    files = list(COMPONENT.rglob("*"))
    assert not any(p.is_symlink() for p in files)
    regular_files = [p for p in files if p.is_file()]
    assert len(regular_files) <= 50_000
    assert sum(p.stat().st_size for p in regular_files) <= 100 * 1024 * 1024


@pytest.mark.parametrize("lang", ["en", "fr"])
def test_shipped_translations_cover_setup_and_reauthentication(lang: str) -> None:
    translation = _json(COMPONENT / "translations" / f"{lang}.json")
    assert isinstance(translation, dict)
    config = translation["config"]
    steps = config["step"]
    assert {"user", "manual_url", "reauth_confirm"} <= steps.keys()
    for name in ("user", "manual_url", "reauth_confirm"):
        assert isinstance(steps[name]["title"], str) and steps[name]["title"]
    assert {"username", "password"} <= steps["user"]["data"].keys()
    assert "invalid_auth" in config["error"]
    assert "wrong_account" in config["error"]


def test_public_guide_is_discoverable_from_existing_readme_chain() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readiness = READY.read_text(encoding="utf-8")
    guide = GUIDE.read_text(encoding="utf-8")
    assert "docs/MARKETPLACE_READINESS.md" in readme
    assert "MARKETPLACE_INSTALLATION_FR_EN.md" in readiness
    assert "[Préparation Marketplace" in guide
    assert "## FR" in guide and "## EN" in guide


def test_guidance_covers_both_languages_and_no_premature_catalog_claim() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    readiness = READY.read_text(encoding="utf-8")
    for text in (guide, readiness):
        assert "hacs/default" in readiness
        assert "0.3.4b1" in text or "0.3.4b1" in readiness
        assert "Recorder" in text and "Energy" in text
        assert "HACS" in text and "Marketplace" in text
    for token in ("réauthentification", "reauthentication", "désinstallation", "removal"):
        assert token.lower() in guide.lower()
    assert "## EN" in readiness and "## FR" in readiness
    assert "aucune version stable" in readiness.lower()


def test_no_installation_specific_data_in_new_public_documentation() -> None:
    """Conservative content gate for docs added/replaced by #39 (not a secrets scan)."""
    texts = [READY.read_text(encoding="utf-8"), GUIDE.read_text(encoding="utf-8")]
    private_patterns = [
        re.compile(r"\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        re.compile(r"\b(?:eyJ[A-Za-z0-9_-]{24,}\.){2}[A-Za-z0-9_-]{10,}\b"),
        re.compile(r"\b(?:10|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"),
        re.compile(r"/(?:Users|home)/(?!runner|oai/)[^\s/]+/"),
    ]
    for text in texts:
        for pattern in private_patterns:
            assert not pattern.search(text), "Sensitive pattern found in public guide"


def test_docs_refer_only_to_existing_local_artifacts() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    for relative in (
        "MARKETPLACE_READINESS.md", "../SECURITY.md",
        "../custom_components/trybatec/services.yaml",
    ):
        assert relative in guide
        assert (GUIDE.parent / relative).resolve().is_file()
