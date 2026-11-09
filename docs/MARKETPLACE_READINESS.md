# Marketplace readiness — lot A: repository conformity

Scope: repository structure, manifests, branding files, version consistency and install-package metadata. This is a **preliminary audit** against official Home Assistant / HACS Marketplace guidance consulted on 2026-11-09. It is **not** approval for production use, merging, a stable release or submitting to the public catalog.

Tracking: [issue #39](https://github.com/christophejaubert/ha-trybatec/issues/39).

## Verified by repository inspection (base `a29fd1526899a4ff45b0e302adf35d204719877f`)

- The repository is public and not archived; the default branch is `main`.
- The repository has a description, topics, GitHub Issues and MIT license.
- One integration is present at `custom_components/trybatec/`, with `__init__.py`, `manifest.json`, `sensor.py`, a `brand/` directory and English/French translations.
- `README.md` and `hacs.json` are at the root.
- Manifest includes `domain=trybatec`, `version=0.2.0b14` on the inspected base, `documentation`, `issue_tracker`, `codeowners`, categories and configuration-flow settings.
- `hacs.json` includes a display name. The legacy `render_readme` option is kept for compatibility with older HACS; Marketplace ignores unrecognized keys.
- Local branding files `brand/icon.png` and `brand/icon@2x.png` are present. CI includes a dimension check for 256×256 and 512×512.
- Existing CI file `.github/workflows/ci.yml` defines `hacs` and `hassfest` jobs. **Their successful execution on a release candidate is not proven by the presence of the jobs.**
- Review decisions use Home Assistant's `homeassistant.helpers.storage.Store`, which persists in the Home Assistant configuration storage, **outside** the integration directory. Therefore no `persistent_directory` key is currently needed to protect these decisions.

## Changes in this lot A PR

- Replace false / stale b7-as-latest statements with a link to the manifest and releases, while retaining b7 notes explicitly as archived history.
- Remove an obsolete `#readme` anchor from the manifest's documentation URL.
- Add an official My Home Assistant Marketplace link (available starting with 2026.11), retaining HACS instructions for older installations.
- Clarify that the repository already exists, and link this conformity checklist from the README.

## Pending verification before stable release or catalog submission

- [ ] Run and examine HACS Action and hassfest on the **exact candidate SHA**, with no ignored validation checks.
- [ ] Validate manifest categories, dependency semantics and `integration_type` using hassfest and runtime tests; do not change them based on conjecture.
- [ ] Confirm actual PNG encoding, compression, visual quality and absence of misleading branding; passing a dimensions script does not prove all image requirements.
- [ ] Validate the distribution archive size (<= 100 MiB) and file count (<= 50,000).
- [ ] Establish and test the **minimum Home Assistant version** before adding `homeassistant` to `hacs.json`. Do not guess a value.
- [ ] Decide whether to enable `hide_default_branch` only after reviewing impact on current prerelease installations and development workflows. It is **not** essential to meet the catalog's minimum requirements.
- [ ] Confirm whether a geographic restriction exists before adding `country`.
- [ ] Do not enable `zip_release` unless a tested release asset is required.
- [ ] Check installation, updates and data persistence using a **separate test Home Assistant**, not the production installation.
- [ ] Keep `manifest.json`, release tag, release notes and published version coherent for the stable release.
- [ ] Check whether the Trybatec service permits the proposed third-party use before broader public distribution.
- [ ] Submit to `hacs/default` **only** after full release qualification and separate explicit authorization.

## Official references

- [Repository structure](https://contributors.home-assistant.io/marketplace/reference/repository-structure/)
- [hacs.json fields](https://contributors.home-assistant.io/marketplace/reference/hacs-json/)
- [Validation checks](https://contributors.home-assistant.io/marketplace/reference/validation/)
- [Custom integration publishing](https://contributors.home-assistant.io/marketplace/guides/integrations/)
- [Catalog submission](https://contributors.home-assistant.io/marketplace/guides/catalog/)
- [Integration branding](https://contributors.home-assistant.io/core/integrations/brands/)

Notes: no API credentials, customer data or external automation are required for this audit. Further status changes must be evidence-based and should be recorded on issue #39.
