"""Coverage inventory for the existing synthetic UI acceptance (#70/#83/#84).

Source-level guard only: it cannot replace executing Chromium or a real HA audit.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "custom_components/trybatec/panel/trybatec-panel.js"
BROWSER = ROOT / "scripts/browser-ci/acceptance.cjs"
SECTIONS = (
    "overview",
    "meters",
    "history",
    "tariffs",
    "energy",
    "diagnostics",
    "settings",
)


def test_panel_navigation_declares_seven_distinct_sections() -> None:
    source = PANEL.read_text(encoding="utf-8")
    navigation = source.split("const TABS = [", 1)[1].split("];", 1)[0]
    keys = re.findall(r'\["([a-z]+)",', navigation)
    assert tuple(keys) == SECTIONS


def test_synthetic_browser_visits_each_section_in_eight_variants() -> None:
    source = BROWSER.read_text(encoding="utf-8")
    expected_tabs = (
        'const tabs=["overview","meters","history",'
        '"tariffs","energy","diagnostics","settings"];'
    )
    assert expected_tabs in source
    variants = source.split("const destinations = [", 1)[1].split("];", 1)[0]
    cases = re.findall(
        r'\["(FR|EN)","(desktop|mobile)",(true|false)\]', variants
    )
    assert len(cases) == 8
    assert len(set(cases)) == 8
    assert "path:join(artifacts,locale+" in source
    assert "screenshots:destinations.length*tabs.length" in source
    assert "mode:\"synthetic-browser-not-real-HA\"" in source


def test_non_mutating_synthetic_protections_remain_explicit() -> None:
    source = BROWSER.read_text(encoding="utf-8")
    assert "productionWrites:0,vendorRequests:0" in source
    assert "const observed=await page.evaluate" in source
    assert "trybatec/panel_snapshot" in source
    assert "trybatec/panel_history_job_start" in source


def test_baseline_a11y_assertions_are_discoverable() -> None:
    source = BROWSER.read_text(encoding="utf-8")
    assert "await page.setViewportSize({width:320,height:760})" in source
    assert "layout.documentWidth<=layout.viewport+2" in source
    assert "focusStyle.width" in source
    assert "renderedContrast(activeNeutral.color,activeNeutral.background)" in source
    # This inventories existing checks, NOT coverage of every view,
    # full keyboard paths, text zoom 200%, or screen readers.
