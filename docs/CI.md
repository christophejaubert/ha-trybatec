# ha-trybatec CI/CD: quality gates, security and releases

Scope: this document and CI harness change only the delivery/test infrastructure,
not the functional Home Assistant integration. Workflow source:
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

## Entry points and required checks

- **Push / pull request:** run unit tests, HA integration tests, Recorder, persistence
  regression, static analysis, Hassfest, HACS, secret scanning and compatibility checks.
- **Scheduled daily:** run compatibility checks on the default branch.
- **Manual workflow dispatch:** optionally prepare an **unpublished release draft**,
  only from `main` and only after all mandatory jobs have succeeded.
  A normal push, a PR or a scheduled job **never publishes a release**.
- **Unit tests:** Python 3.13 and 3.14; coverage report uploaded but the minimum
  coverage and full Ruff formatting are still advisory.
- **Home Assistant runtime:** isolated test fixture, synthetic portal data,
  real sensor/service behavior and a separate SQLite Recorder backend.
- **Physical decision storage:** two independent HA Core/Python processes share
  a throwaway `.storage` directory. Three scenarios are run:
  `baseline-self`, `candidate-self`, `baseline-to-candidate`.
  These also check the user's accounting correction, re-synchronization and
  invalidation after a supplier-side correction. No production HA access.
- **Recorder import E2E:** the same CI-owned contract runs on **both** the
  published baseline and the exact candidate SHA, in separate isolated Home
  Assistant environments with an actual SQLite Recorder backend. It checks
  preview-only, explicit import confirmation, queued/pending ledger, recorded
  hourly sums, duplicate-safe retry, successful verification, queue failure
  and rejection of a source meter with an unverified unit. All vendor data
  are synthetic. Neither the user's account nor production HA is accessed.

### Which source code does the persistence matrix test?

The `resolve-test-refs` job executes a trusted resolver from the audited
immutable commit `5cc64e5e58842e2eba93e4c706e6a357188dd246`,
NOT from the candidate PR. The job explicitly sets `permissions: {}`,
supplies no `GH_TOKEN` or other secrets, and uses only anonymous HTTPS GET
requests to a small allowlist of public GitHub release/tag endpoints.
Unexpected endpoints, redirects and API failures fail closed.

The candidate checkout uses the **exact PR head SHA** on PR runs
(`github.event.pull_request.head.sha`), or the triggering SHA for other
events. Its `manifest.json` is read as untrusted JSON, never executed.
The resolver selects the highest **strictly earlier** published semantic
release and resolves its tag (including annotated tags) to an immutable commit
SHA. Drafts and invalid tags are ignored. Anonymous API limits may cause a
safe CI failure; do not fix this by passing a token to candidate-controlled code.

**Maintainer caveat:** the trusted SHA must remain retrievable as Git history
during and after merges; preserve the `ci/generic-quality-gates-20261108`
branch until this resolver is rebased onto a trusted retained reference.
Never replace the SHA with a mutable PR branch or candidate SHA. This
isolates the resolver executable, but a contributor who can alter the
workflow itself can still weaken its checks; protect workflow changes via
independent trusted review or a separately owned required workflow.

Every writer, reader and harness checkout in the persistence tests is pinned to
one of these resolved SHAs. There are **no `b6`, `b7` or feature-branch names
in the matrix**. If there is no earlier released version, or a reference cannot
be resolved, the tests fail rather than claiming a successful migration.

The `recorder-e2e` job uses the same resolved immutable SHAs and executes
`integration_tests/recorder_pipeline_spec.py` for both `baseline` and
`candidate`. Its matrix is blocking: both versions must pass. The historical
b6-only checkout and mutable test environment were removed.

The `decision-persistence-gate` status is green **only if** reference
resolution, all three process-restart persistence cases **and both Recorder
E2E cases** succeed. Failure, cancellation or skipping of a required matrix
job does not yield a green gate. Its status name remains stable for future
releases and is already required by the `main` ruleset.

The E2E tests now cover the real HA importer and verifier through an isolated
SQLite Recorder (for both baseline and candidate). They do **not** prove
recovery from a physical process crash during a Recorder write, exhaustive
vendor-specific payloads or correctness against the real Trybatec API. Those
remain separate functional regression coverage requirements.

