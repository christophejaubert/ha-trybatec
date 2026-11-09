"""Regression for optional Home Assistant Recorder integration dependency."""
from __future__ import annotations

import json
from pathlib import Path


def test_recorder_is_optional_and_declared_for_hassfest():
    manifest = json.loads(
        Path("custom_components/trybatec/manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["domain"] == "trybatec"
    assert manifest["after_dependencies"] == ["energy", "recorder"]
    assert "recorder" not in manifest.get("dependencies", [])


def test_manifest_keys_are_in_hassfest_order():
    manifest = json.loads(
        Path("custom_components/trybatec/manifest.json").read_text(encoding="utf-8")
    )
    keys = list(manifest)
    assert keys[:2] == ["domain", "name"]
    assert keys[2:] == sorted(keys[2:])
