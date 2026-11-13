"""FR/EN: verify proposed release metadata only; no HA modifications."""
from pathlib import Path
import json

from scripts.ci_experimental_notes_check import validate

ROOT = Path(__file__).resolve().parents[1]


def test_candidate_manifest_and_bilingual_notes_agree() -> None:
    manifest = json.loads(
        (ROOT / "custom_components/trybatec/manifest.json").read_text(encoding="utf-8")
    )
    notes = (ROOT / "RELEASE_NOTES_BETA.md").read_text(encoding="utf-8")
    validate(manifest["version"], notes.split("\n---\n", 1)[0])


def test_production_only_protocol_keeps_write_authorizations_separate() -> None:
    protocol = (ROOT / "docs/PRODUCTION_ACCEPTANCE_0.3.4b1_FR_EN.md").read_text(
        encoding="utf-8"
    ).casefold()
    for phrase in (
        "autorisation distincte de sauvegarde",
        "autorisation distincte d'installation",
        "autorisation distincte d'écriture recorder",
        "autorisation distincte de modification énergie",
        "autorisation distincte de restauration",
        "autorisation distincte de publication",
        "quiescence indépendante du writer",
        "en — production-only acceptance safeguards",
    ):
        assert phrase in protocol
