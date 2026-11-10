"""Verify the approved Trybatec icon assets without Pillow or network access.

This checks file integrity, dimensions, transparency and reference palette
anchors. Visual WCAG/HA acceptance remains a separate manual requirement.
"""
from __future__ import annotations

from pathlib import Path
import struct
import zlib

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "custom_components" / "trybatec" / "brand"
SIGNATURE = b"\x89PNG\r\n\x1a\n"
COLORS = {
    "cold_water_blue": (10, 132, 216),
    "hot_water_raspberry": (199, 58, 92),
    "heating_amber": (224, 161, 38),
    "trybatec_green": (78, 158, 74),
}


def _png_chunks(path: Path) -> dict[bytes, bytes]:
    data = path.read_bytes()
    assert data.startswith(SIGNATURE), f"Invalid PNG signature: {path}"
    chunks: dict[bytes, bytes] = {}
    pos = len(SIGNATURE)
    while pos < len(data):
        assert pos + 12 <= len(data), "Incomplete PNG chunk"
        size = struct.unpack_from(">I", data, pos)[0]
        kind = data[pos + 4:pos + 8]
        end = pos + 12 + size
        assert end <= len(data), "Truncated PNG chunk"
        payload = data[pos + 8:pos + 8 + size]
        stored_crc = struct.unpack_from(">I", data, pos + 8 + size)[0]
        assert zlib.crc32(kind + payload) == stored_crc, f"Bad CRC: {kind!r}"
        chunks[kind] = payload
        pos = end
    assert pos == len(data) and b"IEND" in chunks
    return chunks


@pytest.mark.parametrize(("filename", "dimension"), [
    ("icon.png", 256),
    ("icon@2x.png", 512),
])
def test_approved_brand_icons_are_consistent(filename: str, dimension: int) -> None:
    chunks = _png_chunks(BRAND / filename)
    width, height, bit_depth, color_type = struct.unpack(">IIBB", chunks[b"IHDR"][:10])
    assert (width, height) == (dimension, dimension)
    assert bit_depth == 8 and color_type == 3  # indexed PNG with alpha palette

    palette = chunks[b"PLTE"]
    transparency = chunks[b"tRNS"]
    assert len(palette) % 3 == 0
    assert len(transparency) <= len(palette) // 3
    assert 0 in transparency, "The logo must have a transparent background"
    rgb = [tuple(palette[i:i + 3]) for i in range(0, len(palette), 3)]
    for label, ref in COLORS.items():
        assert any(
            all(abs(v - expected) <= 6 for v, expected in zip(color, ref, strict=True))
            and index < len(transparency) and transparency[index] >= 240
            for index, color in enumerate(rgb)
        ), f"Reference palette anchor missing: {label}"


def test_brand_assets_are_not_identical_duplicates() -> None:
    assert (BRAND / "icon.png").read_bytes() != (BRAND / "icon@2x.png").read_bytes()
