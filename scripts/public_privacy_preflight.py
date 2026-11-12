"""Incremental public PR privacy preflight; candidate content is never executed.

Must be run from a trusted default-branch checkout. Git PR objects are data.
Findings carry category/count only; neither matched values nor Git stderr
are sent to Actions logs.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass

HASH_RE = re.compile(r"[0-9a-f]{40}\Z")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
LOCAL_EMAIL_RE = re.compile(r"@[A-Za-z0-9_.-]+\.(?:local|lan|home|internal)\Z", re.I)
LOCAL_HOST_RE = re.compile(r"\b[A-Za-z0-9_.-]+\.(?:local|lan|internal)\b", re.I)
USER_PATH_RE = re.compile(
    r"(?:/Users/[^\s\"'\\]+|(?<![\w])/home/(?!runner(?:/|\b))[^\s\"'\\/]+/[^\s\"'\\]+|[A-Za-z]:\\Users\\[^\s\"']+)",
    re.I,
)
PRIVATE_IP_RE = re.compile(
    r"\b(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.(?:\d{1,3}\.)\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.(?:\d{1,3}\.)\d{1,3})\b"
)
KEY_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:gh[pousr]_[A-Za-z0-9]{15,}|github_pat_[A-Za-z0-9_]{15,}|xox[baprs]-[A-Za-z0-9-]{15,}|sk-[A-Za-z0-9_-]{20,})\b"
)
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
ID_RE = re.compile(r"\b(?:housingId|dealId|customerId)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{8,}", re.I)
SAFE_HOSTS = frozenset({"example.local", "test.local", "ha.local", "localhost.local"})
SAFE_EMAIL_DOMAINS = frozenset(
    {"example.com", "example.org", "example.net", "example.invalid", "users.noreply.github.com", "github.com"}
)
MAX_GIT_OUTPUT = 12 * 1024 * 1024
MAX_PR_COMMITS = 10000


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str


def inspect_text(value: str) -> list[Finding]:
    """Return only type and severity. No match values, offsets or snippets."""
    findings: list[Finding] = []
    if KEY_RE.search(value) or JWT_RE.search(value):
        findings.append(Finding("error", "credential-pattern"))
    if USER_PATH_RE.search(value):
        findings.append(Finding("error", "local-user-path"))
    if PRIVATE_IP_RE.search(value):
        findings.append(Finding("warning", "private-network-address"))
    if ID_RE.search(value):
        findings.append(Finding("warning", "installation-identifier"))
    if any(m.group(0).lower() not in SAFE_HOSTS for m in LOCAL_HOST_RE.finditer(value)):
        findings.append(Finding("error", "local-machine-hostname"))
    for match in EMAIL_RE.finditer(value):
        address = match.group(0).lower()
        if address.startswith("icon@2x."):
            continue
        if address.rsplit("@", 1)[1] not in SAFE_EMAIL_DOMAINS:
            findings.append(Finding("warning", "non-fixture-email-in-content"))
            break
    return findings


def inspect_commit_email(value: str) -> list[Finding]:
    """An ordinary author email is permitted under decision D1 (warning only)."""
    if LOCAL_EMAIL_RE.search(value):
        return [Finding("error", "local-machine-in-git-identity")]
    if "@" not in value:
        return [Finding("warning", "unusual-git-identity")]
    domain = value.rsplit("@", 1)[1].lower()
    if domain in {"github.com", "users.noreply.github.com"}:
        return []
    return [Finding("warning", "public-git-author-email")]


def git(*args: str) -> str:
    """Use fixed git arguments, never shells or hooks; suppress all Git stderr."""
    try:
        proc = subprocess.run(
            ["git", "-c", "core.pager=cat", *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValueError("Unable to inspect Git object") from exc
    if proc.returncode != 0 or len(proc.stdout) > MAX_GIT_OUTPUT:
        raise ValueError("Incomplete or unreadable Git inspection")
    return proc.stdout.decode("utf-8", "replace")


def audit(base: str, head: str) -> tuple[list[tuple[str, Finding]], int]:
    """Analyze the PR-only range since the merge base; reject missing histories."""
    if not HASH_RE.fullmatch(base) or not HASH_RE.fullmatch(head):
        raise ValueError("Expected complete Git commit SHA values")
    git("cat-file", "-e", f"{base}^{{commit}}")
    git("cat-file", "-e", f"{head}^{{commit}}")
    merge_bases = git("merge-base", "--all", base, head).splitlines()
    if len(merge_bases) != 1 or not HASH_RE.fullmatch(merge_bases[0]):
        raise ValueError("Ambiguous or missing PR merge base")
    ancestor = merge_bases[0]
    records: list[tuple[str, Finding]] = []
    rows = git("log", "--format=%H%x09%ae%x09%ce", f"{ancestor}..{head}").splitlines()
    if not rows or len(rows) > MAX_PR_COMMITS:
        raise ValueError("Empty or excessive PR commit history")
    for row in rows:
        fields = row.split("\t")
        if len(fields) != 3 or not HASH_RE.fullmatch(fields[0]):
            raise ValueError("Malformed PR commit metadata")
        for identity in set(fields[1:]):
            records.extend(("commit metadata", finding) for finding in inspect_commit_email(identity))
    messages = git("log", "--format=%B", f"{ancestor}..{head}")
    for line in messages.splitlines():
        records.extend(("commit message", finding) for finding in inspect_text(line))
    names = git(
        "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
        "--diff-filter=ACMRT", "--name-only", "-z", ancestor, head, "--",
    )
    for path in filter(None, names.split("\x00")):
        records.extend(("changed filename", finding) for finding in inspect_text(path))
    diff = git(
        "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
        "--no-color", "--unified=0", ancestor, head, "--",
    )
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++ "):
            records.extend(("added content", finding) for finding in inspect_text(line[1:]))
        if line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            records.append(("binary data", Finding("warning", "non-text-content-not-inspected")))
    return records, len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Trusted public PR privacy gate")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    try:
        records, commits = audit(args.base, args.head)
    except (ValueError, OSError, subprocess.SubprocessError):
        print("PRIVACY ERROR: PR object range or metadata cannot be fully verified; fail closed.")
        return 2
    groups: dict[tuple[str, str, str], int] = {}
    for origin, finding in records:
        key = (finding.severity, origin, finding.category)
        groups[key] = groups.get(key, 0) + 1
    print(f"Privacy preflight: reviewed {commits} candidate commits.")
    for (severity, origin, category), count in sorted(groups.items()):
        print(f"PRIVACY {severity.upper()}: {origin}: {category} ({count} occurrence(s))")
    if any(finding.severity == "error" for _, finding in records):
        return 1
    print("Privacy preflight: no blocking findings (non-blocking warnings are advisory).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
