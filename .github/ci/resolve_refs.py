"""Select immutable CI comparison commits without release/version literals.

Run from an actions/checkout of the exact candidate commit. Never fetch or
execute data supplied by a release; only read GitHub's release/tag metadata.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:(a|b|rc)(\d+))?$")
SHA = re.compile(r"^[0-9a-f]{40}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PRE_RANK = {"a": 0, "b": 1, "rc": 2, None: 3}


def version_key(version: str):
    """Comparable PEP 440-style project versions; never sort as strings."""
    match = VERSION.fullmatch(version)
    if not match:
        return None
    major, minor, patch, suffix, suffix_num = match.groups()
    return (
        int(major), int(minor), int(patch), PRE_RANK[suffix],
        int(suffix_num or 0),
    )


def github_api(path: str):
    return json.loads(
        subprocess.check_output(
            ["gh", "api", f"repos/{os.environ['GITHUB_REPOSITORY']}/{path}"],
            text=True,
        )
    )


def previous_release(candidate_version: str):
    """Pick the highest *published*, strictly older semantic version."""
    current = version_key(candidate_version)
    if current is None:
        raise SystemExit("Candidate manifest version is not supported")
    available = []
    for page in range(1, 6):
        rows = github_api(f"releases?per_page=100&page={page}")
        if not isinstance(rows, list):
            raise SystemExit("Unexpected GitHub releases response")
        for release in rows:
            tag = release.get("tag_name", "")
            parsed = version_key(tag)
            if (
                not release.get("draft", False)
                and release.get("published_at")
                and parsed is not None
                and parsed < current
            ):
                available.append((parsed, tag))
        if len(rows) < 100:
            break
    if not available:
        raise SystemExit(
            "No published earlier semver release found. "
            "Historical upgrade tests cannot be silently skipped."
        )
    return max(available)[1]


def release_commit(tag: str):
    """Dereference both lightweight and annotated Git tags to a commit."""
    obj = github_api(f"git/ref/tags/{tag}")["object"]
    for _ in range(5):
        if obj["type"] == "commit":
            sha = obj["sha"]
            if not SHA.fullmatch(sha):
                raise SystemExit("Invalid release commit SHA")
            return sha
        if obj["type"] != "tag":
            raise SystemExit("Release tag does not point to a commit")
        obj = github_api(f"git/tags/{obj['sha']}")["object"]
    raise SystemExit("Excessively nested tag reference")


def main():
    repo = os.environ["GITHUB_REPOSITORY"]
    sha = os.environ["CANDIDATE_SHA"]
    if not REPO.fullmatch(repo) or not SHA.fullmatch(sha):
        raise SystemExit("Invalid repository or candidate commit SHA")
    manifest = json.loads(
        Path("custom_components/trybatec/manifest.json").read_text(encoding="utf-8")
    )
    candidate_version = manifest["version"]
    tag = previous_release(candidate_version)
    baseline_sha = release_commit(tag)
    if baseline_sha == sha:
        raise SystemExit("Baseline and candidate resolve to the same commit")
    print(f"Candidate: {candidate_version} @ {sha}")
    print(f"Previous published release: {tag} @ {baseline_sha}")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(f"candidate_sha={sha}\n")
        output.write(f"baseline_sha={baseline_sha}\n")
        output.write(f"baseline_tag={tag}\n")


if __name__ == "__main__":
    main()
