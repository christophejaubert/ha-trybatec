"""Read-only PNG asset audit for Trybatec branding (#70).

FR : les couleurs dans une palette ne prouvent pas le rendu final.
EN: palette membership does not prove that a colour is used in rendered pixels.
No Home Assistant, supplier or network access.
"""

from __future__ import annotations

import argparse
import json
import struct
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CANONICAL = {
    "EF": "#0A84D8",
    "ECS": "#C73A5C",
    "CET": "#E0A126",
    "brand": "#4E9E4A",
}
ASSETS = {
    "custom_components/trybatec/brand/icon.png": (256, 256),
    "custom_components/trybatec/brand/icon@2x.png": (512, 512),
}


def inspect_png_bytes(data: bytes, expected_size: tuple[int, int]) -> dict:
    """Inspect the PNG container, declared palette and transparency.

    Reject invalid chunk boundaries and CRCs. Do not infer logo geometry,
    contrast on actual HA surfaces, or colour usage from PLTE declarations.
    """
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("Invalid PNG signature")
    offset = len(PNG_SIGNATURE)
    header = None
    palette = None
    transparency = None
    found_end = False
    while offset < len(data):
        if offset + 12 > len(data):
            raise ValueError("Truncated PNG chunk")
        length = struct.unpack_from(">I", data, offset)[0]
        end = offset + 12 + length
        if end > len(data):
            raise ValueError("Truncated PNG payload")
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        expected_crc = struct.unpack_from(">I", data, offset + 8 + length)[0]
        computed_crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        if expected_crc != computed_crc:
            raise ValueError("Invalid PNG chunk CRC")
        offset = end
        if kind == b"IHDR":
            if header is not None or length != 13:
                raise ValueError("Invalid IHDR")
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"PLTE":
            if length % 3:
                raise ValueError("Invalid PLTE length")
            palette = {
                "#" + payload[i : i + 3].hex().upper()
                for i in range(0, length, 3)
            }
        elif kind == b"tRNS":
            transparency = payload
        elif kind == b"IEND":
            found_end = True
            break
    if header is None or not found_end:
        raise ValueError("Missing PNG header or terminator")
    width, height, bit_depth, colour_type, _, _, _ = header
    if colour_type == 3:
        has_transparency = transparency is not None and any(
            alpha < 255 for alpha in transparency
        )
        match = (
            {role: rgb in palette for role, rgb in CANONICAL.items()}
            if palette is not None
            else {role: False for role in CANONICAL}
        )
        palette_evaluable = palette is not None
    else:
        # Truecolour requires pixel decoding. Do not report an unsupported
        # container as passing the exact-palette test.
        has_transparency = colour_type in (4, 6) or transparency is not None
        match = {role: None for role in CANONICAL}
        palette_evaluable = False
    return {
        "size": [width, height],
        "size_ok": (width, height) == expected_size,
        "bit_depth": bit_depth,
        "colour_type": colour_type,
        "transparent_container": has_transparency,
        "exact_canonical_colours_declared": match,
        "palette_evaluable": palette_evaluable,
        "fully_verified": (
            (width, height) == expected_size
            and has_transparency
            and palette_evaluable
            and all(value is True for value in match.values())
        ),
        "limitations": (
            "No pixel-use, silhouette, theme contrast, or HA visual "
            "acceptance verification."
        ),
    }


def audit_assets(root: Path) -> dict:
    """Inspect assets without reading any file outside the declared paths."""
    files = {}
    for relative_path, dimensions in ASSETS.items():
        path = root / relative_path
        try:
            files[relative_path] = inspect_png_bytes(path.read_bytes(), dimensions)
        except (OSError, ValueError) as exc:
            files[relative_path] = {"fully_verified": False, "error": str(exc)}
    return {
        "mode": "read-only-assets",
        "files": files,
        "all_declarations_verified": all(
            item.get("fully_verified", False) for item in files.values()
        ),
        "real_home_assistant_acceptance": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on any missing exact palette declaration; opt-in only.",
    )
    args = parser.parse_args()
    result = audit_assets(args.root)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if args.strict and not result["all_declarations_verified"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
