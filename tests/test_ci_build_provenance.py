"""Static regression checks for #110: sdist backend integrity and VM traceability."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
BUILD_LOCK = (ROOT / ".github/ci/locks/build-py314.txt").read_text(encoding="utf-8")
BUILD_INVENTORY = (ROOT / ".github/ci/constraints-build.txt").read_text(encoding="utf-8")
SOURCE_HASH = "b539b01cafebd2406c00097f94525ea0f8ecd1dd92f7731f43eac0ef16c2ccc9"
BACKEND_HASH = "ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2"


def test_exact_source_and_build_backend_locks():
    assert BUILD_INVENTORY.splitlines()[-1] == "setuptools==84.2.1"
    assert BUILD_LOCK.splitlines()[-1] == (
        "setuptools==84.2.1 --hash=sha256:" + BACKEND_HASH
    )
    for file in ("ha-runtime-py314.txt", "ha-persistence-py314.txt"):
        locked = (ROOT / ".github/ci/locks" / file).read_text(encoding="utf-8")
        assert "pyric==0.1.6.3 --hash=sha256:" + SOURCE_HASH in locked


def test_ha_and_recorder_jobs_use_only_verified_local_build_backend():
    # Two fixtures (runtime/persistence) used in three HA/Recorder job families.
    assert CI.count("Install audited PyRIC build backend (Python 3.14)") == 3
    assert CI.count("--no-build-isolation -r ") == 3
    assert CI.count(
        "python -m pip install --require-hashes --only-binary=:all: "
        "--force-reinstall --no-cache-dir -r "
    ) == 3
    for suffix in ("ha-runtime-py314.txt", "ha-persistence-py314.txt"):
        assert "--no-build-isolation -r " in CI
        assert suffix in CI
    assert "python -m pip check" in CI
    assert "python -I ci-harness/.github/ci/lock_check.py" in CI


def test_hosted_runner_labels_and_image_provenance_logged():
    workflows = ROOT / ".github/workflows"
    for filename in (
        "ci.yml", "browser-acceptance.yml", "supply-chain-audit.yml",
        "trusted-workflow-integrity.yml", "publish-experimental.yml",
    ):
        source = (workflows / filename).read_text(encoding="utf-8")
        assert "runs-on: ubuntu-latest" not in source
        assert source.count("Journaliser image VM / Log runner image provenance") == source.count(
            "runs-on: ubuntu-24.04"
        )
        assert "ImageVersion" in source
        assert "RUNNER_ARCH" in source


def test_scanners_cover_build_backend_inventory():
    script = (ROOT / "scripts/ci_supply_chain_audit.py").read_text(encoding="utf-8")
    assert '".github/ci/constraints-build.txt"' in script
    audit = (ROOT / ".github/workflows/supply-chain-audit.yml").read_text(
        encoding="utf-8"
    )
    assert '" .github/ci/constraints-build.txt"' not in audit  # path covered by glob
    assert '".github/ci/constraints-*.txt"' in audit
