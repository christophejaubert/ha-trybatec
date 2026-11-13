# 🤖 Convergence technique — 13 novembre 2026 / Technical convergence — 13 November 2026

**MOE / Lead:** #45 · **Main base:** `8d621da9703b40662800b4a7c286707e8a7f895f` · **Release baseline:** `0.3.4b1`.
**State / État:** DRAFT ONLY / BROUILLON — not qualified for merge, release or deployment.
**No version assigned / Aucun numéro de version attribué.**

## FR — Réconciliation et propriété des fichiers

Vérification des arbres Git (pas uniquement des diffs de PR) : les PR #149/#150/#151/#153 ont une base divergente antérieure à la fusion de #147. L'arbre exact de #153 (`daab196ce4f67b1ed73f1623dc385c5d405a101f`) ne diffère du `main` publié que par six chemins : `.github/workflows/ci.yml`, `.gitleaksignore`, `RELEASE_NOTES_BETA.md`, `docs/CI_GITLEAKS_2026-11-12.md`, `docs/CONVERGENCE_36_37_88_034B1_FR_EN.md` et `tests/test_ci_gitleaks_history.py`. **Ne pas recopier les anciens commits ni écraser la CI de main.**

Cette branche de convergence compose des changements au chemin exact issus de #156 (6 fichiers, `48a5c5839095b5b0957af88bf135e7e05853ae52`), #162 C11 (10 fichiers, `bb25462e213fec1b782fd5b0e7b3340dfd8cf5d6`), #159 Recorder (6 fichiers), #160 filiation (5 fichiers), #158 Énergie (3 fichiers, `4d1f2eef34637957bbea97369482ebe6c2ceaa8e`), #157 CI (2 fichiers) et #165 recette navigateur indépendante (3 fichiers, `7e426134a4c94707d0f068264eb234690772c89d`). Les 2 chemins de convergence propres sont un test de raccordement et cette matrice. Aucun parent de PR de preuve n'a été rejoué.

### Propriétaires et interfaces

| Chantier | Propriété source / owner | Contrat entrant et sortant |
| --- | --- | --- |
| #155 C1–C10 | `panel/trybatec-panel.js`, `strings.json`, `translations/{fr,en}.json`, `tests/test_panel_issue_155*.py` | Scan unique de compte; visibilité des détails; provenance et états 0/positif/inconnu; libellés FR/EN |
| #155 C11 | `panel_history.py`, `panel_history_coverage.py`, `panel_tariff_years.py` | Source mémoire privée bornée par compte, inventaire, période et TTL; réutilisation de données validées, réponse sans données brutes, refus des recherches incomplètes |
| #36 | Historique/Recorder, verrous et reprise sélective | Sortie : une série validée avec provenance/version, quiescence indépendante et persistance prouvée; aucun contournement du refus |
| #37/#81 | Identité physique, anciens compteurs, consolidation et continuité | Entrée : observations exactes par compteur; sortie : consolidation sans concaténation d'index de générations distinctes |
| #88 | Prévisualisation/admission L6, transaction administrative L7, Energy | Entrée : preuves #36/#37 indépendantes, exclusivité Recorder, unités et sources; sortie : admission contrôlée ou refus; ne pas activer la voie de mutation avant qualification |
| CI/CD | Workflows, Gitleaks, privacy preflight, CodeQL | Aucun affaiblissement des vérifications ou promotion de preuve « DO NOT MERGE » |
| Convergence MOE | Ce document et tests de raccordement nouveaux uniquement | Réconcilie les SHA, prévient les réimports et n'édite pas les branches spécialisées |

