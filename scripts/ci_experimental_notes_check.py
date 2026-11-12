"""FR/EN: validate public experimental release notes before any publication.

No network, no filesystem writes, and no printing release-note contents on failure.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

VERSION = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:a|b|rc)[1-9]\d*")
TITLE = re.compile(r"#\s+([0-9]+\.[0-9]+\.[0-9]+(?:a|b|rc)[0-9]+)(?:\s*[—-].*)?")
SECTION = re.compile(r"(?m)^##\s+(FR|EN)(?:\s*[—:-].*)?\s*$")


def validate(version: str, notes: str) -> None:
    """Reject missing, duplicated or empty bilingual sections; do not log content."""
    if VERSION.fullmatch(version) is None:
        raise ValueError("Invalid experimental prerelease version")
    lines = notes.strip().splitlines()
    if not lines or TITLE.fullmatch(lines[0]) is None:
        raise ValueError("Missing version heading")
    if TITLE.fullmatch(lines[0]).group(1) != version:
        raise ValueError("Notes version mismatch")
    headers = list(SECTION.finditer(notes))
    if [match.group(1) for match in headers] != ["FR", "EN"]:
        raise ValueError("FR and EN headings must each appear once in order")
    for i, header in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(notes)
        body = notes[header.end():end].strip()
        if len(body) < 40:
            raise ValueError("Missing substantive language section")
    if len(notes) > 150000:
        raise ValueError("Oversized release notes")


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("Expected version and notes file")
    try:
        version = sys.argv[1]
        notes = Path(sys.argv[2]).read_text(encoding="utf-8")
        validate(version, notes)
    except (OSError, UnicodeError, ValueError):
        print("FR/EN release note check failed: verify language sections and version.", file=sys.stderr)
        return 1
    print("FR/EN release note structure and version verified; manual privacy review still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
