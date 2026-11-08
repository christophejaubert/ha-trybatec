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

These checks **do not** reproduce a real Home Assistant system, Recorder persistence, actual sensors or a live Trybatec account. Functional and integration tests must be developed separately.

## How to prepare a release

1. Merge the approved changes into `main` after the required CI checks pass.
2. Check that `custom_components/trybatec/manifest.json` contains the intended version.
3. Go to **GitHub → Actions → Compatibility and tests → Run workflow** and select `main`.
4. Choose `release_type=prerelease` for `X.Y.ZbN`, `aN` or `rcN`; choose `stable` for `X.Y.Z`.
5. The workflow checks everything again and, only on success, **creates a draft release**. An existing tag or release cannot be overwritten.
6. Review the release draft in GitHub, then **publish it manually**. No normal push, pull request or scheduled run publishes anything.

## Main branch protection (manual GitHub setting)

In **Settings → Rules → Rulesets**, create a rule for `main` that requires pull requests and successful CI checks. Consider preventing direct pushes and including administrators in the rule. Repository administration settings are not changed by this PR.

## Follow-up improvements

- Add integration tests for the configuration flow, sensors, services and Recorder.
- Review the baseline code-coverage report before choosing a mandatory minimum.
- Make Ruff's full lint rules blocking after resolving existing diagnostics.
- Maintain a Python and Home Assistant compatibility matrix reflecting supported environments.
- Pin third-party action commit SHAs as a further supply-chain hardening measure.
