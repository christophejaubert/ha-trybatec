"""FR/EN: static WCAG contrast checks of known Trybatec CSS color tokens.

Read-only source inspection. Not a computed-rendered HA theme or WCAG audit.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

CANONICAL = {
    "--trybatec-ef-brand": "#0A84D8",
    "--trybatec-ecs-brand": "#C73A5C",
    "--trybatec-cet-brand": "#E0A126",
    "--trybatec-brand-green": "#4E9E4A",
}
COLOR = re.compile(r"(--trybatec-[A-Za-z0-9-]+):\s*(#[0-9a-fA-F]{6})\b")


def luminance(rgb: str) -> float:
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", rgb):
        raise ValueError("Expected #RRGGBB")
    values = [int(rgb[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(fg: str, bg: str) -> float:
    light, dark = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def tokens(source: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {"light": {}, "dark": {}}
    for line in source.splitlines():
        if "--trybatec-" in line:
            mode = "dark" if 'data-trybatec-theme=' in line and "dark" in line else "light"
            result[mode].update(COLOR.findall(line))
    return result


def audit(source: str) -> dict:
    found = tokens(source)
    checks = []
    for mode in ("light", "dark"):
        t = found[mode]
        for role, fg, bg in (
            ("primary", "--trybatec-action-text", "--trybatec-action-bg"),
            ("neutral", "--trybatec-neutral-fg", "--trybatec-neutral-bg"),
        ):
            a, b = t.get(fg), t.get(bg)
            ratio = round(contrast(a, b), 3) if a and b else None
            checks.append({
                "theme": mode, "role": role,
                "foreground": a, "background": b,
                "source_ratio": ratio,
                "source_4_5_pass": ratio >= 4.5 if ratio is not None else None,
            })
    return {
        "mode": "source_only_not_live_HA",
        "checks": checks,
        "canonical_logo_tokens": {k: found["light"].get(k) == value for k, value in CANONICAL.items()},
        "actual_theme_render_verified": False,
        "zoom_200_verified": False,
        "screen_reader_verified": False,
        "wcag_2_2_aa_certified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--panel", type=Path,
        default=Path("custom_components/trybatec/panel/trybatec-panel.js"),
    )
    args = parser.parse_args()
    print(json.dumps(audit(args.panel.read_text(encoding="utf-8")), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
