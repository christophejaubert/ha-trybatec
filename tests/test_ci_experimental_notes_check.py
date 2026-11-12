"""FR/EN: synthetic note samples, no release or external effects."""
import pytest

from scripts.ci_experimental_notes_check import validate


def notes(fr: str = "Description française synthétique suffisamment détaillée sans données privées.",
          en: str = "Synthetic English description with enough detail and no private data.",
          version: str = "0.3.4b1") -> str:
    return f"# {version} — Test-only prerelease\n\n## FR — Changements\n\n{fr}\n\n## EN — Changes\n\n{en}\n"


def test_fr_en_release_notes_accept_both_sections() -> None:
    validate("0.3.4b1", notes())


@pytest.mark.parametrize("bad", [
    "# 0.3.4b1 — Test\n\n## FR\n\nTexte français suffisant uniquement pour cette section.",
    notes(en=""),
    notes(fr=""),
    notes(version="0.3.3b1"),
    notes().replace("## EN", "## FR"),
    notes().replace("## FR", "## EN", 1),
    notes() + "\n## EN — Duplicate\n\nDuplicate section.",
])
def test_fr_en_release_notes_fail_closed(bad: str) -> None:
    with pytest.raises(ValueError):
        validate("0.3.4b1", bad)
