"""Offline checks for the scope of initial artifact-hash and runner-label hardening."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ruff_linux_wheel_sha256_is_explicit():
    raw = (ROOT / ".github/ci/requirements-lint.txt").read_text(encoding="utf-8")
    assert "ruff==0.17.4" in raw
    match = re.findall(r"--hash=sha256:([a-f0-9]{64})", raw)
    assert match == ["2cd025509b2e15721b426fc70fd946d71f43b3db3b08e946dfec2d696d911690"]


def test_core_ci_runner_and_lint_install_enforcement():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "runs-on: ubuntu-latest" not in workflow
    assert workflow.count("runs-on: ubuntu-24.04") >= 8
    assert (
        "python -m pip install --require-hashes --only-binary=:all: "
        "-r .github/ci/requirements-lint.txt -c .github/ci/constraints-lint.txt"
    ) in workflow
    assert "python -I .github/ci/lock_check.py .github/ci/constraints-lint.txt" in workflow
    assert "Enforce zero unused imports and locals in cleaned source and test modules" in workflow
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in workflow
