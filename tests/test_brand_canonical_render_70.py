"""FR/EN: verify the canonical colors are used in visible indexed PNG pixels.

Does NOT claim compliance in actual Home Assistant themes or geometry acceptance.
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from scripts.brand_asset_audit import ASSETS, CANONICAL, inspect_png_bytes

ROOT = Path(__file__).resolve().parents[1]


def _visible_indices(raw: bytes) -> tuple[bytes, dict[int, int]]:
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
    width, height, depth, mode, compression, filtering, interlace = struct.unpack_from(
        ">IIBBBBB", raw, 16
    )
    assert (depth, mode, compression, filtering, interlace) == (8, 3, 0, 0, 0)
    offset = 8
    palette, alpha = b"", b""
    data = bytearray()
    while offset < len(raw):
        n = struct.unpack_from(">I", raw, offset)[0]
        kind = raw[offset + 4 : offset + 8]
        payload = raw[offset + 8 : offset + 8 + n]
        if kind == b"PLTE":
            palette = payload
        elif kind == b"tRNS":
            alpha = payload
        elif kind == b"IDAT":
            data.extend(payload)
        offset += 12 + n
        if kind == b"IEND":
            break
    assert palette and alpha
    inflater = zlib.decompressobj()
    expected = (width + 1) * height
    raster = inflater.decompress(bytes(data), expected + 1)
    assert inflater.eof and len(raster) == expected and not inflater.unused_data
    previous = bytearray(width)
    usage: dict[int, int] = {}
    offset = 0
    for _ in range(height):
        method = raster[offset]
        source = raster[offset + 1 : offset + 1 + width]
        offset += width + 1
        line = bytearray(width)
        for x, byte in enumerate(source):
            left = line[x - 1] if x else 0
            above = previous[x]
            upper_left = previous[x - 1] if x else 0
            if method == 0:
                predictor = 0
            elif method == 1:
                predictor = left
            elif method == 2:
                predictor = above
            elif method == 3:
                predictor = (left + above) // 2
            elif method == 4:
                p = left + above - upper_left
                deltas = (abs(p - left), abs(p - above), abs(p - upper_left))
                predictor = (left, above, upper_left)[deltas.index(min(deltas))]
            else:
                raise AssertionError("Unsupported PNG filter")
            index = (byte + predictor) & 255
            line[x] = index
            if index >= len(alpha) or alpha[index] != 0:
                usage[index] = usage.get(index, 0) + 1
        previous = line
    assert offset == len(raster)
    return palette, usage


@pytest.mark.parametrize("relative,dimensions", ASSETS.items())
def test_canonical_colors_are_used_in_visible_pixels(
    relative: str, dimensions: tuple[int, int]
) -> None:
    raw = (ROOT / relative).read_bytes()
    report = inspect_png_bytes(raw, dimensions)
    assert report["fully_verified"], report
    palette, usage = _visible_indices(raw)
    for role, hexa in CANONICAL.items():
        target = bytes.fromhex(hexa[1:])
        found = [
            i // 3 for i in range(0, len(palette), 3)
            if palette[i : i + 3] == target
        ]
        assert len(found) == 1, (relative, role, found)
        assert usage.get(found[0], 0) > 0, (relative, role, "no visible pixels")
