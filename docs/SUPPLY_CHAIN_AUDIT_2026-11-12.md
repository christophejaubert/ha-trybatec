# Audits de chaîne de livraison / Supply-chain security audits

Référence / Baseline: 12 novembre 2026. Dépôt / Repository: `christophejaubert/ha-trybatec`.

## FR — Contrôles ajoutés

Le workflow `.github/workflows/supply-chain-audit.yml` s'exécute seulement sur les PR et pushes qui touchent la CI, ses contraintes ou ce scanner, chaque lundi et sur déclenchement manuel. Son exécution est isolée (`permissions: {}`), avec Python 3.14.10 sur `ubuntu-24.04`, sans accès aux secrets du dépôt ou à Home Assistant. Il installe `pip-audit==2.10.1` et `zizmor==1.32.0`, version directe explicite, sans prétendre verrouiller leurs dépendances transitives.

- **pip-audit** interroge les avis publics pour chacun des quatre inventaires transitifs de la CI (`--no-deps --disable-pip`). Les rapports JSON publics sont conservés 14 jours en artefacts GitHub. **Les vulnérabilités détectées sont signalées, non ignorées** ; elles ne bloquent pas encore la fusion tant que les résultats initiaux n'ont pas été triés. Erreur d'exécution, sortie invalide, absence d'inventaire ou délai dépassé : échec réel du job.
- **zizmor** analyse hors réseau les workflows et la configuration Dependabot (`--offline`), sans jeton et sans correction automatique. Les constatations (codes 11 à 14) sont annotées et visibles, mais provisoirement consultatives. Erreurs d'exécution/collecte (codes 1 à 3) : échec du job.
- Les dix noms de contrôles obligatoires restent inchangés. La première analyse des vulnérabilités ne prétend pas être réussie avant l'exécution réelle. **Aucune exception silencieuse** n'est introduite ; pour devenir bloquants, les diagnostics devront être examinés et chaque exception résiduelle justifiée et assortie d'une échéance.

## FR — Empreintes SHA256 et images d'exécution

Les fichiers `constraints-*.txt` existants fixent les **versions** ; ils ne sont pas utilisables tels quels avec `pip --require-hashes`. D'après la documentation pip, cette option impose un hash pour **chaque dépendance transitive**, ainsi que les alternatives de roues et distributions compatibles. Ne pas inventer de SHA256 ni déclarer un verrouillage cryptographique sans récupérer, vérifier et réexécuter la matrice des artefacts. Un chantier distinct doit produire puis vérifier les inventaires hashés par interpréteur et plateforme ; `latest-homeassistant-import` restera volontairement mobile.

Le workflow navigateur utilise déjà une **image Playwright référencée par digest SHA256**. Les jobs GitHub-hosted sur `ubuntu-latest` utilisent des images mises à jour par GitHub : les remplacer progressivement par `ubuntu-24.04` stabilise la *version majeure de l'OS*, pas la construction exacte de la machine. Examiner cette évolution séparément afin de ne pas perturber les jobs HA/Recorder.

**Sources primaires :** https://github.com/pypa/pip-audit ; https://docs.zizmor.sh/usage/ ; https://pip.pypa.io/en/stable/topics/secure-installs/ ; https://github.com/actions/runner-images

## EN — Security audit workflow and limits

The `.github/workflows/supply-chain-audit.yml` workflow runs on security-related PRs/pushes, Mondays and manual dispatch, not every unrelated code change. It uses a version-labeled `ubuntu-24.04` runner, Python 3.14.10, zero token permissions, no production HA or vendor data, and directly pinned `pip-audit==2.10.1` and `zizmor==1.32.0` tools (their transitive packages are not hash-pinned).

- **pip-audit** scans all four complete version snapshots against public vulnerability advisories without dependency resolution; publishes 14-day JSON reports. Known findings remain visible **advisory observations** until triaged, not silent exclusions. Scanner errors or missing/invalid inputs fail the job.
- **zizmor** inspects workflow definitions and Dependabot locally in offline mode, without tokens or automated fixes. Finding exit codes 11–14 are visible as annotations but initially advisory; execution/collection failures block the job.
- All ten pre-existing mandatory check names remain unchanged. Promote reviewed findings to blocking only after assessing current exposure, justified exception expiry and CI stability.

