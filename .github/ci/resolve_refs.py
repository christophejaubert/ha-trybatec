"""Resolve immutable comparison SHAs using public GitHub metadata only.

The *executable* script must be checked out from a previously reviewed,
immutable trusted commit, NEVER from the candidate PR. The candidate manifest
is read as untrusted JSON from the candidate checkout (cwd), not executed.
No GitHub token, credentials, or privileged API access are needed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

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
    """Read only fixed HTTPS public GitHub REST endpoints, without credentials.

    Any unexpected endpoint, redirect, response or rate limit fails closed.
    The job must not fall back to a token or candidate-supplied executable.
    """
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not REPO.fullmatch(repo):
        raise SystemExit("Invalid repository identifier")
    if not (
        re.fullmatch(r"releases\\?per_page=100&page=[1-5]", path)
        or re.fullmatch(r"git/ref/tags/[A-Za-z0-9_.-]+", path)
        or re.fullmatch(r"git/tags/[0-9a-f]{40}", path)
    ):
        raise SystemExit("Unapproved public GitHub API path")

    url = f"https://api.github.com/repos/{repo}/{path}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "ha-trybatec-ci-readonly-reference-resolver",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise SystemExit("Unexpected GitHub API redirect")

    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise SystemExit("Public GitHub API unavailable or rate-limited") from exc
    if len(raw) > 8 * 1024 * 1024:
        raise SystemExit("GitHub API response exceeded safety limit")
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit("Invalid GitHub API JSON response") from exc


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
