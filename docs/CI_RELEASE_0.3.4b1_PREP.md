# Publication 0.3.4b1 — Préparation CI/CD / Release readiness

## FR — Contrats vérifiés au 12 novembre 2026

**La version 0.3.4b1 est proposée, pas approuvée pour publication.** Aucune release ne doit être déclenchée par cette branche ou cette PR.

Le workflow `.github/workflows/publish-experimental.yml` ne répond qu'à `workflow_dispatch`, limite l'acteur à `christophejaubert`, la branche à `main`, exige une version `a/b/rc` et un SHA de 40 caractères correspondant exactement à la révision `main` vérifiée. Il refuse un manifeste non concordant, une release ou un tag existant, l'absence d'une CI **push** complète sur le SHA autorisé, ou un contrôle obligatoire manquant. Il publie une seule préversion approuvée, note le SHA et vérifie la cible du tag. Le titre affiché doit être `🤖 Trybatec VERSION`, tandis que le tag et le numéro restent `VERSION`, sans emoji. Les notes sont chargées depuis `RELEASE_NOTES_BETA.md` et ne doivent contenir aucune donnée privée.

**Correction de cette PR :** uniquement le préfixe du *titre* de release expérimentale, avec tests de non-régression de l'autorisation manuelle, de l'identité du tag, de la cible SHA et de la conservation du fichier de notes. Le mécanisme `draft-release` de `ci.yml` qui couvre aussi les versions stables n'est pas modifié.

**État initial du dépôt :** `main` = `a1bd6d8558c8fe1cc13cadeb1ff4aaa20528dc53` (contrôles de push #43273136693 réussis) ; `manifest.json` indique `0.3.3b1` et la première section de `RELEASE_NOTES_BETA.md` concerne `0.3.3b1`, non `0.3.4b1`. Les notes de cette première section sont en français et la présence d'une rédaction FR/EN complète **n'est pas démontrée**. Le workflow actuel vérifie l'en-tête de version et la longueur, **pas** automatiquement la présence de deux sections linguistiques : la revue humaine FR/EN est une condition explicite de publication.

### Conditions avant autorisation distincte de publication

1. Périmètre de version intégré à `main` confirmé par la MOE, mécanismes non qualifiés exclus ; aucun nettoyage/migration identitaire ou écriture Recorder/Énergie non approuvée.
2. Version `0.3.4b1` expressément approuvée, présente à l'identique dans le manifeste, avec notes et changements **FR/EN**, risques et restrictions expurgés.
3. SHA de `main` exact et approuvé ; tous les **dix contrôles GitHub obligatoires** sur les PR et l'intégralité des jobs de la CI post-fusion `push` sur ce SHA, incluant Python 3.13/3.14, Ruff, gitleaks, HACS, Hassfest, HA/Recorder, persistance et restauration. CodeQL et le scan supply-chain doivent aussi être vérifiés, en tenant compte des déclenchements effectifs de chaque workflow.
4. Échec gitleaks de la planification #43254529863 traité par la PR indépendante, puis **vérifié en balayage historique**, sans masquer de secret ni supprimer des protections. Une réussite sur une plage d'un commit seulement ne suffit pas.
5. Notes expurgées : pas de jeton, URL privée, adresse personnelle, identifiant matériel, données de consommation, diagnostic de l'installation réelle, logs bruts ou preuves confidentielles ; aucun tag/release préexistant à écraser.
6. Autorisation spécifique et distincte pour **publication**, avec version, SHA, notes et risques. Cette PR ne constitue pas cette autorisation. Une CI réussie n'autorise jamais la fusion, l'installation sur Home Assistant ni la publication.

**Point hors périmètre :** `ci.yml` comporte aussi un créateur de *draft* manuel pour `prerelease` ou `stable` avec un titre `Trybatec VERSION`. La présente intervention ne le modifie pas, conformément à l'exclusion des mécanismes stables ; une éventuelle harmonisation doit être autorisée séparément.

Preuves : [CI push](https://github.com/christophejaubert/ha-trybatec/actions/runs/43273136693), [gitleaks planifié](https://github.com/christophejaubert/ha-trybatec/actions/runs/43254529863), [règles du dépôt](https://github.com/christophejaubert/ha-trybatec/rules).

## EN — CI/CD readiness for a proposed 0.3.4b1

**0.3.4b1 has not been approved for release.** The experimental workflow is manual-only, restricted to the repository owner on `main`, checks the approved 40-digit SHA and prerelease version against the checked-out manifest, requires matching release notes and a successful exact-SHA post-merge push CI with every listed critical job, rejects existing releases/tags and verifies the resulting tag after publication. This change only prefixes the **display title** with `🤖 `; the tag, version, notes file and exact-SHA checks remain untouched. The separate stable-capable draft workflow in `ci.yml` remains out of scope.

At the audited baseline `a1bd6d8558c8fe1cc13cadeb1ff4aaa20528dc53`, the manifest and leading release notes still describe **0.3.3b1**, not 0.3.4b1. The workflow checks note headers and length but not bilingual completeness; the release owner must verify and approve genuinely bilingual FR/EN public notes with sensitive data removed. Before any independent publication authorization: reconcile the exact integrated and qualified scope, approve a version and SHA, verify ten protected checks plus exact post-merge HA/Recorder/persistence/restore CI, confirm historical Gitleaks scanning and CodeQL/supply-chain findings, review residual risks and publish only through a new, explicit owner decision. No publication, stable-workflow alteration or HA production changes are authorized here.
