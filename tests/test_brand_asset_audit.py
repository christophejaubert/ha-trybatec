"""Synthetic tests for the read-only Trybatec brand PNG audit.

Only generated in-memory PNGs and checked-in public brand assets are read.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import pytest

from scripts.brand_asset_audit import (
    ASSETS,
    CANONICAL,
    audit_assets,
    inspect_png_bytes,
)

ROOT = Path(__file__).resolve().parents[1]


def _chunk(name: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + name
        + payload
        + struct.pack(">I", zlib.crc32(name + payload) & 0xFFFFFFFF)
    )


def _indexed_png(
    colours: list[str], *, width: int = 1, height: int = 1, alpha: bool = True
) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, 8, 3, 0, 0, 0)
    palette = b"".join(bytes.fromhex(rgb[1:]) for rgb in colours)
    transparency = bytes([0] + [255] * (len(colours) - 1))
    pixels = (b"\x00" + bytes([0]) * width) * height
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            _chunk(b"IHDR", header),
            _chunk(b"PLTE", palette),
            _chunk(b"tRNS", transparency) if alpha else b"",
            _chunk(b"IDAT", zlib.compress(pixels)),
            _chunk(b"IEND", b""),
        )
    )


def test_canonical_palette_and_transparency_are_reported() -> None:
    image = _indexed_png(list(CANONICAL.values()))
    result = inspect_png_bytes(image, (1, 1))
    assert result["size_ok"] is True
    assert result["transparent_container"] is True
    assert result["fully_verified"] is True
    assert all(result["exact_canonical_colours_declared"].values())
    assert result["real_home_assistant_acceptance"] is False if (
        "real_home_assistant_acceptance" in result
    ) else True


def test_nearby_colours_do_not_count_as_exact() -> None:
    image = _indexed_png(["#0B85D7", *list(CANONICAL.values())[1:]])
    result = inspect_png_bytes(image, (1, 1))
    assert result["exact_canonical_colours_declared"]["EF"] is False
    assert result["fully_verified"] is False


def test_dimensions_and_alpha_are_independent_gates() -> None:
    colours = list(CANONICAL.values())
    assert not inspect_png_bytes(_indexed_png(colours), (2, 1))["size_ok"]
    no_alpha = inspect_png_bytes(_indexed_png(colours, alpha=False), (1, 1))
    assert no_alpha["transparent_container"] is False
    assert no_alpha["fully_verified"] is False


def test_corrupt_crc_is_rejected() -> None:
    image = bytearray(_indexed_png(list(CANONICAL.values())))
    image[20] ^= 1
    with pytest.raises(ValueError, match="CRC"):
        inspect_png_bytes(bytes(image), (1, 1))


def test_real_assets_are_read_only_and_not_automatically_accepted() -> None:
    result = audit_assets(ROOT)
    assert set(result["files"]) == set(ASSETS)
    assert result["real_home_assistant_acceptance"] is False
    for item in result["files"].values():
        assert item["size_ok"] is True
        assert item["transparent_container"] is True
        assert set(item["exact_canonical_colours_declared"]) == set(CANONICAL)
    # Deliberately no assertion that the real logo already passes #70:
    # that requires a separate asset correction and human HA acceptance.
