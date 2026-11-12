# CI — Verrouillage et limites / Locking and limits

## FR — Décisions et preuves (12 novembre 2026)

**Périmètre : CI isolée uniquement.** Aucun accès au fournisseur Trybatec, à Recorder réel, aux préférences Énergie ou à Home Assistant de production. Les tests automatisés ne valent pas recette métier.

| Environnement | Verrou vérifié | Portée |
| --- | --- | --- |
| Tests purs Python 3.13 | `.github/ci/locks/pure-py313.txt` | 16 distributions Linux x86_64 |
| Tests purs Python 3.14 | `.github/ci/locks/pure-py314.txt` | 16 distributions Linux x86_64 |
| Fixtures HA/Recorder 2026.11.0 | `.github/ci/locks/ha-runtime-py314.txt` | 121 distributions Python 3.14 x86_64 |
| Persistance et restauration | `.github/ci/locks/ha-persistence-py314.txt` | 103 distributions Python 3.14 x86_64 |
| Ruff | `.github/ci/requirements-lint.txt` | Wheel Ruff Linux x86_64 |
| Audit pip-audit / zizmor | `.github/ci/locks/audit-py314.txt` | 28 distributions Python 3.14 x86_64 |
| Tests navigateur | `scripts/browser-ci/package-lock.json` | npm ci, scripts désactivés, conteneur Playwright référencé par digest |

Les ensembles Python ci-dessus couvrent les dépendances **directes et transitives de l'environnement installé** : versions fixes, empreintes des archives officielles PyPI vérifiées par comparaison aux octets téléchargés, puis `pip install --require-hashes`, `pip check` et contrôle exhaustif d'inventaire. Les hachages correspondent à l'interpréteur, à la plateforme et à l'archive sélectionnée. Ne pas les présenter comme universels pour Windows, macOS ou ARM64.

Le framework de test officiel `pytest-homeassistant==2026.11.0` remplace l'ancienne fixture 0.13.375. Le snapshot de test utilise Pillow 13.0.0 et son scan `pip-audit` ne signale plus les 40 anciens avis de Pillow 12.3.0. Les scans couvrent aussi les outils d'audit eux-mêmes. Le rapport `zizmor` reste consultatif et signale le garde `pull_request_target`, vérifié exclusivement depuis `main`, sans exécution du code PR et avec token en lecture seule ; ne pas le désactiver pour obtenir un résultat vert.

### Limites matérielles restantes

1. **Archives source et construction isolée.** PyRIC 0.1.6.3 est une archive source : son SHA256 protège l'entrée téléchargée, **pas automatiquement** les outils de build téléchargés dans un environnement PEP 517 isolé, ni la reproductibilité binaire du wheel construit. Le mode `--only-binary=:all:` n'est pas actuellement applicable à tout le graphe. `--no-build-isolation` n'est pas un correctif gratuit : il exige le contrôle préalable de tous les outils de compilation.
2. **VM GitHub-hosted.** `runs-on: ubuntu-24.04` choisit une version d'OS, **pas un digest immuable**. GitHub met à jour les images hébergées chaque semaine. Les actions elles-mêmes sont référencées par SHA. La CI navigateur utilise déjà un conteneur par digest, mais les autres jobs dépendent de l'image hôte.
3. **Choix pour le moment.** Conserver les runners éphémères hébergés et les tests de non-régression plutôt que migrer précipitamment des exécutions de PR non fiables vers un runner autohébergé. Évaluer un conteneur Python/HA digéré et ses dépendances système dans une PR séparée, avec audit d'accès et compatibilité Python 3.13/3.14, Recorder et restaurations. Les images personnalisées de *larger runners* sont une option conditionnée par l'offre GitHub et sa gouvernance.
4. **Mises à jour.** Chaque changement de version, plateforme, ABI ou paquet impose la régénération des empreintes depuis la distribution officielle, un `pip check`, l'audit de vulnérabilités et tous les contrôles requis sur le SHA exact. Ne jamais contourner le résolveur ni ignorer des avis non qualifiés.

**Statut :** verrouillage des distributions installées en CI vérifié ; verrouillage cryptographique complet de l'environnement de build et de la VM **non démontré**. Limites suivies dans l'issue #105. Toute publication reste manuelle.

Sources officielles :
- GitHub, *GitHub-hosted runners* : https://docs.github.com/en/actions/concepts/runners/github-hosted-runners
- GitHub, *runner-images* : https://github.com/actions/runner-images
- pip, *Secure installs* : https://pip.pypa.io/en/stable/topics/secure-installs/
- pip, *Build System Interface* : https://pip.pypa.io/en/stable/reference/build-system/

---

## EN — Verified scope and residual risks (2026-11-12)

**CI only, never production HA or vendor data.** The table above lists the exact Python 3.13/3.14 Linux x86_64 installed-distribution SHA256 locks, the independently hash-checked Ruff wheel, npm Playwright lockfile and digest-pinned browser container. Exact versions, hashes checked against official PyPI bytes, `--require-hashes`, `pip check` and whole-inventory checks protect direct and transitive **installed** dependencies. These hashes are not universal across operating systems, architectures or interpreter ABIs.

Official `pytest-homeassistant==2026.11.0` moves the isolated HA test graph to Pillow 13.0.0; `pip-audit` no longer reports the old 40 Pillow 12.3.0 findings. Audit tooling is itself hash-locked and scanned. The existing `pull_request_target` workflow uses protected-base source, read-only access and no candidate checkout/execution, with the contextual `zizmor` warning retained.

**Residual limitations:** (1) A verified source archive hash, notably for PyRIC, does not cryptographically pin the isolated PEP 517 build-time toolchain or prove wheel build reproducibility; `--no-build-isolation` requires a separately controlled build environment. (2) GitHub-hosted `ubuntu-24.04` labels are not immutable VM digests, and GitHub refreshes runner images weekly. (3) Digest-pinned Python/HA containers or managed custom runner images need separate compatibility and security review before adoption; switching untrusted PR execution to self-hosted infrastructure without a threat model is not justified. (4) Every platform, version or ABI change requires fresh official artifact authentication and exact-head tests.

**Conclusion:** installed Python/npm packages are locked for the tested CI environments; full build/runner image immutability is **not established**. Track residual risks in #105. No production writes, release publication or real-world business acceptance.
