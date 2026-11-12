# 🤖 Pilotage MOE / MOE release tracking

> **État au 12 novembre 2026 / Snapshot on 12 November 2026.**
> Dépôt / Repository: [christophejaubert/ha-trybatec](https://github.com/christophejaubert/ha-trybatec).
> **Document de préparation, non autorisation de fusion, de publication ou de modification Home Assistant. / Preparation only; no merge, release or Home Assistant change is authorized.**

## FR — Décisions et référence

- **Décision D1 validée par l'utilisateur :** préparer une préversion sans migration historique des comptes existants ; préserver leurs identifiants et le verrou de migration. La migration réelle de la [PR #82](https://github.com/christophejaubert/ha-trybatec/pull/82) demeure exclue, en brouillon, et l'[issue #81](https://github.com/christophejaubert/ha-trybatec/issues/81) ouverte.
- **Version candidate :** `0.3.4b1`, proposée et **non approuvée**. Dernière release publiée vérifiée : [`0.3.3b1`](https://github.com/christophejaubert/ha-trybatec/releases/tag/0.3.3b1).
- **Référence `main` au constat :** [`a21906bada0b01a9a069afc2a1b84235b2590cc7`](https://github.com/christophejaubert/ha-trybatec/commit/a21906bada0b01a9a069afc2a1b84235b2590cc7) ; la [PR #117](https://github.com/christophejaubert/ha-trybatec/pull/117) (correctifs historiques L2) y est fusionnée. Toute fusion ultérieure exige une nouvelle vérification de `main`.
- **Gouvernance :** cette matrice est une preuve de pilotage, pas une décision utilisateur. Aucune PR de ce tableau n'est autorisée à fusionner du seul fait de sa CI ; ni clôture automatique d'issue mère.
- **Autorité :** [issue MOE #45](https://github.com/christophejaubert/ha-trybatec/issues/45) et décisions utilisateur explicites ; suivre les références GitHub plutôt que les rapports recopiés. Préserver les critères historiques `COMPAT-01..06` et `UI-01..12` jusqu'à validation réelle documentée.

### Matrice PR / preuves — FR

| PR / Lot | SHA de tête observé | Qualification GitHub observée | Intégration / Étape suivante |
|---|---|---|---|
| [#117](https://github.com/christophejaubert/ha-trybatec/pull/117) — #36/L2 calcul | `5144d79be6e3880090bcd298f4632426554d352c` (PR) | Fusionnée ; CI sur `main` à vérifier après chaque nouveau merge | **Dans `main`** en squash `a21906bada0b01a9a069afc2a1b84235b2590cc7`. #36 et recette métier restent ouvertes |
| [#118](https://github.com/christophejaubert/ha-trybatec/pull/118) — #42 tarifs | `6898e8af352250f68905d3ba2aca7fb310b2397c` | 22 checks success, 1 skipped ; brouillon | Revue, compatibilité native JSON, coût YTD/dérogations, recette HA ; fusion distincte |
| [#119](https://github.com/christophejaubert/ha-trybatec/pull/119) — #35 installation | `2efcb3a64388ee2729938bb27ba810501e1c295c` | 21 success, 1 skipped ; brouillon ; 2 xfail métier déclarés | Revue tests/docs ; anomalies de notification et refus de logement à traiter séparément |
| [#120](https://github.com/christophejaubert/ha-trybatec/pull/120) — #81 identité neuve, D1 | `2fd05544070d8055495883829bab7c18a09967aa` | 20 success, 1 skipped ; brouillon | Revue compatibilité des comptes historiques et risque de retour arrière des nouveaux comptes ; pas de migration |
| [#121](https://github.com/christophejaubert/ha-trybatec/pull/121) — #88/L3 preuves Énergie | `75cd46826402211d0e4c4b6ad6dd329481c23f8e` | 22 success, 1 skipped ; brouillon | Revue du collecteur dormant en lecture seule ; ne pas activer l'ajout groupé |
| [#122](https://github.com/christophejaubert/ha-trybatec/pull/122) — #70/#83/#84 | `f6444a383de84cc1f54e6cafc8147579af0ab318` | 20 success, 1 skipped ; brouillon | Revue tests/docs ; rejouer/établir la preuve navigateur sur SHA exact ; recette WCAG/HA à faire |
| [#82](https://github.com/christophejaubert/ha-trybatec/pull/82) — migration historique | `5fc1d126c7a31a2da1d9769948d05a1fbb3070cb` | 20 success, 1 skipped ; brouillon | **Hors candidate D1** ; inventaire externe, restauration éprouvée et recette réelle manquants |

Les chiffres des checks ci-dessus sont des **photographies par SHA** et non des déclarations de réussite de toutes les CI à venir. Les étapes `skipped` correspondent notamment à une préparation manuelle de release, non exécutée.

### Matrice des issues / backlog — FR

| Priorité | Issue | Développé / testé / intégré | Reste à prouver ou décider pour clôture |
|---|---|---|---|
| P0 | [#45](https://github.com/christophejaubert/ha-trybatec/issues/45) Release intégrée | Version historique `0.3.3b1` publiée ; candidate `0.3.4b1` proposée ; matrice préparée | Périmètre approuvé, SHA final, CI obligatoire, recette, notes FR/EN, risques, publication distinctement autorisée |
| P0 | [#42](https://github.com/christophejaubert/ha-trybatec/issues/42) Tarifs | Éditeur et services existants ; #118 testée mais non fusionnée | Champ JSON de l'interface d'options native, estimations YTD, recette fonctionnelle |
| P0 | [#35](https://github.com/christophejaubert/ha-trybatec/issues/35) Installation | #119 : tests/docs, non fusionnée ; deux échecs métier attendus | Notification après redémarrage, refus d'accès après découverte, recette HA |
| P0 | [#81](https://github.com/christophejaubert/ha-trybatec/issues/81) Identités | #120 non migrante testée ; #82 historique distincte | Décision d'intégration de #120 ; migration historique #82 et retour arrière non validés |
| P0 | [#70](https://github.com/christophejaubert/ha-trybatec/issues/70) Marque/a11y | #85/#90/#91 déjà intégrées ; #122 tests/docs | Palette PNG, contraste, zoom 200 %, reflow 320 px, clavier, lecteurs d'écran, recette réelle |
| P1 | [#83](https://github.com/christophejaubert/ha-trybatec/issues/83) Guidage | États et guidage codés et testés synthétiquement | Parcours métier complets et preuve HA réelle |
| P1 | [#84](https://github.com/christophejaubert/ha-trybatec/issues/84) Fiches | Cinq informations et navigation testées synthétiquement | Valeurs/provenance et contexte vérifiés réellement, accessibilité |
| P1 | [#36](https://github.com/christophejaubert/ha-trybatec/issues/36) Historique | #117 fusionnée : DST, zéros, unités, `Decimal` | Provenance quotidienne, couverture, remplacements/chevauchements, persistance Recorder, recette |
| P1 | [#37](https://github.com/christophejaubert/ha-trybatec/issues/37) Déposés | Inventaires/diagnostics partiels | Filiations, périodes, références externes, continuité, absence de nettoyage automatique |
| P1 | [#88](https://github.com/christophejaubert/ha-trybatec/issues/88) Énergie | #91/#92 fusionnées ; #121 L3 testée, dormante | L6 lecture seule ; L7 activation transactionnelle séparée, non autorisée |
| P2 | [#39](https://github.com/christophejaubert/ha-trybatec/issues/39) Marketplace | Suivi distinct | Vérifier tous les critères HACS/Marketplace après stabilisation |
| P3 | [#34](https://github.com/christophejaubert/ha-trybatec/issues/34) DJU chauffage | Différé | Étude et décision future ; hors release candidate |

### Critères historiques de #45

La description originale de #45 reste la source des **6 critères `COMPAT-01..06` et 12 critères `UI-01..12`**. Aucun n'est automatiquement validé par une PR fusionnée ou une CI réussie. Le suivi doit conserver les cases historiques ouvertes, documenter pour chacun le SHA, le test, la recette, le résultat et la limite ; **ne pas réécrire les objectifs originaux comme s'ils étaient déjà acceptés**.

### Chemin critique et ordonnancement — FR

1. **P0 — CI/CD :** analyser le [`gitleaks` échoué du run planifié #43254529863](https://github.com/christophejaubert/ha-trybatec/actions/runs/43254529863) au SHA `a21906bada0b01a9a069afc2a1b84235b2590cc7`, malgré la [CI sur push réussie #43251453215](https://github.com/christophejaubert/ha-trybatec/actions/runs/43251453215) sur ce même SHA. Ne pas présumer d'une fuite de secret ; identifier la cause et rétablir le contrôle obligatoire.
2. **P0 — Intégrations parallèles :** revue finale de #119 (tests/docs), #121 (module dormant) et #122 (tests/docs), puis décisions de fusion **séparées**. Examiner simultanément #118 (tarifs actifs) et #120 (comportement des nouvelles installations, risque de downgrade).
3. **P1 — Correctifs indépendants :** #35 notifications/accès, #42 JSON natif et estimation YTD, #70 palette/accessibilité, #36/#37 provenance/filiation, #88 L6 purement en lecture seule. Vérifier les propriétaires des fichiers avant tout changement.
4. **P1 — Candidate :** consolider uniquement les PR réellement fusionnées et qualifiées, sans exécuteur #82, sans migration historique, sans nettoyage de compteur et sans activation Énergie L7. Les fonctions incomplètes restent ouvertes/inactives selon décision.
5. **P1 — Recette puis publication :** contrôles CI sur SHA final, FR/EN et bureau/mobile, vérifications critiques réelles et non-régression du compte historique, plan de retour arrière et limites documentés. Numéro, SHA, notes et risques exigent accord utilisateur avant release.

**Anomalie de convention :** le workflow de publication [`.github/workflows/publish-experimental.yml`](https://github.com/christophejaubert/ha-trybatec/blob/main/.github/workflows/publish-experimental.yml) génère encore le titre `Trybatec VERSION` sans le préfixe `🤖 `. Correction CI/CD dédiée avant la prochaine release ; **le tag conserve son format sans emoji**.

**Autorisation :** ce document n'autorise aucune fusion, release, installation, migration, restauration ni modification Home Assistant. Les comptes historiques et leurs identifiants doivent rester préservés ; ne jamais publier de preuves réidentifiables.

---

## EN — Decisions, status and release path

**D1 approved by the user:** prepare an integrated prerelease that does **not** migrate existing historical accounts. Keep [PR #82](https://github.com/christophejaubert/ha-trybatec/pull/82) in draft and issue #81 open; stable IDs for **new** accounts are separately proposed through [PR #120](https://github.com/christophejaubert/ha-trybatec/pull/120). Preserve historic entity/device IDs and migration safety locks.

- **Proposed candidate:** `0.3.4b1` (not yet approved); latest verified published tag: `0.3.3b1`.
- **Verified main baseline:** `a21906bada0b01a9a069afc2a1b84235b2590cc7`, including merged L2 [PR #117](https://github.com/christophejaubert/ha-trybatec/pull/117).
- **All six open PRs are drafts:** #82, #118, #119, #120, #121, #122. Their reported automated checks completed successfully on their **own exact heads**, with intentional manual steps skipped. No live HA business acceptance is implied.

### PR matrix — EN

| PR | Candidate purpose | State / blocking proof |
|---|---|---|
| [#117](https://github.com/christophejaubert/ha-trybatec/pull/117) | Safe L2 calculations | Merged; does not close #36 |
| [#118](https://github.com/christophejaubert/ha-trybatec/pull/118) | Annual tariff form | Draft; native JSON options, YTD estimate and live acceptance outstanding |
| [#119](https://github.com/christophejaubert/ha-trybatec/pull/119) | Setup/reauth test documentation | Draft; two known expected-failure cases need correction |
| [#120](https://github.com/christophejaubert/ha-trybatec/pull/120) | Greenfield stable IDs, no legacy migration | Draft; downgrade risk for newly created accounts |
| [#121](https://github.com/christophejaubert/ha-trybatec/pull/121) | Read-only dormant Energy evidence collector | Draft; full history/lineage verification and subsequent L6/L7 separate |
| [#122](https://github.com/christophejaubert/ha-trybatec/pull/122) | UI/UX evidence and brand audit | Draft; full browser-on-head and actual WCAG/HA acceptance outstanding |
| [#82](https://github.com/christophejaubert/ha-trybatec/pull/82) | One-time historical migration | **Excluded** from this candidate; external dependencies, proven recovery and live acceptance missing |

### Open issue backlog — EN

| Priority | Issue | Remaining gate |
|---|---|---|
| P0 | [#45](https://github.com/christophejaubert/ha-trybatec/issues/45) | Approved exact scope/SHA/version/notes, green mandatory CI, live acceptance, publication authorization |
| P0 | [#42](https://github.com/christophejaubert/ha-trybatec/issues/42) | Native JSON, YTD deviation behavior, live tariff acceptance |
| P0 | [#35](https://github.com/christophejaubert/ha-trybatec/issues/35) | Persistent notification after coordinator restart, discovered-property access denial, live acceptance |
| P0 | [#81](https://github.com/christophejaubert/ha-trybatec/issues/81) | Split greenfield delivery vs still-blocked legacy migration and recovery |
| P0 | [#70](https://github.com/christophejaubert/ha-trybatec/issues/70) | PNG palette, contrasts, keyboard, zoom, reflow, screen readers |
| P1 | [#83](https://github.com/christophejaubert/ha-trybatec/issues/83) | Actual guided-path acceptance |
| P1 | [#84](https://github.com/christophejaubert/ha-trybatec/issues/84) | Actual five meter fields/provenance and contextual navigation |
| P1 | [#36](https://github.com/christophejaubert/ha-trybatec/issues/36) | Daily lineage, coverage, overlaps, Recorder persistence |
| P1 | [#37](https://github.com/christophejaubert/ha-trybatec/issues/37) | Retired meter lineage, continuity, consumers and safe cleanup gates |
| P1 | [#88](https://github.com/christophejaubert/ha-trybatec/issues/88) | L6 read-only connection, separate L7 reversible enrollment |
| P2 | [#39](https://github.com/christophejaubert/ha-trybatec/issues/39) | Marketplace readiness after stabilization |
| P3 | [#34](https://github.com/christophejaubert/ha-trybatec/issues/34) | Degree-day smoothing research, deferred |

### Next steps / Required safeguards — EN

1. Investigate the scheduled `gitleaks` failure without assuming a credential leak. Fix the release-title `🤖 ` convention separately.
2. Review draft PRs #119/#121/#122 for independent integration; review functional PRs #118/#120 with stricter backward-compatibility and downgrade checks. **Each merge requires explicit user authorization**.
3. Reconcile `main`, exact SHA CI and remaining branches after every approved merge; rerun checks as appropriate.
4. Prepare only a nonmigrating candidate using what is actually merged and qualified. Exclude #82's historical executor, destructive retired-meter cleanup, Recorder backfills, and Energy L7 bulk activation.
5. Require a separate user decision for exact version, SHA, FR/EN notes, acceptance scope, risks and publication; installation on Home Assistant and migration/restore are independent decisions.

**Evidence hierarchy:** developed ≠ CI-tested ≠ real Home Assistant accepted ≠ merged ≠ released ≠ installed. An issue is not closed merely because one PR merged. Only anonymized, non-reidentifying acceptance conclusions may be stored publicly; private installation data must stay private.
