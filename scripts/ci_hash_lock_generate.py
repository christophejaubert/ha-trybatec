"""Produce reviewable CI wheel/sdist hash inventory from the official PyPI index.

FR: Générateur temporaire de verrou, sans installer de paquet et sans écriture de production.
EN: Temporary lock inventory generator, no package installation or production writes.
Only fixed repository inventories are accepted; independent pip check and CI tests are still required.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import quote
from urllib.request import Request, urlopen

from packaging.utils import canonicalize_name, parse_wheel_filename

SNAPSHOTS = {
    "pure313": ".github/ci/constraints-pure.txt",
    "pure314": ".github/ci/constraints-pure.txt",
    "ha314": ".github/ci/constraints-ha-runtime.txt",
    "persistence314": ".github/ci/constraints-ha-persistence.txt",
}
SNAPSHOT_LINE = re.compile(r"^([a-zA-Z0-9_.-]+)==([a-zA-Z0-9.!+_-]+)$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_PYPI_BYTES = 10 * 1024 * 1024


def load_snapshot(path: Path) -> dict[str, str]:
    result = {}
    for source in path.read_text(encoding="utf-8").splitlines():
        line = source.strip()
        if not line or line.startswith("#"):
            continue
        match = SNAPSHOT_LINE.fullmatch(line)
        if match is None:
            raise ValueError("Invalid dependency pin")
        name, version = canonicalize_name(match[1]), match[2]
        if name in result or name in {"pip", "setuptools", "wheel"}:
            raise ValueError("Duplicate/bootstrap dependency")
        result[name] = version
    if not 1 <= len(result) <= 400:
        raise ValueError("Unexpected inventory size")
    return result


def dist_from_filename(filename: str, snapshot: dict[str, str]) -> tuple[str, str]:
    if filename.endswith(".whl"):
        name, version, _, _ = parse_wheel_filename(filename)
        return str(name), str(version)
    for suffix in (".tar.gz", ".zip", ".tar.bz2"):
        if filename.endswith(suffix):
            stem = filename[: -len(suffix)]
            for name, version in snapshot.items():
                if stem.lower().endswith("-" + version.lower()):
                    source_name = stem[: -(len(version) + 1)]
                    if canonicalize_name(source_name) == name:
                        return name, version
    raise ValueError("Unrecognized archive type or version")


def official_hash(name: str, version: str, filename: str) -> str:
    url = "https://pypi.org/pypi/" + quote(name, safe="") + "/" + quote(version, safe="") + "/json"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "ha-trybatec-ci-hash-lock/1"})
    with urlopen(request, timeout=30) as response:
        if response.status != 200 or not response.url.startswith("https://pypi.org/"):
            raise ValueError("Unexpected PyPI HTTP response")
        data = response.read(MAX_PYPI_BYTES + 1)
    if len(data) > MAX_PYPI_BYTES:
        raise ValueError("Oversized PyPI metadata")
    parsed = json.loads(data)
    info = parsed.get("info", {})
    if canonicalize_name(info.get("name", "")) != name or info.get("version") != version:
        raise ValueError("PyPI project/version metadata mismatch")
    matches = [entry for entry in parsed.get("urls", []) if entry.get("filename") == filename]
    if len(matches) != 1:
        raise ValueError("Official PyPI artifact filename not found")
    item = matches[0]
    digest = item.get("digests", {}).get("sha256", "")
    if not SHA256.fullmatch(digest) or item.get("yanked", False):
        raise ValueError("Missing official SHA256 or yanked artifact")
    return digest


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in SNAPSHOTS:
        raise SystemExit("Expected one fixed CI inventory selector")
    label = sys.argv[1]
    expected = load_snapshot(Path(SNAPSHOTS[label]))
    with TemporaryDirectory(prefix="trybatec-verified-pypi-") as temp:
        subprocess.run(
            [
                sys.executable, "-m", "pip", "download", "--no-deps",
                "--no-cache-dir", "--index-url", "https://pypi.org/simple",
                "--disable-pip-version-check",
                "--dest", temp, "-r", SNAPSHOTS[label],
            ],
            check=True,
            timeout=900,
        )
        files = list(Path(temp).iterdir())
        found = {}
        for file in files:
            if not file.is_file() or file.is_symlink():
                raise ValueError("Unexpected downloaded artifact")
            name, version = dist_from_filename(file.name, expected)
            if expected.get(name) != version or name in found:
                raise ValueError("Unexpected/duplicate downloaded package")
            found[name] = (file.name, sha256(file.read_bytes()).hexdigest())
        if set(found) != set(expected):
            raise ValueError("Incomplete official distribution inventory")
        def verify(name: str) -> tuple[str, str]:
            filename, measured = found[name]
            official = official_hash(name, expected[name], filename)
            if measured != official:
                raise ValueError("PyPI official SHA256 mismatch: " + name)
            return name, measured
        authenticated = {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {pool.submit(verify, name): name for name in expected}
            for future in as_completed(futures):
                name, digest = future.result()
                authenticated[name] = digest
        # Only print hashes if all downloaded bytes match PyPI official release metadata.
        print("OFFICIAL_HASH_LOCK_BEGIN " + label)
        for name in sorted(expected):
            print(f"{name}=={expected[name]} --hash=sha256:{authenticated[name]}")
        print("OFFICIAL_HASH_LOCK_END " + label)
        print(f"Verified {len(authenticated)} official PyPI archives for {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
