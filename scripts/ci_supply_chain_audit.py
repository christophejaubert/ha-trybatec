"""CI-only reports for known vulnerabilities and GitHub Actions misconfigurations.

The initial baseline is advisory on *findings* but fails on scanner execution,
parse, timeout and missing-input errors. It never fixes or installs dependencies.
Network access is used by pip-audit solely to query public package advisories.
zizmor runs fully offline. No credentials or real Home Assistant data.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ".github/ci/constraints-pure.txt",
    ".github/ci/constraints-lint.txt",
    ".github/ci/constraints-ha-runtime.txt",
    ".github/ci/constraints-ha-persistence.txt",
)
MAX_OUTPUT = 6 * 1024 * 1024
MAX_FINDINGS = 1200
SAFE_NAME = re.compile(r"^[a-zA-Z0-9_.-]{1,128}$")


def run_command(args: list[str], timeout: int = 240) -> tuple[int, str, str]:
    """Execute an explicitly fixed tool command, never data-derived shell text."""
    completed = subprocess.run(
        args, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
        check=False, shell=False,
    )
    if len(completed.stdout) > MAX_OUTPUT or len(completed.stderr) > MAX_OUTPUT:
        raise ValueError("Security tool produced an oversized report")
    return completed.returncode, completed.stdout, completed.stderr


def parse_findings(output: str) -> tuple[dict, int]:
    doc = json.loads(output)
    if not isinstance(doc, dict) or not isinstance(doc.get("dependencies"), list):
        raise ValueError("Invalid pip-audit JSON schema")
    count = 0
    for item in doc["dependencies"]:
        if not isinstance(item, dict) or not isinstance(item.get("vulns"), list):
            raise ValueError("Invalid dependency vulnerability record")
        if not SAFE_NAME.fullmatch(str(item.get("name", ""))):
            raise ValueError("Unexpected dependency name")
        count += len(item["vulns"])
        if count > MAX_FINDINGS:
            raise ValueError("Unbounded security findings")
    return doc, count


def audit_dependencies() -> int:
    report_dir = Path(os.environ["RUNNER_TEMP"]) / "trybatec-security-reports"
    report_dir.mkdir(mode=0o700, exist_ok=True)
    total = 0
    for filename in FILES:
        path = ROOT / filename
        if not path.is_file() or not path.read_text(encoding="utf-8").strip():
            raise ValueError("Missing or empty pinned dependency inventory")
        code, out, err = run_command(
            ["pip-audit", "--no-deps", "--disable-pip", "--format=json",
             "--progress-spinner=off", "-r", filename], timeout=300,
        )
        if code not in (0, 1):
            raise ValueError(f"pip-audit failed (exit {code}): {err[:400]}")
        report, n = parse_findings(out)
        if code == 0 and n or code == 1 and not n:
            raise ValueError("pip-audit exit code contradicts parsed findings")
        basename = path.name
        if not SAFE_NAME.fullmatch(basename):
            raise ValueError("Unexpected inventory filename")
        (report_dir / (basename + ".json")).write_text(
            json.dumps(report, separators=(",", ":")) + "\n", encoding="utf-8",
        )
        total += n
        print(f"pip-audit {basename}: {len(report['dependencies'])} packages, {n} findings")
        for package in report["dependencies"]:
            vulnerabilities = package["vulns"]
            if not vulnerabilities:
                continue
            version = str(package.get("version", ""))
            if not SAFE_NAME.fullmatch(version):
                raise ValueError("Unexpected package version in audit")
            ids = []
            for item in vulnerabilities:
                value = str(item.get("id", "")) if isinstance(item, dict) else ""
                if not SAFE_NAME.fullmatch(value):
                    raise ValueError("Unexpected advisory ID")
                ids.append(value)
            print(f"  {package['name']}=={version}: {len(ids)} advisories ({', '.join(ids[:12])})")
    if total:
        print(f"::warning title=Dependency vulnerabilities::Found {total} known vulnerabilities across four pinned CI inventories; inspect artifact and review before enforcing.")
    append_summary(f"pip-audit: {total} reported vulnerability occurrences across {len(FILES)} inventories (advisory baseline).")
    return 0


def audit_workflows() -> int:
    inputs = [".github/workflows", ".github/dependabot.yml"]
    for name in inputs:
        if not (ROOT / name).exists():
            raise ValueError("Missing workflow audit input")
    code, out, err = run_command(
        ["zizmor", "--offline", "--strict-collection", "--format=github", *inputs],
        timeout=180,
    )
    if code not in (0, 11, 12, 13, 14):
        raise ValueError(f"zizmor execution/collection failed (exit {code}): {err[:400]}")
    print(out[:MAX_OUTPUT])
    if code:
        print(f"::warning title=Workflow findings::zizmor reported findings (exit {code}); review annotations before enforcing.")
    append_summary(f"zizmor: exit {code} (0 = no findings, 11–14 = findings; advisory baseline).")
    return 0


def append_summary(line: str) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as file:
            file.write("- " + line + "\n")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if os.environ.get("GITHUB_ACTIONS") != "true" or len(args) != 1:
        print("CI only: dependencies|workflows", file=sys.stderr)
        return 2
    try:
        if args[0] == "dependencies":
            return audit_dependencies()
        if args[0] == "workflows":
            return audit_workflows()
        raise ValueError("Unsupported security audit mode")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(f"Security scanner infrastructure failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
