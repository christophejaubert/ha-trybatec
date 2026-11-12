# 🤖 Issue #110 — Provenance builds et runners / Build & runner provenance

Date de l'audit / Audit date: 2026-11-12. Périmètre / Scope: CI/CD of `christophejaubert/ha-trybatec` only.

## FR — État initial vérifié

- `main` initial : `abf1b437bd3d0c45719a15c26f18e067a23511b3`. Deux rulesets actifs : protection CI/CD de `main` et protection du résolveur de confiance.
- Dix noms de contrôles obligatoires inchangés : `pure-tests (Python 3.13)`, `pure-tests (Python 3.14)`, `ruff-essential`, `hacs`, `gitleaks`, `ha-runtime-and-storage`, `latest-homeassistant-import`, `hassfest`, `decision-persistence-gate`, `trusted-workflow-integrity`.
- Python pur : 3.13.18 / 3.14.10 ; HA runtime et persistance : Python 3.14.10, Home Assistant 2026.11.0. Les tests HA, Recorder, redémarrage, sauvegarde/restauration et comparaisons baseline/candidate sont obligatoires. Le test « latest HA » n'est volontairement pas verrouillé.
- Les cinq inventaires existants (pure, lint, ha-runtime, ha-persistence, audit) ont donné **0 avis pip-audit** dans [la CI initiale 43228428275](https://github.com/christophejaubert/ha-trybatec/actions/runs/43228428275). `zizmor` a conservé une alerte contextuelle `pull_request_target` (exit 14) : aucune exemption n'est ajoutée.
- Actions épinglées par SHA, installation `pip --require-hashes`, `pip check`, vérification des inventaires, navigateur Playwright 1.56.1 avec `package-lock.json`, `npm ci --ignore-scripts` et conteneur référencé par digest. Le runtime de pip, Node et npm fourni par les images n'est pas globalement immuable ; seuls les runtimes Python explicitement sélectionnés sont figés au niveau de la version.

## FR — Risques classés et preuves

| Observation | Qualification | Impact / réponse |
|---|---|---|
| PyRIC 0.1.6.3 n'a que `PyRIC-0.1.6.3.tar.gz` sur PyPI, SHA256 `b539b01cafebd2406c00097f94525ea0f8ecd1dd92f7731f43eac0ef16c2ccc9`, sans attestation de provenance | Démontré par PyPI | Authentification des octets source seulement |
| La CI initiale télécharge la sdist et affiche `Installing build dependencies` avant la création de la wheel | Démontré par les logs | Isolation PEP 517 et installations de build non garanties par le verrou applicatif |
| Wheels PyRIC produites dans deux jobs : chacune 407 977 octets, SHA256 respectifs `e919597bf1d8cef0ead91cac897ab542645d26e14f58c50f51bdf804e819634b` (HA runtime) et `aee2908a274d4b19f6ce23e8218b34279e00ae045ad9676f4c779506da95f676` (persistance) | Différence binaire démontrée | Ne pas déclarer une construction bit-à-bit reproductible ; cause exacte non déterminée |
| La sdist 0.1.6.3 déclare-t-elle des exigences additionnelles dynamiques dans son code de packaging ? | À vérifier depuis **la sdist publiée**, pas depuis le `master` actuel de l'amont | Pas de présomption que `setup.py` amont plus récent égale l'archive 2016 |
| `ubuntu-24.04` sélectionne la famille OS, pas le digest de VM | Limitation architecturale documentée par GitHub | Historiser `ImageOS`, `ImageVersion`, OS, architecture et noyau pour chaque job |
| Publication manuelle utilisant `ubuntu-latest` | Écart de politique constaté dans le workflow initial | Sélectionner `ubuntu-24.04`, sans changer les déclencheurs, permissions, SHA approuvé ni logique de publication |
| Compromission du dépôt ou des environnements | Non démontrée | Aucune déclaration d'incident sans preuve |

Journaux : [HA runtime](https://github.com/christophejaubert/ha-trybatec/actions/runs/43228427784/job/131217579313), [HA persistance](https://github.com/christophejaubert/ha-trybatec/actions/runs/43228427784/job/131217668274). Les deux jobs ont exécuté l'image `ubuntu-24.04` avec manifeste `ubuntu24/20261101.360` au démarrage de leurs journaux.

## FR — Atténuation implémentée et limites

1. Ajouter un sixième inventaire de sécurité `.github/ci/constraints-build.txt` pour le backend `setuptools==84.2.1`, ainsi qu'un verrou SHA256 pour sa wheel officielle `.github/ci/locks/build-py314.txt` (empreinte PyPI `ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2`).
2. Avant les trois familles de tests HA/Recorder, installer le backend depuis sa wheel avec `--require-hashes --only-binary=:all: --force-reinstall --no-cache-dir`, puis installer le graphe applicatif haché avec `--no-build-isolation`. L'objectif précis est **d'empêcher pip de télécharger automatiquement un backend PEP 517 non verrouillé dans un environnement isolé**, pas de rendre le build hermétique.
3. Conserver `pip check`, le contrôle des inventaires, les tests HA/Recorder/persistance/restauration, la vérification du source-hash et le scan `pip-audit` étendu au backend. La réussite CI doit être démontrée sur le SHA exact.
4. Ajouter la journalisation minimale des images `ImageOS` et `ImageVersion`, de `RUNNER_OS`, `RUNNER_ARCH` et de la version du noyau dans les cinq workflows, sans données personnelles, hostname, jeton ni secrets.

**Limites restantes :** le code du packaging de PyRIC peut s'exécuter pendant le build ; ni le hash source ni `--no-build-isolation` ne le rendent inoffensif. Les archives produites peuvent diverger en octets ; aucune signature, attestation SLSA, comparaison des contenus wheel ou garantie de build hors réseau n'est actuellement apportée. `pip` et les bibliothèques système de la VM restent dépendants de l'image GitHub. L'isolement des jobs et leurs permissions minimales réduisent les conséquences, sans éliminer le risque. Les seuls paquets effectivement vus comme construits depuis source dans les deux jobs audités sont PyRIC ; cela ne démontre pas l'absence d'autres sdists dans toutes les exécutions futures.

## FR — Matrice d'options runners

| Option | Isolation et sécurité PR | Reproductibilité | Coût direct et exploitation | Compatibilité HA/Recorder | Décision |
|---|---|---|---|---|---|
| GitHub-hosted `ubuntu-24.04` + journalisation de l'image | VM neuve standard, permissions minimales ; code PR exécuté sans secrets | Label OS stable, révision VM variable et désormais tracée | **0 EUR** d'exécution standard pour ce dépôt public ; maintenance fournisseur | Existante, matrice complète à conserver | **Retenir** |
| Conteneur par digest sur runner standard | Userland plus stable ; même noyau/hôte, pas une sandbox de sécurité indépendante | Améliore userspace, pas le noyau ; digest à réviser pour patchs | Hébergement standard public sans surcoût de minutes ; maintenance des tags/digests et temps de pull | Playwright déjà validé ; HA/Recorder non démontrés dans un nouveau conteneur | Limité aux jobs déjà compatibles |
| Image de VM personnalisée / larger runner | Contrôle accru du contenu, isolation gérée selon offre | Plus reproductible si image et provisioning hachés ; patching à gérer | Option payante selon tarif/configuration GitHub, coût à chiffrer avant tout engagement | Tests de compatibilité à refaire | **Ne pas engager** |
| Runner auto-hébergé | Risques de persistance et de mouvements latéraux si PR non fiable ; isolement à construire | Potentiellement maîtrisable, pas automatique | Coût matériel/hébergement/énergie + exploitation et patchs ; chiffrage non établi | Dépend entièrement de l'environnement | **Déconseillé** pour PR non fiables |

Décision : rester sur les runners standard GitHub-hosted, ne pas introduire de VM dédiée ou runner auto-hébergé, ne pas migrer HA/Recorder vers un conteneur non testé, conserver les dix statuts et les contrôles de sécurité. Aucune action payante ni modification de production ne fait partie de ce chantier.

## FR — Revue ultérieure obligatoire

- Réévaluer le risque `pull_request_target`/`zizmor` après toute modification du garde de confiance et au plus tard le **12 décembre 2026** ; conserver l'alerte visible. Le garde utilise la branche de base protégée et un jeton en lecture seule ; son architecture reste à vérifier de nouveau après modification.
- En cas de besoin de reproductibilité binaire stricte, réaliser **un chantier distinct** : contrôler le contenu exact de la sdist, toutes les dépendances PEP 517 et leur provenance, produire des wheels dans une chaîne auditée, comparer les contenus normalisés et faire respecter des hashes de wheels revus. Ne pas déclarer cette capacité comme acquise.
- Après fusion, vérifier les SHA, tous les statuts requis et la CI de `main`. Ne pas confondre développement, tests automatiques, recette métier et publication.

Références officielles : [PyPI PyRIC 0.1.6.3](https://pypi.org/project/PyRIC/0.1.6.3/), [PyPI setuptools 84.2.1](https://pypi.org/project/setuptools/84.2.1/), [pip build-system](https://pip.pypa.io/en/stable/reference/build-system/), [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/), [GitHub runner images](https://github.com/actions/runner-images), [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [facturation Actions](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

---

## EN — Verified baseline and residual risks

The baseline `main` SHA is `abf1b437bd3d0c45719a15c26f18e067a23511b3`, with ten protected required checks and official Python 3.13.18/3.14.10, Home Assistant 2026.11.0 tests, Recorder E2E and persistence/backup/restore. All five existing dependency inventories returned **zero pip-audit findings** in [run 43228428275](https://github.com/christophejaubert/ha-trybatec/actions/runs/43228428275). The contextual `zizmor` `pull_request_target` alert remains visible.

PyRIC 0.1.6.3 is **source-only on PyPI**, without provenance attestation, with source SHA256 `b539b01cafebd2406c00097f94525ea0f8ecd1dd92f7731f43eac0ef16c2ccc9`. The initial HA and persistence builds used isolated build dependencies and produced two **different wheel hashes** despite both wheels being 407,977 bytes. That proves byte-for-byte reproducibility was not achieved; it does not establish why or suggest a compromise. The actual published source archive still requires a direct packaging-manifest review before claiming the full build-requirement graph is proven. The source hash alone does not cover isolated PEP 517 backend installations.

Mitigation: the HA/Recorder jobs preinstall `setuptools==84.2.1` from its official SHA256-locked wheel, then use `--no-build-isolation` for the already hash-locked application graph. This prevents pip-managed *isolated* backend resolution; it **does not make the source build hermetic, attest its provenance, prevent all arbitrary source code execution, pin pip or the host VM, or guarantee bitwise-identical wheels**. All original functional test and lock checks stay in place. The backend gets its own sixth `pip-audit` inventory.

All workflow jobs report the GitHub-hosted image family and revision alongside OS/architecture/kernel metadata. The manual publishing workflow moves from `ubuntu-latest` to `ubuntu-24.04` while preserving owner authorization, triggers, exact-SHA checks and restricted permissions; no release is initiated. `ubuntu-24.04` is a mutable VM-image label, not an immutable image digest.

**Runner decision:** retain the GitHub-hosted standard runners (direct execution price **0 EUR** for this public repository), reuse the existing digest-pinned Playwright browser container, and **do not** adopt paid custom/larger images or self-hosted runners without a new explicit decision. Digest-pinned containers stabilize userspace but share the host kernel and require patch management; custom images and self-hosting add expense and attack/maintenance obligations. HA/Recorder container migration remains unvalidated, so no change is made.

Review the contextual protected-base `pull_request_target` risk after any trust-guard change and by **2026-12-12**. Preserve the advisory, never silently suppress it. Future strict reproducibility would require separately reviewed, trusted wheel building, source auditing, exact artifacts and binary comparison. After merge, reconcile checks on the new `main` SHA; CI success is neither real-world HA acceptance nor a publication.

Primary references and original run links are listed in the French section above.
