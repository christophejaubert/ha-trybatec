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