Current constraints are **version locks**, not cryptographic locks: pip's `--require-hashes` needs artifact SHA256 hashes for *all* transitive requirements and relevant wheel alternatives. Do not fabricate hashes. A separate verified migration with per-Python/platform artifact inventories is necessary; `latest-homeassistant-import` stays intentionally floating. The Playwright container is already digest pinned; selecting `ubuntu-24.04` for hosted runners pins the OS release family, **not the exact GitHub VM image revision**.

No tags, release, production Home Assistant or vendor writes. CI is not business acceptance.

### FR — Première analyse observée (run 43204838664)

Lors du premier passage réel, `pip-audit` a relevé **40 occurrences d'avis, toutes pour `pillow==12.3.0`**, dans le lot `constraints-ha-runtime.txt` (Home Assistant 2026.10.4 et ses dépendances), et **zéro** dans les trois autres inventaires. Pillow 13.0.0 comporte des correctifs officiels, mais le framework de tests `pytest-homeassistant-custom-component==0.13.375` est lié à Home Assistant 2026.10.4 : ne pas modifier directement le seul pin Pillow sans vérifier la compatibilité et réactualiser tout l'inventaire CI. Il ne s'agit pas nécessairement de 40 bibliothèques distinctes, ni de 40 vulnérabilités exploitables dans ha-trybatec : elles doivent être attribuées à leurs paquets et aux surfaces réellement accessibles. Le scanner affiche désormais les identifiants des avis dans son journal en complément de l'artefact JSON, afin d'effectuer ce triage sans copier des données réelles.

`zizmor` a relevé quatre constats : deux délais de refroidissement Dependabot implicites inférieurs à sept jours, l'installation npm hors lockfile du navigateur synthétique, et un avertissement de forte sévérité lié à `pull_request_target` dans `trusted-workflow-integrity.yml`. Les deux valeurs de cooldown sont portées à sept jours pour les **mises à jour de version seulement** (les mises à jour de sécurité ne sont pas retardées). Les deux autres alertes restent ouvertes : le déclencheur `pull_request_target` doit être analysé dans son contexte *branche cible protégée, aucune exécution de code candidat, jeton en lecture seule* ; ce diagnostic isolé ne justifie ni suppression du contrôle ni exception silencieuse. La chaîne navigateur requiert un chantier de lockfile dédié.

### EN — First observed baseline (run 43204838664)

Initial `pip-audit` found **40 vulnerability advisory occurrences, all affecting `pillow==12.3.0`**, in the `constraints-ha-runtime.txt` inventory (Home Assistant 2026.10.4 and dependencies), and **zero** in the other three inventories. Pillow 13.0.0 includes upstream security fixes, but `pytest-homeassistant-custom-component==0.13.375` is coupled to Home Assistant 2026.10.4; changing Pillow alone without verifying dependency compatibility and refreshing the full runtime snapshot would risk CI integrity. These are not necessarily 40 distinct packages or exploitable weaknesses in ha-trybatec; review individual advisories, exposure and remediation first. Package IDs are now logged alongside the public JSON reports.

`zizmor` reported four findings: two implicit Dependabot cooldowns under seven days (now explicitly set to seven for version updates only, with security updates unaffected), the synthetic browser's unlocked npm install, and a high-severity warning for `pull_request_target` in the protected trusted guard. The latter requires context-aware review: trusted base checkout, no candidate code execution, read-only token. Do not delete this guard or conceal the finding solely to obtain green CI. A browser npm lockfile remains separate follow-on work.

**FR — Priorité :** ouvrir un chantier ciblé de compatibilité Home Assistant/Pillow pour lever ces avis ; un constat vulnérable ne devient pas 'corrigé' parce que le scanner est consultatif. Source : https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html.

**EN — Priority:** plan a separate HA/Pillow fixture compatibility update to remediate these advisories; advisory scan status does not imply a vulnerability was fixed. Source: https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html.
