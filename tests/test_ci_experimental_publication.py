"""Preflight contract for the manual experimental publication workflow.

FR : aucune publication et aucune opération externe dans ces tests.
EN: these are file-only tests, never publish or mutate a release.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISH = ROOT / ".github/workflows/publish-experimental.yml"


def test_experimental_release_title_and_tag_are_distinct():
    source = PUBLISH.read_text(encoding="utf-8")
    # The presentation title is AI-prefixed; the version/tag is unchanged.
    assert '--title "🤖 Trybatec $VERSION"' in source
    assert 'gh release create "$VERSION" --repo "$REPO"' in source
    assert 'release["tag_name"] == os.environ["VERSION"]' in source
    assert "🤖 $VERSION" not in source
    assert "gh release create \"🤖" not in source


def test_publication_stays_manual_exact_sha_and_preliminary_only():
    source = PUBLISH.read_text(encoding="utf-8")
    assert "  workflow_dispatch:" in source
    assert "  push:" not in source
    assert "  schedule:" not in source
    assert "  pull_request:" not in source
    assert "github.actor == 'christophejaubert'" in source
    assert "github.ref == 'refs/heads/main'" in source
    assert 'approved_sha != os.environ["GITHUB_SHA"]' in source
    assert "Stable releases and invalid prerelease versions are forbidden" in source
    assert 'manifest.get("version") != version' in source
    assert 'if not required.issubset(passed):' in source
    assert 'No successful post-merge CI push on the exact approved commit' in source
    assert 'gh release create "$VERSION" --repo "$REPO" --target "$APPROVED_SHA"' in source
    assert 'gh release view "$VERSION"' in source
    assert 'git/ref/tags/$VERSION' in source
    assert '--notes-file "$RUNNER_TEMP/release-notes.md"' in source
    assert 'release["draft"] is False and release["prerelease"] is True' in source
    assert 'tag["object"]["sha"] == os.environ["APPROVED_SHA"]' in source
