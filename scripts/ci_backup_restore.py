"""CI-only physical snapshot/restore of synthetic Home Assistant decision storage.

Do not run against a real Home Assistant configuration. Operates only in
GitHub Actions RUNNER_TEMP on explicitly prefixed synthetic test directories.
A separate Home Assistant Core process verifies restored records afterward.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys

ENTRY = "synthetic-ci-entry-persistence"
KEY = "trybatec.review_v4_" + sha256(ENTRY.encode()).hexdigest()[:20]
MAX_STORAGE_BYTES = 256 * 1024
MANIFEST_NAME = "manifest.json"
PAYLOAD_NAME = "decision-store.json"


def bounded_bytes(path: Path, maximum: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Missing or linked synthetic backup source")
    size = path.stat().st_size
    if not 0 < size <= maximum:
        raise ValueError("Synthetic backup file exceeds safe size limit")
    data = path.read_bytes()
    if len(data) != size:
        raise ValueError("Synthetic backup changed while being read")
    return data


def require_synthetic_directory(path: Path, prefix: str) -> Path:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("Snapshot/restore is permitted only in GitHub Actions CI")
    root = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    if path.is_symlink() or path.parent.resolve(strict=True) != root:
        raise ValueError("Snapshot/restore must stay inside RUNNER_TEMP")
    if not re.fullmatch(re.escape(prefix) + r"(?:baseline-self|baseline-to-candidate|candidate-self)", path.name):
        raise ValueError("Unexpected synthetic directory name")
    return path


def validate_synthetic_store(data: bytes) -> None:
    try:
        obj = json.loads(data)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Malformed synthetic Home Assistant storage") from exc
    if not isinstance(obj, dict) or obj.get("version") != 1:
        raise ValueError("Invalid Home Assistant storage envelope")
    envelope = obj.get("data")
    if not isinstance(envelope, dict):
        raise ValueError("Invalid Home Assistant storage data")
    decisions = envelope.get("decisions")
    if not isinstance(decisions, dict) or len(decisions) != 1:
        raise ValueError("Unexpected synthetic decision record count")
    value = next(iter(decisions.values()))
    if not isinstance(value, dict) or value.get("action") != "correct":
        raise ValueError("Unexpected synthetic decision")
    if value.get("reason") != "Synthetic year-end accounting reassignment for restart verification":
        raise ValueError("Only the known synthetic CI record may be snapshotted")


def snapshot(source: Path, destination: Path) -> None:
    source = require_synthetic_directory(source, "ha-decision-")
    destination = require_synthetic_directory(destination, "ha-backup-")
    if not source.is_dir() or (source / ".storage").is_symlink():
        raise ValueError("Missing or linked synthetic HA storage directory")
    data = bounded_bytes(source / ".storage" / KEY, MAX_STORAGE_BYTES)
    validate_synthetic_store(data)
    digest = sha256(data).hexdigest()
    destination.mkdir(mode=0o700, exist_ok=False)
    (destination / PAYLOAD_NAME).write_bytes(data)
    (destination / MANIFEST_NAME).write_text(
        json.dumps({"schema": 1, "key": KEY, "sha256": digest, "size": len(data)}, sort_keys=True),
        encoding="utf-8",
    )
    print("Verified synthetic Home Assistant storage snapshot, sha256:", digest)


def restore(source: Path, destination: Path) -> None:
    source = require_synthetic_directory(source, "ha-backup-")
    destination = require_synthetic_directory(destination, "ha-restored-")
    if not source.is_dir() or destination.exists():
        raise ValueError("Invalid or already used restore destination")
    manifest_raw = bounded_bytes(source / MANIFEST_NAME, 4096)
    try:
        manifest = json.loads(manifest_raw)
    except (UnicodeError, ValueError) as exc:
        raise ValueError("Malformed synthetic backup manifest") from exc
    if not isinstance(manifest, dict) or set(manifest) != {"schema", "key", "sha256", "size"}:
        raise ValueError("Unsupported synthetic backup manifest")
    if manifest["schema"] != 1 or manifest["key"] != KEY:
        raise ValueError("Unexpected or foreign synthetic storage key")
    digest = manifest["sha256"]
    if not isinstance(digest, str) or re.fullmatch(r"[a-f0-9]{64}", digest) is None:
        raise ValueError("Invalid backup checksum")
    data = bounded_bytes(source / PAYLOAD_NAME, MAX_STORAGE_BYTES)
    if len(data) != manifest["size"] or sha256(data).hexdigest() != digest:
        raise ValueError("Backup checksum or size mismatch; refusing restoration")
    validate_synthetic_store(data)
    store_folder = destination / ".storage"
    store_folder.mkdir(mode=0o700, parents=True, exist_ok=False)
    target = store_folder / KEY
    target.write_bytes(data)
    if sha256(bounded_bytes(target, MAX_STORAGE_BYTES)).hexdigest() != digest:
        raise ValueError("Backup read-back verification failed")
    print("Restored verified synthetic storage to fresh isolated directory")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3 or args[0] not in {"snapshot", "restore"}:
        print("Usage: ci_backup_restore.py snapshot|restore source_dir destination_dir", file=sys.stderr)
        return 2
    try:
        action, original, target = args
        if action == "snapshot":
            snapshot(Path(original), Path(target))
        else:
            restore(Path(original), Path(target))
    except (OSError, ValueError, KeyError) as exc:
        print("Synthetic backup/restore rejected: " + type(exc).__name__, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