Fichiers sensibles aux collisions : `panel/trybatec-panel.js` (C1–C10), traductions (UI), `panel_history.py`, `panel_tariff_years.py` (C11), `panel_api.py`/`__init__.py` (enregistrement), composants Recorder et Energy (frontières #36/#37/#88). Tout changement transversal doit être justifié sur SHA exact.

### Matrice de non-régression

| Chaîne | Vérifications attendues | Situation au point de composition |
| --- | --- | --- |
| #36 Historique → Recorder | provenance, bornes, versions, clôture du writer, stockage et reprise sélective | acquis historiques dans main; preuves indépendantes complètes encore requises |
| #37 Recorder → filiation physique | compte/lot/fluide/série, générations déposées, jours, aucune double attribution | interfaces présentes dans main; exhaustivité réelle non démontrée |
| #88 Filiation → Énergie | une statistique consolidée admissible, unités EF/ECS/CH, conflit, idempotence, rollback, conservation des tiers | refus conservés; L6/L7 réel non qualifié |
| #155 UI → C11 → Tarifs | scan global explicite, cache confiné et borné, pas de répétition fournisseur; dates et statut complets/incomplets | codes composés pour test; tests fonctionnels croisés et recette à confirmer |
| CI/Privacy | Ruff, Python 3.13/3.14, Gitleaks, CodeQL, intégrité workflow, tests navigateur et accessibilité, privacy preflight | CI du SHA de convergence **à vérifier** |

### Blocages et limites

- La CI #156 est réussie sur la nouvelle tête `48a5c5839095b5b0957af88bf135e7e05853ae52`. L'échec antérieur `4e6d863e989039a3a7a45a99a94678e139556def` (assertion C5–C10) reste une preuve historique uniquement.
- C11 #162 est qualifiée en CI sur le SHA `bb25462e213fec1b782fd5b0e7b3340dfd8cf5d6` (workflow `43420192794` réussi) avec deux tests d'intégration HA supplémentaires : enregistrement des 18 commandes et parcours historique. Une CI source réussie reste distincte de la recette HA réelle.
- Ne pas intégrer les six différences résiduelles de #153 sans revue du propriétaire CI et du suivi documentaire. Les PR #154/#146/#143 et toute PR « DO NOT MERGE » restent des preuves non candidates.
- Aucune validation en Home Assistant réel, aucune écriture Recorder/Énergie, aucun merge/release/tag, aucune installation ou restauration. La procédure future de recette réelle relève d'autorisations distinctes.

## EN — Reconciliation, contracts and acceptance gates

Tree-level comparison confirms that #149/#150/#151/#153 mostly contain code already shipped by merged #147. The only #153 differences left against released `main` are six CI/release/documentation paths listed above; they **must not** be blindly replayed.

This branch composes six UI files from #156, ten C11 backend/test/docs files from #162, focused #36/#37/#88 and CI-only contributions, and three browser-qualification paths from #165; source branches remain untouched. The matrix above defines file ownership and the required History → Recorder → Physical lineage → Energy, and UI → C11 → Tariffs interface and regression gates.

**Known blockers:** #156 and the latest C11 #162 source CI now pass, but such statuses do not qualify the integrated exact SHA. Independent full-stack CI on this integration SHA remains required. True independent Recorder quiescence, complete physical lineage and admissible/transactional Energy enrollment are not established by this composition. Do not bypass any fail-closed guard; no actual HA acceptance exists. Check all mandatory CI and privacy controls on the exact integrated SHA before any future separately approved merge and release.

## Complément de composition / Composition update — 13/11/2026

**FR :** Contributions spécialisées complémentaires reprises au **chemin exact uniquement** : PR #157 (CI Gitleaks, SHA `c0cf7a71e51cbd4255b474758b61d3296f80c74b`, 2 chemins), #158 (#88 admin non enregistré, SHA `4d1f2eef34637957bbea97369482ebe6c2ceaa8e`, 3 chemins propres hors héritage #153), #159 (#36, SHA `7ce922320da4bb46d7619fe8285f6c2c9d001ace`, 6 chemins), #160 (#37/#81, SHA `f99a6de148dffa56a560e7c0e6b5f20f039aa612`, 5 chemins), #162 (C11, 10 chemins), #156 (6 chemins) et #165 (recette navigateur indépendante, 3 chemins). Les 6 écarts hérités de #153 ne sont **pas** repris. #161 reste propriété du pilotage documentaire; #163 (Marketplace) demeure un lot distinct. Chacune de ces PR reste non fusionnée.

Les contrats administratifs #88 restent dormants, les contrôles #36/#37 restent fail-closed et les tests synthétiques ne prouvent aucune admisibilité réelle. Les PR source #157, #159, #156 avaient une CI réussie au point de lecture ; #160 et #162 ont ensuite une CI source réussie; #158 a un Gitleaks historique en échec sur sa branche empilée ; **seul l'état CI du SHA final de cette PR** établira la qualification automatique de la composition. Aucun état source ne vaut recette HA.

**EN:** Leaf-only import from #157 (CI 2 paths), #158 (#88 dormant admin 3 paths), #159 (#36 6 paths), #160 (#37/#81 5 paths), #162 (C11 10 paths), #156 (UI 6 paths), and #165 (browser tests 3 paths). Six stale #153 CI/docs differences are excluded. #161 owns MOE tracking; #163 marketplace work is separate. No admission, writer reopening, production acceptance or deployment. All source PRs remain untouched and unmerged.

## Dernière qualification de sources / Latest source evidence — 13/11/2026

**FR :** PR #162 SHA `bb25462e213fec1b782fd5b0e7b3340dfd8cf5d6` : CI source réussie, corrige le contrat d'enregistrement et ajoute des tests C11 d'intégration; #166 SHA `d8d7e869fdea826bc64f29fb79a312f6699a5014` : tests navigateur indépendants de #165 exécutés sur le panneau #156, CI et navigateur réussis; #165 sur main seul conserve un échec navigateur attendu par l'absence des fonctions #156, non qualifiant pour la convergence. #157, #159, #160 et #156 : CI sources réussies sur les SHAs de composition. #158 `4d1f2eef34637957bbea97369482ebe6c2ceaa8e` : Gitleaks historique échoue sur la branche **empilée**, mais les trois fichiers dédiés #88 sont les seuls importés; les contrôles Gitleaks doivent être vérifiés sur la branche de convergence propre. Les verrous métier ne sont pas levés.

**EN:** Source #162 passed exact-head CI after registering the additional websocket command and testing panel historical behavior. Independent browser tests #165 pass on functional UI #156 via stacked #166; the same tests on featureless main are expected to fail and must not be masked. #158 stacked-branch historical Gitleaks failure does not authorize security weakening; requalify the clean, leaf-only integration head. All business write guards remain inactive.

## Qualification indépendante de la convergence / Independent integration qualification — 13/11/2026

**FR — Photographie figée, avant cette actualisation documentaire.**
- PR [#164](https://github.com/christophejaubert/ha-trybatec/pull/164), arbre fonctionnel au SHA `3eef5770ba57c36aa596121321819cf9c3186100`, base `main` `8d621da9703b40662800b4a7c286707e8a7f895f`. Les **35 chemins sources** correspondent bit pour bit aux sept têtes : #156 (6), #157 (2), #158 (3), #159 (6), #160 (5), #162 (10), #165 (3), plus deux chemins propres de convergence. Aucune reprise intégrale de #149/#150/#151/#153, aucun écrasement de source, aucune modification de `main`.
- Checks GitHub [sur ce SHA](https://github.com/christophejaubert/ha-trybatec/commit/3eef5770ba57c36aa596121321819cf9c3186100/checks) : **26 réussis / 1 ignoré (préparation manuelle de release) / 0 échec / 0 attente** ; **10/10 obligatoires réussis** selon la ruleset `Protect main - CI/CD` consultée. CI [#43421476603](https://github.com/christophejaubert/ha-trybatec/actions/runs/43421476603) : Python 3.13 **946 tests réussis, 53 sous-tests, 79,22 % de couverture**, environnement Home Assistant isolé **221 tests réussis** ; Python 3.14, Ruff, HACS, Hassfest, import HA, Recorder E2E et persistance réussis.
- [Navigateur](https://github.com/christophejaubert/ha-trybatec/actions/runs/43421476645) : **80/80 assertions synthétiques C1–C11 réussies**, huit combinaisons FR/EN × desktop/mobile × clair/sombre, sept vues conservées. [Accessibilité synthétique](https://github.com/christophejaubert/ha-trybatec/actions/runs/43421476499) et [supply-chain](https://github.com/christophejaubert/ha-trybatec/actions/runs/43421476513) réussis. Gitleaks, CodeQL, `public-privacy-preflight` et `trusted-workflow-integrity` réussis sur le même SHA ; **le privacy preflight n'est cependant pas inscrit dans les dix checks obligatoires de la ruleset**.
- **Développé + testé synthétiquement ≠ recetté ni fonctionnellement admissible.** `history_recorder_b15.py` refuse la reprise sélective sans attestation indépendante anti-writer tardif ; `lineage_energy_handoff_37.py` conserve `physical_inventory_complete=False` et `energy_activation_authorized=False` ; `energy_bulk_contract_l6.py` conserve `admissible=False` et `energy_bulk_admin_service_88.py` est volontairement **non enregistré**. Besoin d'attestations indépendantes, sérialisation des générations, exclusivité des statistiques, sémantique CET/CH kWh, protection des sources tierces, sauvegarde/restauration transactionnelles. Les tests synthétiques n'en démontrent pas l'aboutissement en production.
- C11 : source en mémoire confinée, fenêtre validée et cache réutilisable sans données brutes dans la réponse ; **la reprise après interruption reste `restart_from_zero`** et le scan borné ne doit pas être confondu avec une couverture historique exhaustive.
- **Étape préparée** : revue de la candidate et approfondissement des garanties #36/#37/#88 puis CI exacte sur les commits subséquents ; seulement ensuite décisions explicites et séparées de fusion, publication, installation et opérations de recette autorisées. Aucune baisse de garde, aucun tag, aucune écriture Recorder/Énergie ni opération HA dans cette convergence.

**EN — Immutable evidence snapshot before this documentation update.**
At `3eef5770ba57c36aa596121321819cf9c3186100`, all 35 source-path blobs exactly matched seven source PR heads. GitHub recorded 26 passing checks, one optional manual-release job skipped, 10/10 required passing, zero failures/pending; 946 Python 3.13 tests + 53 subtests (79.22% coverage), 221 isolated HA tests, and 80/80 cross-browser assertions in eight FR/EN/device/theme configurations. Gitleaks, CodeQL, public privacy preflight, trusted workflow integrity and security workflows all passed. Privacy preflight was successful but is **not** among the current ten required branch checks.

These are synthetic exact-SHA tests, not live HA acceptance. Recorder late-writer exclusion is still unproven, lineage/physical inventory remains incomplete, Energy L6 admission is false, and L7 admin entrypoints remain unregistered. C11 retains explicit restart-from-zero for interrupted scans. No merge, release/tag, HA change, backup/restore or Recorder/Energy write is authorized or executed; no next version number has been selected.


## Actualisation C11 — 13 novembre 2026 / C11 update — 13 November 2026

**FR — Source de vérité et périmètre.** PR #164 demeure une candidate brouillon sur la base publiée main 8d621da9703b40662800b4a7c286707e8a7f895f (0.3.4b1). SHA du code après raccordement, avant ce commit documentaire : 6e321244c0bc904cdb6290ad6e4b0a46ae36a2d8. Aucun nouveau numéro de version approuvé. Les branches spécialisées #156, #162, #159, #160, #158, #157, #165/#166 n'ont pas avancé lors de cette réconciliation ; leurs modifications utiles étaient déjà composées dans #164.

**FR — Anomalie C11 démontrée.** Au SHA initial 59ca822cbe8590151d32fc1db9061d4a79d19870, le backend exposait la commande administrateur en lecture seule trybatec/panel_history_discovery_status, mais le panneau ne la consommait pas. Les 80 assertions navigateur antérieures étaient synthétiques et ne couvraient pas cette commande.

**FR — Intégration ciblée.** La branche #164 consomme maintenant le statut C11 au chargement, à la navigation et sur actualisation explicite, sans démarrer de job fournisseur. Elle présente les états non démarré, en cours, complet, partiel, interrompu, erreur, indisponible ; les dates bornées, le nombre de compteurs rapprochés, la progression, la réutilisation/expiration/invalidation du cache, les catégories d'échec expurgées et l'impossibilité de reprendre partiellement sans points de reprise atomiques. L'interface ne confond ni une fenêtre bornée avec l'exhaustivité du compte, ni une fenêtre vérifiée avec une continuité quotidienne. Seule une couverture account_full validée sans invalidation rend admissible le cache de bornes physiques. Les données dérivées du statut ne sont pas injectées dans l'instantané de compte, afin d'éviter des dates périmées après invalidation.

**FR — Changements et propriété.** Les 35 blobs initiaux de sept PR spécialisées étaient identiques dans #164. Trois chemins spécialisés composés ont été adaptés exclusivement dans #164 : custom_components/trybatec/panel/trybatec-panel.js, scripts/browser-ci/acceptance.cjs et scripts/browser-ci/qualification_155_cross.cjs. Un banc d'accessibilité existant, scripts/browser-ci/a11y_independent_70_83_84.cjs, accepte désormais uniquement la commande supplémentaire de lecture seule. Les 32 autres chemins spécialisés restent identiques aux sources. Les fichiers et branches propriétaires des PR #161 et #163 sont inchangés ; pas de reprise des commits empilés historiques de #153.

**FR — Tests et limites.** Les nouveaux scénarios Playwright synthétiques contrôlent les appels WebSocket effectivement émis, huit états de découverte, le refus de réponse non sûre, l'invalidation, le cache et l'absence de nouveau scan déclenché par une simple consultation. La CI obligatoire doit être évaluée au SHA final issu de ce commit documentaire, et non d'après les anciens résultats verts. Ces tests ne constituent ni recette HA réelle ni attestation d'exhaustivité physique.

**FR — Dépendances bloquantes.** #36 : preuve indépendante excluant tout writer Recorder tardif encore absente ; refus actif. #37/#81 : inventaire et attribution des générations physiques non complètement attestés ; physical_inventory_complete=false et energy_activation_authorized=false. #88 : admission L6 non prouvée, activation_authorized=false, façade native administrative L7 non enregistrée, sauvegarde/restauration et exclusivité Energy non qualifiées. C11 : après interruption, restart_from_zero ; aucune reprise atomique par fenêtre.

**FR — Recette et décisions.** Préparer une recette future comprenant FR/EN, bureau/mobile, clair/sombre, lecture d'état C11 sans nouvelle recherche, cache expiré, erreurs et annulations, historique/tarifs, et accessibilité HA. La recette réelle attend une fusion, un numéro de version, une release et une installation chacun explicitement autorisés et distincts ; toute opération Recorder, Energy, migration, sauvegarde ou restauration requiert sa propre autorisation. Aucune de ces opérations n'a été réalisée.

**EN — Current C11 integration.** The original draft exposed an administrator-only read-only discovery-status WebSocket endpoint but the frontend did not call it. PR #164 now consumes and displays account-scoped discovery status, complete versus bounded intervals, progress, safe failure categories, cache reuse/expiry/invalidation, and restart-from-zero semantics. Status polling and the explicit refresh button never start supplier jobs or write HA/Recorder/Energy data. Eight synthetic browser states and actual outbound WebSocket commands are tested; partial coverage cannot be promoted to exhaustive and derived dates are not persisted into the panel snapshot.

**EN — Ownership and gates.** Three formerly identical source-owned files were minimally adapted in the convergence branch only, plus an existing accessibility test harness; 32 other selected source blobs are unchanged. #161 MOE documentation and #163 Marketplace stay independent. Recorder no-late-writer proof (#36), independently complete physical lineage (#37), Energy L6 eligibility and dormant L7 transaction registration/backup/recovery (#88) remain blocked. The full exact-SHA CI, including ten required main checks and optional privacy/browser/security/a11y evidence, must be verified before any readiness claim. Real HA acceptance is not yet performed and requires separately approved merge, version, release and installation; no version was assigned.
