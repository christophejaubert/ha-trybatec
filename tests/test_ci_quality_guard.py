"""Regression tests for mandatory GitHub workflow safety contracts."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

POLICY = Path(__file__).resolve().parents[1] / ".github" / "ci" / "quality_guard.py"
_spec = spec_from_file_location("ci_quality_guard", POLICY)
assert _spec is not None and _spec.loader is not None
policy = module_from_spec(_spec)
_spec.loader.exec_module(policy)

PIN = "a" * 40
SAFE = (
    "name: Test\non:\n  push:\npermissions: {}\njobs:\n"
    "  test:\n    steps:\n      - uses: actions/checkout@" + PIN + "\n"
    "        with:\n          persist-credentials: false\n"
)


def test_actual_workflows_follow_guard():
    assert policy.audit() == []


def test_mutable_tag_ref_fails_closed():
    assert policy.scan_workflow("ci.yml", SAFE.replace("@" + PIN, "@v4"))


def test_checkout_must_not_persist_token():
    assert policy.scan_workflow(
        "ci.yml", SAFE.replace("persist-credentials: false", "persist-credentials: true")
    )


def test_external_privileged_pr_trigger_fails():
    assert policy.scan_workflow(
        "ci.yml", SAFE.replace("  push:", "  pull_request_target:")
    )


def test_manual_publication_requires_controls():
    assert policy.scan_workflow("publish-experimental.yml", SAFE)


def test_missing_workflow_is_a_failure(tmp_path):
    (tmp_path / "ci.yml").write_text(SAFE, encoding="utf-8")
    assert any("missing required" in item for item in policy.audit(tmp_path))


def test_named_step_uses_syntax_and_checkout_protection():
    named = SAFE.replace(
        "      - uses: actions/checkout@",
        "      - name: Checkout source\n        uses: actions/checkout@",
    )
    assert policy.scan_workflow("ci.yml", named) == []
    assert policy.scan_workflow(
        "ci.yml", named.replace("persist-credentials: false", "persist-credentials: true")
    )


def test_privacy_workflow_can_only_use_trusted_default_branch():
    source = (
        Path(__file__).resolve().parents[1] /
        ".github/workflows/public-privacy-preflight.yml"
    ).read_text(encoding="utf-8")
    assert policy.scan_workflow("public-privacy-preflight.yml", source) == []
    assert policy.scan_workflow(
        "public-privacy-preflight.yml",
        source.replace("ref: main", "ref: candidate"),
    )
    assert policy.scan_workflow(
        "public-privacy-preflight.yml",
        source.replace("persist-credentials: false", "persist-credentials: true"),
    )
    assert policy.scan_workflow(
        "public-privacy-preflight.yml",
        source.replace("python3 -I scripts/public_privacy_preflight.py", "echo bypass"),
    )
    assert policy.scan_workflow(
        "public-privacy-preflight.yml",
        source.replace("pull_request_target:", "pull_request:"),
    )
    assert policy.scan_workflow(
        "public-privacy-preflight.yml",
        source.replace("permissions:\n  contents: read", "permissions: write-all"),
    )


def test_privacy_guard_rejects_stacked_branch_filter():
    source = (
        Path(__file__).resolve().parents[1] /
        ".github/workflows/public-privacy-preflight.yml"
    ).read_text(encoding="utf-8")
    assert policy.scan_workflow("public-privacy-preflight.yml", source) == []
    filtered = source.replace(
        "  pull_request_target:\n",
        "  pull_request_target:\n    branches: [main]\n",
    )
    assert any("must cover PRs targeting all branches" in issue for issue in
               policy.scan_workflow("public-privacy-preflight.yml", filtered))
    skipped = source.replace(
        "    runs-on: ubuntu-24.04",
        "    if: ${{ github.event.pull_request.base.ref == 'main' }}\n"
        "    runs-on: ubuntu-24.04",
    )
    assert any("cannot silently skip" in issue for issue in
               policy.scan_workflow("public-privacy-preflight.yml", skipped))
