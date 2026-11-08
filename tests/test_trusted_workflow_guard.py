"""Guard regression tests. PR-controlled data never becomes executable."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


GUARD = Path(__file__).resolve().parents[1] / ".github/ci/trusted_workflow_guard.py"
spec = importlib.util.spec_from_file_location("trusted_workflow_guard", GUARD)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def metadata(author="outside-user", head_repo="outside-user/ha-trybatec"):
    return {
        "base": {"ref": "main"},
        "user": {"login": author},
        "head": {"repo": {"full_name": head_repo}},
    }


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/ci.yml",
        ".github/ci/trusted_workflow_guard.py",
        ".github/actions/custom/action.yml",
        ".github/CODEOWNERS",
        "CODEOWNERS",
        "docs/CODEOWNERS",
        ".github/dependabot.yml",
        "scripts/ci_decision_restart.py",
        "integration_tests/recorder_pipeline_spec.py",
        "tests/test_security.py",
    ],
)
def test_protected_paths_rejected_for_external_pr(path):
    permitted, selected = guard.evaluate(metadata(), [path])
    assert not permitted and selected == [path]


def test_ordinary_external_pr_allowed():
    allowed, protected = guard.evaluate(
        metadata(), ["custom_components/trybatec/api.py", "README.md"]
    )
    assert allowed and protected == []


def test_owner_pr_with_owned_head_repo_may_change_ci_but_requires_review():
    allowed, selected = guard.evaluate(
        metadata("christophejaubert", "christophejaubert/ha-trybatec"),
        [".github/workflows/ci.yml"],
    )
    assert allowed and selected


def test_owner_impersonation_with_fork_is_rejected():
    allowed, _ = guard.evaluate(
        metadata("christophejaubert", "outsider/ha-trybatec"),
        [".github/workflows/ci.yml"],
    )
    assert not allowed


@pytest.mark.parametrize(
    "path",
    ["/.github/workflows/ci.yml", "../.github/workflows/ci.yml",
     ".github//../workflows/ci.yml", "readme\\evil", ""],
)
def test_bad_paths_fail_closed(path):
    with pytest.raises(ValueError):
        guard.sensitive_path(path)


def test_modified_base_or_missing_metadata_fails_closed():
    d = metadata()
    d["base"] = {"ref": "elsewhere"}
    with pytest.raises(ValueError):
        guard.evaluate(d, ["README.md"])
    with pytest.raises(ValueError):
        guard.evaluate({}, ["README.md"])


def test_rename_out_of_protected_directory_remains_protected(monkeypatch):
    class Resp:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self, _):
            return json.dumps([
                {"filename": "README.md", "status": "renamed",
                 "previous_filename": ".github/workflows/ci.yml"}
            ]).encode()
    class Opener:
        def open(self, request, timeout):
            assert request.full_url.startswith(
                "https://api.github.com/repos/christophejaubert/ha-trybatec/pulls/8/files"
            )
            assert timeout == 15
            return Resp()
    monkeypatch.setattr(guard.urllib.request, "build_opener", lambda *_: Opener())
    names = guard.public_pr_files(8, "fake-readonly-token")
    assert ".github/workflows/ci.yml" in names
    assert not guard.evaluate(metadata(), names)[0]


def test_security_workflow_is_from_protected_base_only():
    path = GUARD.parents[1] / ".github/workflows/trusted-workflow-integrity.yml"
    content = path.read_text(encoding="utf-8")
    assert "pull_request_target:" in content
    assert "ref: main" in content
    assert "persist-credentials: false" in content
    assert "pull-requests: read" in content
    assert "contents: read" in content
    assert "python3 -I .github/ci/trusted_workflow_guard.py" in content
    assert "pull_request.head.sha" not in content
    assert "contents: write" not in content
