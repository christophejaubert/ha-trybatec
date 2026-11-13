"""Fail-closed workflow pin and publication-contract checks.

Runs inside the read-only, mandatory ruff-essential CI job. This static guard
is not a replacement for GitHub rulesets, trusted-workflow-integrity or review.
Only repository-owned workflow files are inspected; no network or secrets.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
EXPECTED = {
    "ci.yml",
    "trusted-workflow-integrity.yml",
    "public-privacy-preflight.yml",
    "publish-experimental.yml",
    "browser-acceptance.yml",
}
PINNED_ACTION = re.compile(
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)?@[a-f0-9]{40}"
)
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)", re.MULTILINE)


def scan_workflow(name: str, source: str) -> list[str]:
    """Find unpinned external actions and unsafe supported trigger patterns."""
    problems: list[str] = []
    lines = source.splitlines()
    references = list(USES.finditer(source))
    if not references:
        problems.append("no externally pinned actions found")
    for match in references:
        action = match.group(1)
        if PINNED_ACTION.fullmatch(action) is None:
            problems.append("external action is not pinned to 40-char SHA")
    for position, line in enumerate(lines):
        match = re.match(r"^(\s*)(?:-\s*)?uses:\s*(actions/checkout@\S+)", line)
        if match is None:
            continue
        indentation = len(match.group(1))
        step: list[str] = []
        for following in lines[position + 1 :]:
            trimmed = following.lstrip()
            width = len(following) - len(trimmed)
            if width <= indentation and trimmed.startswith("- "):
                break
            step.append(following)
        if not any(re.match(r"^\s*persist-credentials:\s*false\s*(?:#.*)?$", s) for s in step):
            problems.append("checkout persists or does not explicitly disable credentials")
    if name not in {"trusted-workflow-integrity.yml", "public-privacy-preflight.yml"} and re.search(
        r"(?m)^\s{2}pull_request_target\s*:", source
    ):
        problems.append("unexpected privileged pull_request_target trigger")
    if re.search(r"(?m)^\s*permissions:\s*write-all\s*$", source):
        problems.append("global write-all token forbidden")

    if name == "trusted-workflow-integrity.yml":
        required = (
            "pull_request_target:",
            "ref: main",
            "persist-credentials: false",
            "python3 -I .github/ci/trusted_workflow_guard.py",
        )
        if not all(needle in source for needle in required):
            problems.append("trusted PR guard no longer runs base-branch-only")

    if name == "public-privacy-preflight.yml":
        # FR/EN: privileged trigger is allowed only for the exact trusted
        # base-sourced privacy scanner; never allow PR-controlled code execution.
        requirements = (
            "pull_request_target:",
            "types: [opened, synchronize, reopened, ready_for_review, edited]",
            "permissions:\n  contents: read",
            "ref: main",
            "persist-credentials: false",
            "refs/pull/$PR_NUMBER/head",
            'if [[ "$fetched" != "$PR_HEAD_SHA" ]]',
            "python3 -I scripts/public_privacy_preflight.py",
        )
        if not all(needle in source for needle in requirements):
            problems.append("privacy gate no longer runs trusted main-only scanner")
        if re.search(r"(?m)^\s{2}pull_request\s*:", source):
            problems.append("privacy gate cannot run from PR-provided workflow")
        # FR/EN: branch/path filters silently skip stacked public PRs.
        trigger = source.split("\n  pull_request_target:\n", 1)[-1].split("\npermissions:", 1)[0]
        if re.search(r"(?m)^\s*(?:branches|branches-ignore|paths|paths-ignore):", trigger):
            problems.append("privacy gate must cover PRs targeting all branches")
        if "github.event.pull_request.base.ref" in source:
            problems.append("privacy gate cannot silently skip stacked-base PRs")

    if name == "publish-experimental.yml":
        requirements = (
            "workflow_dispatch:",
            "approved_sha:",
            "github.actor == 'christophejaubert'",
            "github.ref == 'refs/heads/main'",
            "gh release create",
            "--prerelease",
            "No successful post-merge CI push on the exact approved commit",
        )
        if not all(needle in source for needle in requirements):
            problems.append("manual approved-SHA prerelease controls missing")
        if re.search(
            r"(?m)^\s{2}(?:push|pull_request|pull_request_target|schedule|release|workflow_run)\s*:",
            source,
        ):
            problems.append("publication can be triggered without manual dispatch")
    return problems


def audit(directory: Path = WORKFLOWS) -> list[str]:
    """Check all YAML workflow sources; fail on missing protected workflows."""
    findings: list[str] = []
    actual = {p.name for p in directory.glob("*.yml")}
    missing = EXPECTED - actual
    if missing:
        findings.append("missing required workflow file(s): " + ", ".join(sorted(missing)))
    for path in sorted(directory.glob("*.yml")):
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            findings.append("cannot read workflow source: " + path.name)
            continue
        for problem in scan_workflow(path.name, source):
            findings.append(path.name + ": " + problem)
    if any(directory.glob("*.yaml")):
        findings.append("unexpected .yaml workflow extension: review inclusion policy")
    return findings


def main() -> int:
    findings = audit()
    if findings:
        for problem in findings:
            print("CI policy violation: " + problem, file=sys.stderr)
        return 1
    print("CI policy verified: pinned actions, no credential persistence, "
          "protected PR guard, manual-only prerelease")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