## Reproducibility versus forward compatibility

| Category | Reference / behavior |
| --- | --- |
| Python for unit tests | 3.13.18 and 3.14.10 (check labels remain 3.13 and 3.14) |
| Python for isolated HA and persistence | 3.14.10 |
| Pure-test direct packages | [`requirements-pure.txt`](../.github/ci/requirements-pure.txt) |
| Ruff | [`requirements-lint.txt`](../.github/ci/requirements-lint.txt) |
| HA runtime test framework | [`requirements-ha-runtime.txt`](../.github/ci/requirements-ha-runtime.txt) |
| Physical persistence HA Core | 2026.11.0 |
| Latest-HA compatibility job | Intentionally installs the latest available HA and current Python 3.14 patch |

The three pinned requirement files are in [`.github/ci/`](../.github/ci/).
They lock **direct tools** based on versions already demonstrated to pass in
GitHub Actions. The complete transitive Python dependency graph and
`ubuntu-latest` image are **not locked**. Accordingly, the reference jobs are
more reproducible, but not perfectly deterministic. Future hardening may generate
hash-verified, transitive lockfiles per Python version and pin the runner image.

Dependabot proposes **weekly** pull requests for both GitHub Actions and Python
tooling in `.github/ci`; it neither merges them nor publishes a release. The
Dependabot configuration becomes effective only once merged into default
branch `main`. Re-run checks on each update.

For the forward-compatibility signal, `latest-homeassistant-import` deliberately
does **not** pin the latest Home Assistant package or the Python 3.14 patch
version; it checks module imports only, not the whole runtime test suite.

## GitHub Actions security

- All third-party and first-party actions are referenced by **full 40-character
  commit SHAs**, not mutable major tags or default-branch names.
- Global `GITHUB_TOKEN`: `contents: read`. Only the manual draft-release job
  can request `contents: write`.
- Every checkout uses `persist-credentials: false`.
- Manual draft creation is serialized with a concurrency group.
- The release job validates manifest/version type, refuses an existing tag or
  release and never overwrites an earlier published artifact.

## Ruleset: Protect main - CI/CD

Verified **active** on 2026-11-08. It targets the default branch `main`,
requires a PR, resolved review conversations, up-to-date checks, squash merges,
and blocks branch deletions and force pushes. Bypass list is empty.

The nine currently required GitHub Actions status names are:

1. `pure-tests (Python 3.13)`
2. `pure-tests (Python 3.14)`
3. `ruff-essential`
4. `hassfest`
5. `hacs`
6. `gitleaks`
7. `ha-runtime-and-storage`
8. `latest-homeassistant-import`
9. `decision-persistence-gate`

The ninth required check was confirmed active in the GitHub ruleset on
2026-11-08. It now covers both the three process-restart migration scenarios
and the two full Recorder E2E cases through mandatory job dependencies.
**No additional GitHub administrative change is required** for this new
E2E matrix.

Do not remove Hassfest or bypass the branch rules to make a failing integration
appear releasable. Code/manifest corrections belong in the functional PR.

## Preparing and publishing releases

1. Validate the functional version and merge authorized changes through PRs.
2. Merge the updated delivery workflow into `main` using required checks.
3. Set the intended version in `manifest.json` through the functional workflow.
4. From **GitHub → Actions → Compatibility and tests → Run workflow**, select
   `main`, then choose `release_type=prerelease` or `stable`.
5. After all required tests pass, GitHub prepares **an unpublished draft**.
6. Publication remains a **separate, explicitly authorized step**. The current
   workflow does not publish releases automatically; an authorized publication
   mechanism may be added separately without changing the branch ruleset.

HACS/Marketplace update discovery depends on the version/tag and on publishing
a release, not merely creating a draft. This workflow does not contact or change
an installed Home Assistant instance.

## Subsequent CI/CD improvements

- Introduce complete transitive Python lockfiles with hashes per interpreter.
- Add Actionlint and comprehensive workflow-level security checks.
- Add coverage thresholds after addressing existing test debt.
- Extend interrupted Recorder-write/crash recovery tests beyond the new baseline/candidate E2E service tests.
- Keep the stable `decision-persistence-gate` mandatory when expanding matrix.
