"""Read-only privacy preflight for public pull requests (no secret values in output)."""

from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass

HASH_RE = re.compile(r"[0-9a-f]{40}\Z")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
LOCAL_EMAIL_RE = re.compile(r"@[A-Za-z0-9_.-]+\.(?:local|lan|home|internal)\Z", re.I)
LOCAL_HOST_RE = re.compile(r"\b[A-Za-z0-9_.-]+\.(?:local|lan|internal)\b", re.I)
USER_PATH_RE = re.compile(r"(?:/U[s]ers/[^\s\"'`\\]+|(?<![\w])/ho[m]e/(?!runner(?:/|\b))[^\s\"'`\\/]+/[^\s\"'`\\]+|[A-Za-z]:\\Users\\[^\s\"']+)", re.I)
PRIVATE_IP_RE = re.compile(r"\b(?:10\.(?:\d{1,3}\.){2}\d{1,3}|192\.168\.(?:\d{1,3}\.)\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.(?:\d{1,3}\.)\d{1,3})\b")
KEY_RE = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:ghp_[A-Za-z0-9]{15,}|github_pat_[A-Za-z0-9_]{15,}|xox[baprs]-[A-Za-z0-9-]{15,}|sk-[A-Za-z0-9_-]{20,})\b")
JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
ID_RE = re.compile(r"\b(?:housingId|dealId|customerId)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{8,}", re.I)

# Recognizable synthetic fixtures; never store a private person's hostname here.
SAFE_HOSTS = frozenset({"example.local", "test.local", "ha.local", "localhost.local"})
SAFE_EMAIL_DOMAINS = frozenset({"example.com", "example.org", "example.net", "example.invalid", "users.noreply.github.com", "github.com"})


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str


def inspect_text(text: str) -> list[Finding]:
    """Classify suspicious content; never include the matched value in a result."""
    findings: list[Finding] = []
    if KEY_RE.search(text) or JWT_RE.search(text):
        findings.append(Finding("error", "credential-pattern"))
    if USER_PATH_RE.search(text):
        findings.append(Finding("error", "local-user-path"))
    if PRIVATE_IP_RE.search(text):
        findings.append(Finding("warning", "private-network-address"))
    if ID_RE.search(text):
        findings.append(Finding("warning", "installation-identifier"))
    for match in LOCAL_HOST_RE.finditer(text):
        if match.group(0).lower() not in SAFE_HOSTS:
            findings.append(Finding("error", "local-machine-hostname"))
            break
    for match in EMAIL_RE.finditer(text):
        domain = match.group(0).rsplit("@", 1)[1].lower()
        # e.g. icon@2x.png is a filename, not an email address.
        if match.group(0).lower().startswith("icon@2x."):
            continue
        if domain not in SAFE_EMAIL_DOMAINS:
            findings.append(Finding("warning", "non-fixture-email-in-content"))
            break
    return findings


def inspect_commit_email(email: str) -> list[Finding]:
    """Warn on public identity; error on a leaked local machine hostname."""
    if LOCAL_EMAIL_RE.search(email):
        return [Finding("error", "local-machine-in-git-identity")]
    if "@" not in email:
        return [Finding("warning", "unusual-git-identity")]
    domain = email.rsplit("@", 1)[1].lower()
    if domain in {"github.com", "users.noreply.github.com"}:
        return []
    return [Finding("warning", "public-git-author-email")]


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return proc.stdout


def audit(base: str, head: str) -> tuple[list[tuple[str, Finding]], int]:
    if not HASH_RE.fullmatch(base) or not HASH_RE.fullmatch(head):
        raise ValueError("Expected complete Git commit SHA values")
    records: list[tuple[str, Finding]] = []
    commit_lines = git("log", "--format=%H%x09%ae%x09%ce", f"{base}..{head}").splitlines()
    for row in commit_lines:
        fields = row.split("\t")
        if len(fields) != 3:
            records.append(("commit metadata", Finding("error", "unreadable-commit-metadata")))
            continue
        for identity in set(fields[1:]):
            records.extend(("commit metadata", finding) for finding in inspect_commit_email(identity))
    messages = git("log", "--format=%B", f"{base}..{head}")
    for line in messages.splitlines():
        records.extend(("commit message", finding) for finding in inspect_text(line))
    diff = git("diff", "--no-ext-diff", "--no-renames", "--unified=0", base, head, "--")
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            records.extend(("added content", finding) for finding in inspect_text(line[1:]))
    return records, len(commit_lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Privacy-safe preflight for public pull requests")
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    try:
        records, commits = audit(args.base, args.head)
    except (subprocess.CalledProcessError, ValueError, OSError):
        print("PRIVACY ERROR: unable to verify candidate Git metadata/diff; fail closed.")
        return 2
    # Print only categories and counts: no email, hostname, serial, token, or matched snippet.
    groups: dict[tuple[str, str, str], int] = {}
    for origin, finding in records:
        key = (finding.severity, origin, finding.category)
        groups[key] = groups.get(key, 0) + 1
    print(f"Privacy preflight: reviewed {commits} candidate commits.")
    for (severity, origin, category), count in sorted(groups.items()):
        print(f"PRIVACY {severity.upper()}: {origin}: {category} ({count} occurrence(s))")
    if any(finding.severity == "error" for _, finding in records):
        return 1
    print("Privacy preflight: no blocking findings (warnings require human review).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
