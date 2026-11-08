# Continuous integration and manual releases

The workflow [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) is **version-independent**. Update the version only in `custom_components/trybatec/manifest.json`, not in the workflow.

## When checks run

Checks run for every push, pull request, a daily compatibility check, and manual workflow runs. They include:

- Pytest on Python 3.13 and 3.14, with branch coverage reporting (no minimum threshold yet).
- Python compilation, manifest validation, selected privacy patterns and image dimensions.
- Ruff essential errors as blocking checks; broader lint and formatting reports are initially advisory.
- Home Assistant Hassfest and HACS repository validation.
- Gitleaks detection of accidentally committed secrets.
- Import of integration modules with the latest available Home Assistant release.
- A separate Home Assistant test runner (`ha-runtime-and-storage`) using `pytest-homeassistant-custom-component`: real integration setup, sensor states and unload, admin-only service authorization, configuration flow, and review-decision Store reads. Tests use synthetic vendor responses and do not perform external requests.
- A real Home Assistant recorder test with an isolated SQLite database: round-trip of hourly external statistics, duplicate import retry, and bucket verification.
- Real on-disk review-decision durability: a separate CI matrix (b6→b6,
  b7→b7, b6→b7) starts two distinct Home Assistant Core/Python processes
  using a shared temporary .storage directory. It validates an approved
  synthetic accounting correction, original index fingerprint, justification,
  re-synchronization and invalidation if the supplier changes the index.
  No real account or personal Home Assistant instance is accessed.

Runtime tests exercise real Home Assistant code and a real, isolated Recorder statistics backend. They **do not** contact a live Trybatec account, alter a personal Home Assistant installation, or yet verify every historical import/repair path end-to-end. The Home Assistant test harness virtualizes the storage directory, so the decision Store test verifies save/read via Home Assistant APIs, not physical disk endurance across a process restart.

## How to prepare a release

1. Merge the approved changes into `main` after the required CI checks pass.
2. Check that `custom_components/trybatec/manifest.json` contains the intended version.
3. Go to **GitHub → Actions → Compatibility and tests → Run workflow** and select `main`.
4. Choose `release_type=prerelease` for `X.Y.ZbN`, `aN` or `rcN`; choose `stable` for `X.Y.Z`.
5. The workflow checks everything again and, only on success, **creates a draft release**. An existing tag or release cannot be overwritten.
6. Review the release draft in GitHub, then **publish it manually**. No normal push, pull request or scheduled run publishes anything.

## Security of the pipeline

- GitHub Actions are pinned to verified full 40-character Git commit SHAs. This
  prevents a moved major-version tag or branch from silently replacing a step.
- GitHub's `GITHUB_TOKEN` receives `contents: read` by default. Only the
  explicitly invoked release-draft job receives `contents: write`, which is
  not available to regular push/PR tests. The draft is **not published**.
- Checkout steps use `persist-credentials: false`, so later test commands
  do not receive retained repository credentials.
- Release-draft creation is serialized to avoid competing manual operations.
- `.github/dependabot.yml` proposes weekly GitHub Actions dependency updates,
  as PRs with checks, without auto-merge. Dependabot **only becomes operational
  once its configuration is in the default branch (`main`)**.
- These are SHA pins, not GitHub workflow dependency lockfiles. A full action
  dependency lockfile would offer additional transitive-dependency guarantees.

## Protect `main` (repository administrator action)

As of 2026-11-08, `main` is **not protected** and no GitHub ruleset is configured.
The ChatGPT GitHub connection can write repository files but has **no repository
administration operation for setting branch protection**. An administrator must
complete the following in the GitHub web interface:

1. Open `https://github.com/christophejaubert/ha-trybatec/settings/rules`.
2. Select **New ruleset → New branch ruleset**.
3. Use a descriptive name (for example `Protect main CI`), set enforcement to
   **Active**, and target only the default branch `main`.
4. Require a pull request before merging. Require resolution of conversations;
   do not enable a mandatory independent reviewer if there is no other
   eligible reviewer (the author cannot approve their own PR).
5. Require successful status checks from GitHub Actions. Once the new workflow
   is merged and check names have appeared, select:
   - `pure-tests (Python 3.13)`
   - `pure-tests (Python 3.14)`
   - `ruff-essential`
   - `hassfest`
   - `hacs`
   - `gitleaks`
   - `ha-runtime-and-storage`
   - `decision-persistence (b6-to-b6)`
   - `decision-persistence (b7-to-b7)`
   - `decision-persistence (b6-to-b7)`
   - `latest-homeassistant-import`
6. Block force pushes and deletions; prevent bypassing the checks under normal
   operation. Decide whether requiring up-to-date branches is appropriate.
7. Save the ruleset and confirm that `main` reports as protected.

**Important:** The current `feature/0.2.0b7` manifest fails Hassfest for
missing Recorder dependency declaration. Do not mark this as passing, exclude
Hassfest, or bypass branch protections. Resolve it separately in integration
development before the full CI can pass. If the release workflow is installed
on `main`, the controlled release remains accessible through the manual
`workflow_dispatch`, without direct source pushes.

Protecting `main` does not prevent correctly authorized creation of releases
and tags. If stronger tag integrity is required, add a separate tag ruleset
targeted at release-version tags after reviewing the required publishing identity.

## Follow-up improvements

- Extend real-HA tests to cover complete approved historical imports and interrupted Recorder writes. Two-process disk persistence and synthetic resynchronization are tested separately; a full HA service/UI reboot is outside their scope.
- Resolve observed Home Assistant sensor warnings about annual estimate sensor device/state class combinations; avoid silently changing their statistics semantics.
- Review the baseline code-coverage report before choosing a mandatory minimum.
- Make Ruff's full lint rules blocking after resolving existing diagnostics.
- Maintain a Python and Home Assistant compatibility matrix reflecting supported environments.
- Pin third-party action commit SHAs as a further supply-chain hardening measure.
