"""Only synthetic data. Exercise the trusted scanner and workflow safety contract."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.public_privacy_preflight import audit, inspect_commit_email, inspect_text, main


def categories(items):
    return {(item.severity, item.category) for item in items}


def run_git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "synthetic-repository"
    repo.mkdir()
    run_git(repo, "init", "-b", "main")
    run_git(repo, "config", "user.name", "Fixture Author")
    run_git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    run_git(repo, "add", "README.md")
    run_git(repo, "commit", "-m", "base fixture")
    monkeypatch.chdir(repo)
    return repo


def test_ordinary_git_identity_is_nonblocking_d1():
    assert ("warning", "public-git-author-email") in categories(
        inspect_commit_email("ordinary@sample-domain.invalid")
    )
    assert inspect_commit_email("123+bot@users.noreply.github.com") == []
    assert ("error", "local-machine-in-git-identity") in categories(
        inspect_commit_email("fixture@synthetic-host.local")
    )


def test_fixtures_and_host_warning():
    assert inspect_text("icon@2x.png") == []
    assert inspect_text("ha.local") == []
    assert ("warning", "private-network-address") in categories(inspect_text("192.168.44.21"))
    assert ("error", "local-machine-hostname") in categories(inspect_text("my-laptop.local"))


def test_personal_paths_and_fake_tokens_without_outputting_values():
    assert ("error", "local-user-path") in categories(
        inspect_text("/Users/synthetic-person/Library/file.log")
    )
    assert inspect_text("/home/runner/work/project") == []
    fake_token = "ghp_" + "X" * 32
    detected = inspect_text("token=" + fake_token)
    assert ("error", "credential-pattern") in categories(detected)
    assert fake_token not in str(detected)


def test_fake_installation_identifier_is_advisory():
    findings = inspect_text("housingId=fakevalue123456")
    assert ("warning", "installation-identifier") in categories(findings)
    assert "fakevalue123456" not in str(findings)


def test_diverged_main_uses_merge_base_without_scanning_unrelated_commits(repository):
    base = run_git(repository, "rev-parse", "HEAD")
    run_git(repository, "checkout", "-b", "candidate")
    (repository / "candidate.txt").write_text("ordinary change\n", encoding="utf-8")
    run_git(repository, "add", "candidate.txt")
    run_git(repository, "commit", "-m", "candidate")
    head = run_git(repository, "rev-parse", "HEAD")
    run_git(repository, "checkout", "main")
    (repository / "README.md").write_text("updated main\n", encoding="utf-8")
    run_git(repository, "commit", "-am", "trusted main update")
    updated_base = run_git(repository, "rev-parse", "HEAD")
    assert updated_base != base
    records, count = audit(updated_base, head)
    assert count == 1
    assert not any(f.severity == "error" for _, f in records)


def test_commit_message_secrets_block_without_echo(repository):
    base = run_git(repository, "rev-parse", "HEAD")
    fake = "ghp_" + "Z" * 32
    (repository / "x.txt").write_text("safe fixture", encoding="utf-8")
    run_git(repository, "add", "x.txt")
    run_git(repository, "commit", "-m", "message fixture " + fake)
    head = run_git(repository, "rev-parse", "HEAD")
    records, count = audit(base, head)
    assert count == 1
    assert ("commit message", "credential-pattern") in {
        (origin, finding.category) for origin, finding in records if finding.severity == "error"
    }
    assert fake not in str(records)


def test_changed_filenames_are_scanned(repository):
    base = run_git(repository, "rev-parse", "HEAD")
    target = repository / "docs" / "fixture-machine.local"
    target.parent.mkdir()
    target.write_text("ordinary file\n", encoding="utf-8")
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-m", "filename fixture")
    records, _ = audit(base, run_git(repository, "rev-parse", "HEAD"))
    assert ("changed filename", "local-machine-hostname") in {
        (origin, finding.category) for origin, finding in records if finding.severity == "error"
    }


def test_no_history_or_incomplete_object_fails_closed(repository):
    sha = run_git(repository, "rev-parse", "HEAD")
    with pytest.raises(ValueError):
        audit(sha, sha)
    with pytest.raises(ValueError):
        audit("a" * 40, sha)
    with pytest.raises(ValueError):
        audit("../untrusted", sha)


def test_cli_never_prints_synthetic_secret(repository, capsys, monkeypatch):
    base = run_git(repository, "rev-parse", "HEAD")
    fake = "ghp_" + "B" * 32
    (repository / "x.txt").write_text("fake_token=" + fake + "\n", encoding="utf-8")
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-m", "synthetic candidate")
    head = run_git(repository, "rev-parse", "HEAD")
    monkeypatch.setattr(
        "sys.argv", ["public_privacy_preflight.py", "--base", base, "--head", head]
    )
    assert main() == 1
    output = capsys.readouterr()
    assert fake not in (output.out + output.err)
    assert "credential-pattern" in output.out


def test_workflow_uses_only_trusted_main_code():
    workflow = (
        Path(__file__).resolve().parents[1] /
        ".github/workflows/public-privacy-preflight.yml"
    ).read_text(encoding="utf-8")
    assert "pull_request_target:" in workflow
    assert "\n  pull_request:\n" not in workflow
    assert "branches: [main]" in workflow
    assert "ref: main" in workflow
    assert "persist-credentials: false" in workflow
    assert "python3 -I scripts/public_privacy_preflight.py" in workflow
    assert "PR_HEAD_SHA: " in workflow
    assert "refs/pull/$PR_NUMBER/head" in workflow
    assert "github.event.pull_request.head.sha }}" not in workflow.split("with:", 1)[1].split(
        "- name: Inspect", 1
    )[0]
    assert "permissions:\n  contents: read" in workflow

def test_intermediate_secret_is_scanned_even_when_removed(repository):
    """FR/EN: deleting a secret in a later PR commit cannot erase its history."""
    base = run_git(repository, "rev-parse", "HEAD")
    fake = "ghp_" + "Q" * 32
    (repository / "temporary.txt").write_text("token=" + fake + "\n", encoding="utf-8")
    run_git(repository, "add", "temporary.txt")
    run_git(repository, "commit", "-m", "temporary fixture")
    (repository / "temporary.txt").unlink()
    run_git(repository, "add", "-A")
    run_git(repository, "commit", "-m", "remove temporary fixture")
    records, count = audit(base, run_git(repository, "rev-parse", "HEAD"))
    assert count == 2
    assert ("added content", "credential-pattern") in {
        (origin, finding.category) for origin, finding in records if finding.severity == "error"
    }
    assert fake not in str(records)


def test_intermediate_sensitive_filename_is_scanned_even_when_removed(repository):
    """FR/EN: an intermediate personal machine filename remains public."""
    base = run_git(repository, "rev-parse", "HEAD")
    temporary = repository / "computer-fixture.local"
    temporary.write_text("safe fixture\n", encoding="utf-8")
    run_git(repository, "add", "computer-fixture.local")
    run_git(repository, "commit", "-m", "fixture filename")
    temporary.unlink()
    run_git(repository, "add", "-A")
    run_git(repository, "commit", "-m", "remove fixture filename")
    records, count = audit(base, run_git(repository, "rev-parse", "HEAD"))
    assert count == 2
    assert ("changed filename", "local-machine-hostname") in {
        (origin, finding.category) for origin, finding in records if finding.severity == "error"
    }
