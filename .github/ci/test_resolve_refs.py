"""Regression tests for dynamic CI release resolution, without network calls."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import resolve_refs as resolver


@pytest.mark.parametrize(
    ("older", "newer"),
    [
        ("0.2.0b9", "0.2.0b10"),
        ("0.2.0rc1", "0.2.0"),
        ("0.2.0a2", "0.2.0b1"),
        ("0.2.0b9", "0.3.0a1"),
        ("0.9.0", "1.0.0b1"),
    ],
)
def test_numeric_versions_sort_correctly(older, newer):
    assert resolver.version_key(older) < resolver.version_key(newer)


def test_earlier_release_ignores_drafts_and_future_versions(monkeypatch):
    releases = [
        {"tag_name": "0.2.0b8", "draft": False, "published_at": "2026-11-08T12:00:00Z"},
        {"tag_name": "0.2.0b7", "draft": True, "published_at": None},
        {"tag_name": "0.2.0b6", "draft": False, "published_at": "2026-11-07T12:00:00Z"},
        {"tag_name": "nonsense", "draft": False, "published_at": "2026-11-06T12:00:00Z"},
        {"tag_name": "0.2.0b5", "draft": False, "published_at": "2026-11-05T12:00:00Z"},
    ]
    monkeypatch.setattr(resolver, "github_api", lambda path: releases)
    assert resolver.previous_release("0.2.0b7") == "0.2.0b6"


def test_missing_history_fails_closed(monkeypatch):
    monkeypatch.setattr(resolver, "github_api", lambda path: [])
    with pytest.raises(SystemExit, match="No published earlier"):
        resolver.previous_release("0.1.0b1")


def test_annotated_tag_dereferenced_to_commit(monkeypatch):
    commit = "b" * 40
    seen = []

    def fake_api(path):
        seen.append(path)
        if path == "git/ref/tags/0.2.0b6":
            return {"object": {"type": "tag", "sha": "a" * 40}}
        if path == "git/tags/" + ("a" * 40):
            return {"object": {"type": "commit", "sha": commit}}
        raise AssertionError(path)

    monkeypatch.setattr(resolver, "github_api", fake_api)
    assert resolver.release_commit("0.2.0b6") == commit
    assert len(seen) == 2


def test_actual_candidate_sha_written_to_outputs(monkeypatch, tmp_path):
    sha = "1" * 40
    baseline = "2" * 40
    manifest = tmp_path / "custom_components/trybatec/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"version": "0.2.0b7"}), encoding="utf-8")
    output = tmp_path / "outputs.txt"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/ha-trybatec")
    monkeypatch.setenv("CANDIDATE_SHA", sha)
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setattr(resolver, "previous_release", lambda v: "0.2.0b6")
    monkeypatch.setattr(resolver, "release_commit", lambda tag: baseline)
    resolver.main()
    assert output.read_text(encoding="utf-8").splitlines() == [
        "candidate_sha=" + sha,
        "baseline_sha=" + baseline,
        "baseline_tag=0.2.0b6",
    ]


def test_public_resolver_rejects_unapproved_endpoint_without_network(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/ha-trybatec")
    def never_call(*args, **kwargs):
        raise AssertionError("External network call must not happen")
    monkeypatch.setattr(resolver.urllib.request, "build_opener", never_call)
    for endpoint in [
        "actions/secrets",
        "git/ref/tags/../../evil",
        "releases?per_page=200&page=1",
        "https://third-party.example.invalid/",
    ]:
        with pytest.raises(SystemExit, match="Unapproved"):
            resolver.github_api(endpoint)


def test_public_resolver_makes_anonymous_limited_api_request(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY", "example/ha-trybatec")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    observed = {}
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, size):
            observed["read_limit"] = size
            return b"[]"
    class FakeOpener:
        def open(self, request, timeout):
            observed["url"] = request.full_url
            observed["headers"] = dict(request.header_items())
            observed["timeout"] = timeout
            return FakeResponse()
    monkeypatch.setattr(resolver.urllib.request, "build_opener", lambda *args: FakeOpener())
    assert resolver.github_api("releases?per_page=100&page=1") == []
    assert observed["url"] == "https://api.github.com/repos/example/ha-trybatec/releases?per_page=100&page=1"
    assert "Authorization" not in observed["headers"]
    assert observed["read_limit"] == 8 * 1024 * 1024 + 1
    assert observed["timeout"] == 15


def test_workflow_release_is_manual_draft_only():
    workflow = Path(__file__).resolve().parents[1] / "workflows/ci.yml"
    data = workflow.read_text(encoding="utf-8")
    assert "publish-experimental-beta:" not in data
    assert "gh release create" in data
    assert '--draft' in data
    assert data.count("contents: write") == 1
    assert "github.event_name == 'workflow_dispatch'" in data
    assert "github.ref == 'refs/heads/main'" in data
    assert "permissions: {}" in data
    assert "GH_TOKEN: ${{ github.token }}" not in data.split("  decision-persistence-process-restart:")[0]
