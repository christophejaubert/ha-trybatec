"""Synthetic tests for the public privacy preflight: no real identities or secrets."""

from scripts.public_privacy_preflight import inspect_commit_email, inspect_text


def categories(items):
    return {(item.severity, item.category) for item in items}


def test_local_git_host_is_blocked_without_disclosing_its_value():
    assert ("error", "local-machine-in-git-identity") in categories(
        inspect_commit_email("builder@" + "workstation" + ".local")
    )


def test_noreply_identity_passes_and_personal_address_warns():
    assert inspect_commit_email("123+bot@users.noreply.github.com") == []
    assert ("warning", "public-git-author-email") in categories(
        inspect_commit_email("person@sample-domain.invalid")
    )


def test_synthetic_assets_and_network_fixtures():
    assert inspect_text("icon@2x.png") == []
    assert inspect_text("ha.local") == []
    assert ("warning", "private-network-address") in categories(inspect_text("ip=192.168.44.21"))


def test_local_user_path_blocks_but_runner_path_does_not():
    assert ("error", "local-user-path") in categories(inspect_text("/" + "Users/a-person/Library/private.log"))
    assert inspect_text("/home/runner/work/project") == []


def test_obvious_synthetic_credentials_are_blocked_without_static_secret_fixtures():
    fake_token = "ghp_" + "A" * 30
    assert ("error", "credential-pattern") in categories(inspect_text("token=" + fake_token))


def test_detects_ids_without_echoing_values():
    findings = inspect_text("housingId=sample23456")
    assert ("warning", "installation-identifier") in categories(findings)
    assert "sample23456" not in str(findings)
