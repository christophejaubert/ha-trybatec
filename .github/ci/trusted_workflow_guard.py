"""PR path-integrity gate: run only from a trusted *base-branch* checkout.

For GitHub Actions pull_request_target only. Never checkout, import or execute
the pull request's files. The PR API is read as untrusted data, never directions.
No write permission or repository secret is required; only an ephemeral
read-only GitHub Actions token for pull-request metadata.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import PurePosixPath

REPOSITORY = "christophejaubert/ha-trybatec"
OWNER = "christophejaubert"
MAX_FILES = 3000
MAX_RESPONSE = 2 * 1024 * 1024
PROTECTED_PREFIXES = (
    ".github/workflows/",
    ".github/ci/",
    ".github/actions/",
    "integration_tests/",
    "scripts/",
    "tests/",
)
PROTECTED_EXACT = {
    ".github/workflows",
    ".github/ci",
    ".github/actions",
    ".github/CODEOWNERS",
    "CODEOWNERS",
    "docs/CODEOWNERS",
    ".github/dependabot.yml",
}


def sensitive_path(value: object) -> bool:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("Invalid pull-request file path")
    if value.startswith("/") or "\\" in value:
        raise ValueError("Unexpected pull-request path")
    parts = PurePosixPath(value).parts
    if not parts or any(part in (".", "..") for part in value.split("/")):
        raise ValueError("Non-normalized pull-request file path")
    return value in PROTECTED_EXACT or any(
        value.startswith(prefix) for prefix in PROTECTED_PREFIXES
    )


def owner_authored_in_same_repo(pr: dict) -> bool:
    """Require both the verified GitHub PR author and the owned head repository."""
    user = pr.get("user")
    head = pr.get("head")
    if not isinstance(user, dict) or not isinstance(head, dict):
        raise ValueError("Unexpected PR metadata")
    repo = head.get("repo")
    if not isinstance(repo, dict):
        raise ValueError("Missing head repository")
    return (
        user.get("login") == OWNER
        and repo.get("full_name") == REPOSITORY
    )


def evaluate(pr: dict, filenames: list[str]) -> tuple[bool, list[str]]:
    if not isinstance(pr, dict) or not isinstance(pr.get("base"), dict):
        raise ValueError("Invalid PR payload")
    if pr["base"].get("ref") != "main":
        raise ValueError("Trusted gate must inspect PRs targeting main")
    if not isinstance(filenames, list) or len(filenames) > MAX_FILES:
        raise ValueError("PR file list missing or exceeds safety limit")
    sensitive = sorted({name for name in filenames if sensitive_path(name)})
    if not sensitive:
        return True, []
    if owner_authored_in_same_repo(pr):
        return True, sensitive
    return False, sensitive


def public_pr_files(number: int, token: str) -> list[str]:
    """Bounded GitHub API metadata lookup; never open links from API responses."""
    if not isinstance(number, int) or not 1 <= number <= 1_000_000_000:
        raise ValueError("Invalid PR number")
    if not token:
        raise ValueError("Missing read-only Actions token")
    names: list[str] = []
    opener = urllib.request.build_opener(_NoRedirect())
    for page in range(1, MAX_FILES // 100 + 2):
        url = (
            f"https://api.github.com/repos/{REPOSITORY}/pulls/{number}/files"
            f"?per_page=100&page={page}"
        )
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "ha-trybatec-trusted-ci-policy",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with opener.open(req, timeout=15) as response:
                raw = response.read(MAX_RESPONSE + 1)
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            raise ValueError("Unable to read PR file metadata") from exc
        if len(raw) > MAX_RESPONSE:
            raise ValueError("GitHub API response too large")
        try:
            rows = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid GitHub PR API response") from exc
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError("Invalid GitHub PR file page")
        for item in rows:
            if not isinstance(item, dict):
                raise ValueError("Invalid GitHub PR file entry")
            filename = item.get("filename")
            sensitive_path(filename)  # Validate even when not protected.
            names.append(filename)
            if len(names) > MAX_FILES:
                raise ValueError("PR has too many changed files")
        if len(rows) < 100:
            return names
    raise ValueError("Incomplete GitHub PR file list")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Unexpected redirect from GitHub API")


def main() -> None:
    if (
        os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
        or os.environ.get("GITHUB_EVENT_NAME") != "pull_request_target"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
    ):
        raise SystemExit("Untrusted workflow context")
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")
    if not event_path or len(event_path) > 2048:
        raise SystemExit("Invalid event location")
    try:
        with open(event_path, "r", encoding="utf-8") as inp:
            event = json.load(inp)
        pr = event["pull_request"]
        number = event["number"]
        if isinstance(number, bool) or not isinstance(number, int):
            raise ValueError("Invalid PR number")
        names = public_pr_files(number, os.environ.get("GH_TOKEN", ""))
        allowed, changed = evaluate(pr, names)
    except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Trusted workflow protection failed closed: {type(exc).__name__}") from exc
    if not allowed:
        print("External contributor attempted to change protected CI/security files:")
        for name in changed:
            print(f"- {name}")
        raise SystemExit(1)
    if changed:
        print("Protected CI files changed in a PR authored by the repository owner.")
        print("These changes still require a deliberate human security review.")
        for name in changed:
            print(f"- {name}")
    else:
        print("No protected CI or security policy files changed.")
    print("Trusted workflow-integrity policy passed.")


if __name__ == "__main__":
    main()
