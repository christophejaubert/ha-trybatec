"""Run standalone FR/EN UI guard without importing the shared panel."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js unavailable")
def test_standalone_energy_ui_is_non_operational_and_accessible():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "browser-ci" / "energy-bulk-draft-l7.spec.mjs"
    completed = subprocess.run(["node", str(script)], check=False, capture_output=True,
                               text=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
    assert "UI FR/EN" in completed.stdout
