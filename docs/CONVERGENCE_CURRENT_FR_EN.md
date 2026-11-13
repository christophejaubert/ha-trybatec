# 🤖 Convergence technique — 13 novembre 2026 / Technical convergence — 13 November 2026

**MOE / Lead:** #45 · **Main base:** `8d621da9703b40662800b4a7c286707e8a7f895f` · **Release baseline:** `0.3.4b1`.
**State / État:** DRAFT ONLY / BROUILLON — not qualified for merge, release or deployment.
**No version assigned / Aucun numéro de version attribué.**

## FR — Réconciliation et propriété des fichiers

Vérification des arbres Git (pas uniquement des diffs de PR) : les PR #149/#150/#151/#153 ont une base divergente antérieure à la fusion de #147. L'arbre exact de #153 (`daab196ce4f67b1ed73f1623dc385c5d405a101f`) ne diffère du `main` publié que par six chemins : `.github/workflows/ci.yml`, `.gitleaksignore`, `RELEASE_NOTES_BETA.md`, `docs/CI_GITLEAKS_2026-11-12.md`, `docs/CONVERGENCE_36_37_88_034B1_FR_EN.md` et `tests/test_ci_gitleaks_history.py`. **Ne pas recopier les anciens commits ni écraser la CI de main.**

Cette branche de travail reprend exclusivement les **six chemins** de #156 à son SHA `48a5c5839095b5b0957af88bf135e7e05853ae52` et les **huit chemins** C11 de PR #162 au SHA `38a539aaea7e1312391d8e5769695836e58db211`, plus les tests de raccordement et le présent suivi. Ces sources restent indépendantes et peuvent évoluer.

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
- C11 est désormais porté par PR #162 avec tests et commande enregistrée; l'exécution CI du SHA `38a539aaea7e1312391d8e5769695836e58db211` a été constatée **annulée** (pas de preuve verte transférable). Tests de raccordement ajoutés ici; couverture exhaustive réelle non démontrée.
- Ne pas intégrer les six différences résiduelles de #153 sans revue du propriétaire CI et du suivi documentaire. Les PR #154/#146/#143 et toute PR « DO NOT MERGE » restent des preuves non candidates.
- Aucune validation en Home Assistant réel, aucune écriture Recorder/Énergie, aucun merge/release/tag, aucune installation ou restauration. La procédure future de recette réelle relève d'autorisations distinctes.

## EN — Reconciliation, contracts and acceptance gates

Tree-level comparison confirms that #149/#150/#151/#153 mostly contain code already shipped by merged #147. The only #153 differences left against released `main` are six CI/release/documentation paths listed above; they **must not** be blindly replayed.

This branch composes six UI files from #156, eight C11 backend/test/docs files from #162, plus focused #36/#37/#88 and CI-only contributions; source branches remain untouched. The matrix above defines file ownership and the required History → Recorder → Physical lineage → Energy, and UI → C11 → Tariffs interface and regression gates.

**Known blockers:** #156 head CI is now green, but the latest C11 source run was cancelled. Independent full-stack CI on this integration SHA remains required. True independent Recorder quiescence, complete physical lineage and admissible/transactional Energy enrollment are not established by this composition. Do not bypass any fail-closed guard; no actual HA acceptance exists. Check all mandatory CI and privacy controls on the exact integrated SHA before any future separately approved merge and release.

## Complément de composition / Composition update — 13/11/2026

**FR :** Contributions spécialisées complémentaires reprises au **chemin exact uniquement** : PR #157 (CI Gitleaks, SHA `c0cf7a71e51cbd4255b474758b61d3296f80c74b`, 2 chemins), #158 (#88 admin non enregistré, SHA `0750af43611326eb6bb8f8d01744aa622e576dd2`, 3 chemins propres hors héritage #153), #159 (#36, SHA `7ce922320da4bb46d7619fe8285f6c2c9d001ace`, 6 chemins), #160 (#37/#81, SHA `f99a6de148dffa56a560e7c0e6b5f20f039aa612`, 5 chemins), #162 (C11, 8 chemins) et #156 (6 chemins). Les 6 écarts hérités de #153 ne sont **pas** repris. #161 reste propriété du pilotage documentaire; #163 (Marketplace) demeure un lot distinct. Chacune de ces PR reste non fusionnée.

Les contrats administratifs #88 restent dormants, les contrôles #36/#37 restent fail-closed et les tests synthétiques ne prouvent aucune admisibilité réelle. Les PR source #157, #159, #156 avaient une CI réussie au point de lecture ; #158 et #160 étaient en file, #162 annulée ; **seul l'état CI du SHA final de cette PR** établira la qualification automatique de la composition. Aucun état source ne vaut recette HA.

**EN:** Leaf-only import from #157 (CI 2 paths), #158 (#88 dormant admin 3 paths), #159 (#36 6 paths), #160 (#37/#81 5 paths), #162 (C11 8 paths), and #156 (UI 6 paths). Six stale #153 CI/docs differences are excluded. #161 owns MOE tracking; #163 marketplace work is separate. No admission, writer reopening, production acceptance or deployment. All source PRs remain untouched and unmerged.
