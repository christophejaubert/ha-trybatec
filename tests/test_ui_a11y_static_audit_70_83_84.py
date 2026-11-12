"""FR/EN: source-only contrast arithmetic and actual panel token contracts."""
from pathlib import Path

import pytest

from scripts.ui_a11y_static_audit import CANONICAL, audit, contrast, tokens

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "custom_components/trybatec/panel/trybatec-panel.js"


def test_wcag_contrast_arithmetic() -> None:
    assert contrast("#000000", "#FFFFFF") == pytest.approx(21.0)
    assert contrast("#FFFFFF", "#FFFFFF") == pytest.approx(1.0)
    assert contrast("#25364A", "#FFFFFF") >= 4.5
    with pytest.raises(ValueError):
        contrast("var(--theme)", "#FFFFFF")


def test_tokens_distinguish_light_and_dark() -> None:
    source = (
        '":host{--trybatec-action-text:#111111;--trybatec-action-bg:#FFFFFF}",\n'
        '":host([data-trybatec-theme=\\\"dark\\\"]){'
        '--trybatec-action-text:#FFFFFF;--trybatec-action-bg:#111111}",'
    )
    result = tokens(source)
    assert result["light"]["--trybatec-action-text"] == "#111111"
    assert result["dark"]["--trybatec-action-text"] == "#FFFFFF"


def test_unknown_theme_colors_are_not_marked_as_pass() -> None:
    result = audit('":host{--trybatec-action-text:var(--primary-text-color)}"')
    assert all(x["source_4_5_pass"] is None for x in result["checks"])
    assert result["actual_theme_render_verified"] is False
    assert result["screen_reader_verified"] is False


def test_declared_panel_action_colors_have_adequate_source_ratio() -> None:
    result = audit(PANEL.read_text(encoding="utf-8"))
    assert set(result["canonical_logo_tokens"]) == set(CANONICAL)
    assert all(result["canonical_logo_tokens"].values())
    assert len(result["checks"]) == 4
    assert all(x["source_4_5_pass"] is True for x in result["checks"])
    assert result["wcag_2_2_aa_certified"] is False
