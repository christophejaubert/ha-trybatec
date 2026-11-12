# 🤖 0.3.4b1 — Réconciliation finale UI/UX #70/#83/#84 / UI/UX acceptance reconciliation

**Référence vérifiée le 12/11/2026 / Verified baseline:** `main` `a1bd6d8558c8fe1cc13cadeb1ff4aaa20528dc53`.
**Responsabilité commune / Shared owner:** [tariff PR #118](https://github.com/christophejaubert/ha-trybatec/pull/118) retains control of `trybatec-panel.js` and `scripts/browser-ci/acceptance.cjs`. No merge or publication authorized.

## FR — Matrice distinguant trois niveaux de preuve

| Fonction / critère | Développé (code en PR) | Testé (preuve SHA) | Recetté HA réel | Reste à faire |
|---|---|---|---|---|
| Palette EF/ECS/CET/marque #70 | [PR #131](https://github.com/christophejaubert/ha-trybatec/pull/131) : PLTE corrigée pour 2 PNG, IDAT/tRNS préservés | CI #131 [#43281643386](https://github.com/christophejaubert/ha-trybatec/actions/runs/43281643386), tests de pixels visibles | **Non** | Vérifier silhouette approuvée, thème HA, petit format, références/caches |
| États de contrôle #83 | Fusion #90 : conforme/anomalie/non vérifié/non applicable ; disponibilité et optionnalité distinctes | Tests Python/Node des PR #90/#91 ; CI synthétique | **Non** | Cas en service/déposé, inconnu/indisponible, blocage prouvé, message « terminé » uniquement si preuve |
| Énergie #83/#88 | Fusion #91 : modes `technical_unavailable`, `configuration_incomplete`, `verification_needed`, `coverage_unverified`, `not_implemented`; repli en lecture seule | Tests de guidance, sonde Chromium [#43283574524](https://github.com/christophejaubert/ha-trybatec/actions/runs/43283574524) | **Non** | Activation groupée non autorisée ; #88 dépend d'autres preuves |
| Fiche des 5 champs #84 | Fusion #90 : index, début, dernière observation source, dernier index exploitable, unité/statut/provenance | `tests/test_panel_ui_semantics_83_84.py` et navigateur synthétique | **Non** | Contrôler données réelles, dates, source API/manuelle et cas sans historique |
| Navigation contextualisée #84 | `physical_key` exact, retour et repli sûr pour compteur introuvable | Régressions Python/Node #90/#91 | **Non** | Tester sélection, disparition du compteur et retour dans HA |
| Tarifs facultatifs #83 | Fusion #90/#91 ; éditeur annuel en cours sur #118 | CI #118 propre à son SHA, pas recette globale | **Non** | Attendre finalisation de #118 ; absence de tarifs ne doit pas être une anomalie |
| Reflow mobile 320 CSS px #70 | [PR #138](https://github.com/christophejaubert/ha-trybatec/pull/138) empilée sur #118 : largeur min grille/champs + test 7 sections | Workflow navigateur synthétique **réussi** sur `ac1ce054fa23a97b55703cedd90d8bbe0c625f84` | **Non** | Rejouer après réconciliation #118 et valider sur vrai HA |
| Contrast WCAG #70 | Audit source [PR #133](https://github.com/christophejaubert/ha-trybatec/pull/133) | Quatre ratios de tokens de boutons évalués, sonde sur 56 configurations | **Non** | Mesurer surfaces effectivement compositées, focus/contrôles/graphes |
| Clavier / focus #70 | Focus CSS et navigation déclarés | Focus de navigation testé, 40 observations de focus hors viewport restent à examiner | **Non** | Tabulation complète, pièges, masquage, menu à défilement |
| Zoom 200 % / spacing / VoiceOver/TalkBack | Protocole publié en PR #133 | **Non vérifié** par le dispositif actuel | **Non** | Recette spécifique avec technologies d'assistance |
| Cibles tactiles #70 | Règles documentées | 56 observations de petites cibles dans sonde, concentration dans Énergie | **Non** | Mesurer les véritables cibles, exceptions WCAG et tailles mobiles |
| FR/EN × bureau/mobile × clair/sombre | Sondes et checklist 56 combinaisons | 56 **exécutions synthétiques**, aucun appel fournisseur | **0/56** | 56 scénarios HA réels restent non exécutés |

### Analyse des anomalies et dépendances

- **Écart initial P1 :** quatre débordements 320 CSS px de la vue Énergie FR à 373 px, reproductibles par la sonde #133. Le CSS et la couverture navigateur 7 sections sont corrigés **sur branche #138 uniquement**, sans modifier la PR #118 ou `main`.
- **Statuts :** `indisponible` (module non chargé) ≠ `inconnu` (identité/valeur non connue) ≠ `non vérifié` (preuve insuffisante) ≠ `bloqué` (opération empêchée) ≠ `configuration terminée` (contrôles réellement accomplis). La lecture de prérequis seule ne suffit jamais à prouver l'activation groupée #88.
- **Conservation du contexte :** référencer le compteur physique exact, sans réaffectation implicite vers un compteur voisin ; ne pas considérer le scan global achevé comme une preuve individuelle.
- **Confidentialité :** aucun relevé réel, identifiant d'installation, secret, numéro de série, capture non expurgée ni historique source brut dans GitHub.

### Actions restantes et responsables proposés

1. **#118, propriétaire tarifs :** conserver ses huit à dix modifications métier et réconcilier le petit patch empilé #138, sans régression de l'éditeur annuel.
2. **UI/UX :** utiliser les résultats des 56 exécutions synthétiques pour qualifier focus, cibles et zones d'overflow ; vérifier les 21 critères WCAG du fichier `MATRICE_WCAG_70_83_84.csv`.
3. **Recette métier :** exécuter `RECETTE_REELLE_56.csv` sur une installation autorisée avec preuves privées. Réaliser VoiceOver/TalkBack et texte 200 %.
4. **MOE :** ne déclarer **aucune** issue #70/#83/#84 recettée avant validation métier ; fusion, release et déploiement nécessitent chacun une autorisation spécifique.

## EN — Evidence levels and pending acceptance

The table above separates **implemented code**, **automated tests on a stated SHA**, and **real Home Assistant acceptance**. Draft #131 changes only two PNG palettes and tests actually visible indexed pixels. Draft #133 supplies static WCAG analysis, a synthetic 56-case Chromium probe, the 21-criterion checklist and 56 unexecuted live HA cases. Stacked draft #138 targets #118's branch with a minimal CSS fix for four French Energy 320px overflows plus an existing-browser extension from 3 to 7 views; synthetic Chromium passed on `ac1ce054fa23a97b55703cedd90d8bbe0c625f84`.

**State distinctions:** technically unavailable, unknown value/identity, not verified, blocked operation, and completed configuration must not be conflated. Meter navigation must retain the exact physical key and fail closed for missing meters. Recorder and Energy bulk actions are outside this authorization; a read-only guidance view does not authorize activation.

**Still required:** latest #118 reconciliation, full keyboard and focus, genuine 200% text zoom, screen readers, touch target checks, computed-contrast review in actual HA themes, private live HA business acceptance of all 56 cases, and separately authorized merges/releases. No issue closure from green CI alone.
