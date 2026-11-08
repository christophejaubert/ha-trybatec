# Trybatec b7 development and validation plan

**Status:** b7 source was promoted to `main` after synthetic test validation. Publication is controlled separately from installation and real historical imports; the latter remain unauthorized pending field verification.

## Included features

1. Read-only historical EUR cost estimates grouped by French-local civil year,
   fluid (EF/ECS/CET) and evidence class (measured near-daily versus separately
   approved accounting attribution); no silent annual tariff fallback.
2. Read-only diagnostic action exposing gaps, index declines, missing units,
   conflicting observations and ambiguous physical meter succession.
3. Bounded Trybatec HTTP responses and limited retries for temporary statuses;
   permanent failures do not trigger repeated calls.
4. Synthetic automated tests for per-meter scaling, sparse gaps, DST/year-end,
   cross-lot identity isolation, admin-only actions and network conditions.

## Validation gates

- GitHub Actions: Python compile, pytest, import with latest published HA,
  manifest check, brand dimensions, and scanned repository files.
- On a backed-up test instance: compare unit labels with the physical meter,
  try water-only, heating-only, multiple lots, sparse history and retired
  meters. Check admin-only access, rate years, and read-only action outputs.
- Perform b6 regression tests on real data before b7 promotion. Ensure Recorder
  pending verification, entity migration and Energy dashboard selections are
  unaffected.
- Document and fix any b6 defects on their own branch and incorporate the
  patches into this b7 branch before final release review.

**Known limitations:** Undocumented portal field names, unaudited tariff
inputs, unavailable independent vendor invoice data, no automatic Recorder
or Energy dashboard migration, no claim of complete interval coverage.
The EUR results are estimates, not an approved statement of charges.


## Recette fonctionnelle complémentaire — 8 novembre 2026

Référence : [issue #6](https://github.com/christophejaubert/ha-trybatec/issues/6).
Cette section représente l'état de tests synthétiques, **pas une autorisation
d'import de données réelles** ni de publication.

| Critère | État de preuve |
| --- | --- |
| Reprise sur source modifiée | PR #7 fusionnée : empreinte source/plan, refus avant enfilement |
| Interruption de trois compteurs | PR #8 fusionnée : quatre pannes injectées sur Recorder SQLite réel après rechargement HA et quatre scénarios sur deux processus HA avec adaptateur SQLite durable |
| Confirmation Recorder | Tests de sommes exactes, lignes manquantes, incohérentes, doublons, réponses invalides et validation partielle compteur par compteur ; chaque série non confirmée reste pending |
| Unités d'index | Tests explicites m³, L, kWh, MWh, GJ ; unités contradictoires, non identifiées et incompatibles exclues |
| Migration b6 → b7 | Tests CI de persistance et tests des identifiants des séries ; pas de changement automatique de sélection Energy |
| Historique / antidatage | Tests synthétiques de corrections datées, validation des choix hors période et persistance de décisions lors d'un redémarrage de processus |

**Limites non levées** : absence de vérification des unités sur les compteurs
physiques de l'utilisateur, décisions sur les anomalies historiques réelles,
restauration d'une sauvegarde non testée, pas de crash brutal du thread
Recorder à l'intérieur d'une transaction SQLite. La vérification des entités
réelles, des versions/notes de release et de l'ergonomie sur l'instance cible
doit précéder toute autorisation de migration en production.

La publication d'une version expérimentale exige une recette documentée de l'issue #6, les contrôles obligatoires réussis sur `main`, la revue d'un brouillon créé manuellement et une décision explicite de publication. Cette décision n'autorise pas les imports historiques réels.
