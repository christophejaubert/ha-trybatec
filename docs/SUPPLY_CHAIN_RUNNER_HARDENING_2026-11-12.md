# Empreintes et runners CI / Artifact hashes and runner labels

Baseline: 12 November 2026. Repository: `christophejaubert/ha-trybatec`.

## FR — Première installation Python vérifiée par SHA256

Le job `ruff-essential` installe **Ruff 0.17.4** sur Linux GitHub-hosted x86_64 avec `--require-hashes --only-binary=:all:`. Son unique paquet Python ne dépend pas d'autres distributions. La roue `ruff-0.17.4-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl` possède l'empreinte **2cd025509b2e15721b426fc70fd946d71f43b3db3b08e946dfec2d696d911690**, vérifiée sur les métadonnées officielles PyPI : https://pypi.org/project/ruff/0.17.4/.

Cette PR constitue **un premier verrouillage cryptographique limité au job Ruff**, et non un verrouillage intégral de la chaîne Python : les inventaires `constraints-pure.txt`, `constraints-ha-runtime.txt`, `constraints-ha-persistence.txt`, et les outils des autres jobs restent figés par version uniquement. Le hachage authentifie un artefact identique à celui référencé à la date de revue, sans prouver l'absence de malveillance dans la distribution ou l'index.

## FR — Images d'exécution

Tous les jobs du workflow CI principal passent de `ubuntu-latest` à `ubuntu-24.04` afin de réduire les changements implicites de génération d'OS. Le système de builds de GitHub met continuellement à jour ses machines : **ce label n'est pas un digest immutable de machine virtuelle**. Le navigateur synthétique utilise déjà une image Playwright référencée par digest `sha256:`. La validation complète du changement de runner doit s'appuyer sur les dix contrôles et la matrice Recorder/HA.

Le workflow privilégié de publication expérimentale et le contrôle d'intégrité de base ne sont pas modifiés par cette PR ; leur runner sera étudié séparément avant changement, sans déclencher de publication.

**Travaux résiduels :** générer des jeux de roues vérifiés pour les environnements 3.13/3.14 et les versions Home Assistant, avec hashes de toutes les dépendances directes et transitives, puis tester `--require-hashes` sur chaque matrice. Aucune empreinte inconnue n'est inventée. Le test `latest-homeassistant-import` reste volontairement non verrouillé.

## EN — First cryptographically checked Python install

The `ruff-essential` job installs **Ruff 0.17.4** on GitHub-hosted Linux x86_64 using `--require-hashes --only-binary=:all:` and the exact SHA256 for its official PyPI wheel: `2cd025509b2e15721b426fc70fd946d71f43b3db3b08e946dfec2d696d911690` (https://pypi.org/project/ruff/0.17.4/). Ruff has no transitive Python dependencies in this job. This verifies the package artifact against reviewed PyPI metadata, not its inherent safety.

This is an **initial narrowly scoped hash lock for Ruff**, not whole-project dependency integrity. The pure-test and Home Assistant environments still have version-only constraints. Full per-interpreter/platform wheels and transitive hashes require separate preparation and CI verification before enabling `--require-hashes` for those jobs. The intentionally floating latest-HA compatibility signal remains unpinned.

All jobs in the primary CI workflow use `ubuntu-24.04` instead of `ubuntu-latest`. It stabilizes the operating-system *release*, not the exact GitHub-hosted VM build. The browser container already uses a digest-pinned Playwright image. Privileged publication and trusted integrity workflow runner labels are unchanged pending separate safety review. No release, tag, production HA or vendor modifications.
