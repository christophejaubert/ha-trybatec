# 🤖 Compteurs physiques et filiation #37 / Physical-meter lineage #37

> **État / Status (2026-11-12):** prototype de contrat indépendant en lecture seule; **pas** de branchement Home Assistant, Recorder ou Énergie, **pas** de migration, **pas** de validation métier réelle. / Independent read-only contract prototype; **not** connected to HA, Recorder or Energy; no migration or real-world acceptance.

## FR — Décisions et matrice V-01 à V-12

Source de vérité fonctionnelle : [issue #37](https://github.com/christophejaubert/ha-trybatec/issues/37), y compris **R-01/R-02/R-03 rejetées**. Cible approuvée pour la préparation : `0.3.4b1`. Le périmètre MOE D2–D6 conserve la continuité des compteurs déposés, mais **exclut** la migration et le nettoyage d'identifiants hérités associés à [PR #82](https://github.com/christophejaubert/ha-trybatec/pull/82).

| Décision | Périmètre cible | Preuve actuellement disponible / Reste |
| --- | --- | --- |
| V-01 Nettoyage contrôlé | **Exclu** (identifiants historiques) | Audit en lecture seule uniquement ; aucun nettoyage |
| V-02 Compteurs déposés historiques | **Incluse** | Capteurs historiques et archivage déjà sur `main`; exhaustivité non démontrée |
| V-03 Statuts explicites | **Incluse** | `panel_api.py` montre trois statuts ; projection du capteur à harmoniser |
| V-04 Traçabilité physique | **Incluse** | `meter_lineage_37.py` sépare dates observées, dates de service et provenance ; connecter aux données qualifiées |
| V-05 Remplacements | **Incluse** | Prévisualisation de générations et décisions empreintées ; vérifier leurs preuves et la couverture |
| V-06 Historique Énergie | **Incluse, dépend de #36/#88** | Consommations seulement ; aucune activation sans preuve Recorder/Énergie |
| V-07 Migration, nettoyage et tests | **Tests fonctionnels inclus ; tests de migration différés** | Tests fictifs non destructifs, tests réels/rollback restant à faire |
| V-08 Origine des relevés | **Incluse** | Origine manuelle/automatique indéterminée sauf indicateur API prouvé ; aucune inférence de cadence |
| V-09 Lissage portail | **Incluse, dépend de #36** | Aucune hypothèse sur le portail ; décisions explicites, sources intactes |
| V-10 Inventaire historique | **Incluse** | Un cache de compteurs courants ne prouve pas les compteurs historiques manquants |
| V-11 Migration non destructive | **Exclue** (identifiants historiques) | PR #82 séparée et non fusionnée |
| V-12 Continuité technique | **Consolidation incluse ; migration d'identifiants exclue**, dépend de #36/#88 | Série logique stable, vérification des versions et référence Énergie encore manquantes |

**Règles rejetées maintenues :** ne jamais effacer les anciens compteurs physiques lors d'une mise à jour (R-01) ; ne jamais exclure systématiquement leurs consommations d'Énergie (R-02) ; ne jamais additionner des index bruts provenant de compteurs différents (R-03).

### Contrat de prévisualisation `preview_lineage`

- **Entrée** : compte, liste physique bornée (lot, fluide EF/ECS/CET, série, statut), empreinte de source, unité canonique vérifiée, observations et dates de service éventuellement inconnues ; variantes de **consommation journalière**, sélection unique par compteur ; filiation explicitement confirmée avec empreintes et référence probante ; éventuelles paires réellement parallèles dûment autorisées.
- **Identités** : clé physique `(account, lot, fluid, serial)` ; identité logique historique par `(account, lot, fluid)`. Les `entity_id`, `device_id`, `unique_id` et `statistic_id` historiques ne sont ni calculés à nouveau pour le registre, ni modifiés.
- **Sortie** : statut courant ou inconnu, périodes **observées** distinctes du début/fin de service, liens de générations et leur statut, lignes journalières de consommations et provenance, somme cumulée indépendante des index d'origine, motifs bloquants. En cas de chevauchement non approuvé, aucune ligne consolidée n'est proposée.
- **Exclusions** : pas de détermination automatique d'une date de remplacement, pas de reconstitution des journées manquantes, pas de qualification automatique manuel/automatique, pas de copie du lissage #36, pas de contrôle exhaustif des statistiques/consommateurs externes.
- **Verrous non négociables** : `full_historical_coverage_verified=false`, `version_exclusivity_verified=false` et `energy_activation_authorized=false`, même lorsque l'inventaire fourni semble complet. Une confirmation de filiation n'autorise aucune écriture.
- **Données de test** : identités et valeurs fictives ; aucune référence à l'installation réelle publiée.

### Contrats avec #36 et #88

**#36 — historique / Recorder** : l'adaptateur futur doit utiliser les objets validés de `history.py`, `history_variants_b15.py`, `history_plan_b15.py` et `history_versions_b15.py` ; conserver l'identité physique et les empreintes ; distinguer journées mesurées et estimations approuvées, restituer lacunes/rejets, convertir uniquement des unités vérifiées (EF/ECS m³ ; CET kWh). Sélectionner exactement une variante par compteur puis une version consolidée par logement/fluide, sans addition d'index. Les versions Recorder restent sous la responsabilité de #36.

**#88 — preuve d'admissibilité Énergie** : fournir, en lecture seule, l'inventaire historique exhaustif attesté par une source indépendante, la correspondance de chaque compteur (y compris déposé) à la version consolidée, les dates couvertes, lacunes, conflits, unités, empreintes et provenance, puis la liste des alternatives concurrentes. `energy_bulk_evidence.py` ne peut déduire cette exhaustivité du seul cache courant ou du seul journal B15. Tant que les preuves ne sont pas disponibles, préserver le blocage `blocked=true`, `activation_authorized=false`. La transaction Énergie, les sauvegardes, la persistance Recorder, les préférences HA et leur rollback appartiennent à #88/#36 et à une autorisation distincte.

**#120 — identités neuves** : conserver l'ancien comportement des comptes existants ; les identités stables sans unité ne s'appliquent qu'aux nouveaux comptes. Ne reprendre aucun exécuteur, adaptateur de migration ou nettoyage de #82. Cette PR #37 ne touche ni `sensor.py` ni `panel_api.py`, fichiers partagés avec #120.

### Matrice de recette / qualification

| Test | Attendu |
| --- | --- |
| Un compteur actif ; deux générations ; index initiaux différents | Totaux de consommations, pas somme des index |
| Remplacement avec lacune | Lacune conservée, aucune mesure inventée |
| Remplacement avec chevauchement | Blocage sans preuve d'allocation ou confirmation parallèle bornée |
| Statut inconnu ; service non daté | État inconnu explicite ; ne pas inventer de date |
| Compteur déposé | Conservé avec son identité, empreinte et historique |
| Deux variantes | Une seule sélectionnée ; pas de double comptage |
| Source ou approbation périmée | Refus ; aucune écriture |
| Lot/fluide différent, collision, référence historique | Refus de mélange, aucune mutation de registre |
| Rechargement / reprise | Sortie déterministe sur entrées inchangées |
| Énergie/Recorder et HA réel | **Non recettés** : essais ultérieurs distincts |

**Statuts de qualification** : développé = module isolé ; testé = vérifications exactes du code de PR à établir ; recetté = NON ; fusionné = NON ; publié = NON ; installé = NON. L'issue #37 demeure ouverte, notamment pour ses critères de migration exclus de la version cible.

### Suite recommandée

1. Faire approuver la PR de contrat seul après CI, sans annoncer la continuité complète.
2. Compléter #36 avec des consommations journalières traçables, prouvées et versionnées ; alimenter `preview_lineage` avec des données réelles seulement dans un environnement autorisé.
3. Ajouter l'adaptateur serveur de preuve historique #37→#88 sans effacer les verrous et tester les références Recorder/Énergie sur une instance représentative.
4. Qualifier l'IHM et les capteurs historiques en coordination avec #120 ; toute fusion, migration, import ou activation exige sa propre autorisation.

## EN — Decision, interfaces and acceptance

Functional source: [issue #37](https://github.com/christophejaubert/ha-trybatec/issues/37); D2–D6 approve retired-meter continuity for target `0.3.4b1` but expressly **exclude legacy entity-ID migration and cleanup** (draft #82). V-02/V-03/V-04/V-05/V-08/V-09/V-10 are in scope; V-06 and the consumption/continuity portion of V-12 depend on #36/#88; functional parts of V-07 are in scope while historical migration tests and V-01/V-11 are deferred. The R-01, R-02 and R-03 proposals remain rejected.

`preview_lineage` is a pure, bounded, **read-only proposal**. Input contains exact physical meter scope, observed and service bounds (nullable), verified normalized units, source fingerprints, one selected **daily consumption** variant per physical meter, and optional fingerprint-anchored successor or parallel-use evidence. Output includes physical generations, status, provenance, blockers and dwelling/fluid consumption sums; it **never** merges cumulative raw index values or fabricates replacement dates and missing observations. Unknown statuses remain unknown, overlapping meters fail closed unless their parallel use is explicitly verified, and historical entity/statistic references remain untouched.

The #36 producer owns measurement/estimate qualification, gap review, normalized units, history revisions and Recorder persistence. The #88 consumer must independently prove **complete** physical and historical coverage, retired-meter inclusion, all competing statistic versions, Recorder persistence and Energy preference exclusivity. This module does **not** claim these proofs: `full_historical_coverage_verified=false`, `version_exclusivity_verified=false`, `energy_activation_authorized=false` always. No live Energy or Registry modifications, automatic cleanup, #82 migration code or deployment is part of this PR. Coordinate any `sensor.py`/`panel_api.py` changes with open #120.

Synthetic regressions cover active, retired and unknown meters, successive generations, gaps, overlaps, initial index differences, one variant selection, stale approvals, cross-dwelling rejection and deterministic reloads. **CI on exact head, read-only server integration, representative HA acceptance, Recorder/Energy proof and restoration are still separate gates.** Keep #37 open; a draft or passing CI does not signify completion, merge, publication or installation.

## FR — Compléments de raccordement qualifiables (#125)

**Modules réellement présents sur cette branche :**
- `lineage_history_bridge_37.py` — adaptation *en lecture seule* des historiques `build_history` et variantes `variants_preview` de #36 ; mélange prudent des identités trouvées dans la source historique, le cache courant et les archives conservées. Les compteurs sans série qualifiée bloquent le groupe plutôt que de disparaître du total.
- `meter_lineage_37.py` — filiation par logement et fluide, statut inconnu, sélection unique des variantes, empreintes physiques, unités vérifiées, dates de service non déduites des observations, prévention des chevauchements et conservation des sommes journalières avec la contribution par compteur. Provenance `measured`, `estimated_linear_confirmed` et `mixed` ; le mixte exige deux contributions strictement positives et leur somme exacte.
- `lineage_energy_handoff_37.py` — enveloppe de preuve **non autoritaire** vers #88 : comptes de compteurs physiques/déposés/inconnus, provenance, conservation des contributions et empreinte déterministe. Elle ne prétend pas vérifier un inventaire historique exhaustif, la persistance Recorder ou les références Énergie concurrentes.

**Contrat consommateur obligatoire #88 :** collecter lui-même les sources originales, vérifier toutes les générations contre l'inventaire historique indépendant et les compteurs du cache actuel, confronter chaque contribution aux lignes Recorder **persistées** et aux fenêtres #36, contrôler les variantes V4/V5/B15 et autres références déjà sélectionnées, vérifier les unités/classes et les préférences actuelles. **Ne jamais** transformer le `fingerprint` de l'enveloppe en preuve autonome de complétude. En cas de doute, `blocked=true`, `activation_authorized=false`.

**Données et comportements non prouvés :** la source historique du portail peut être incomplète (couverture par période et bornes), les dates de remplacement ne sont pas fournies systématiquement, certaines entrées peuvent ne pas avoir d'unité vérifiée, la qualification réelle des chevauchements/estimations dépend des décisions #36, et la consultation d'un relevé archivé n'établit aucune continuité Recorder. La PR ne modifie donc pas l'initialisation native des capteurs ni le tableau Énergie. Les anciennes entités et leurs références restent intégralement inchangées.

**Qualification et recette à réaliser :** tests de bridge sur mesures+estimations le même jour, estimation seule, compteurs actuels absents de l'histoire, archives discordantes, diminution d'index, source modifiée, logement distinct ; tests de handoff sur somme physique, identité et provenance, refus des incohérences et verrouillage Énergie. Rejouer exact-head CI. Un test d'intégration sur Home Assistant **isolé et fictif**, puis la recette réelle séparément autorisée, restent nécessaires avant de déclarer le parcours Énergie opérationnel.

## EN — Integration-ready boundaries and remaining gates (#125)

The branch includes a read-only #36 history bridge, pure meter-lineage consolidation, and a non-authoritative #37→#88 Energy evidence envelope. It retains retired/current/unknown physical meters, declines incomplete histories and ambiguous overlaps, preserves selected per-meter daily consumption and measured/estimated/mixed provenance, validates exact physical contribution sums, and never infers real service dates from observations. The #88 consumer must independently verify complete vendor meter inventories, persisted Recorder windows, version exclusivity, matching schema/units and selected Energy references; a deterministic fingerprint from this module does **not** grant completeness or authorization. All outputs remain **write-free and Energy-disabled**. No legacy-ID migration, entity cleanup, real Home Assistant modification, merge or release is included. CI is necessary but insufficient; isolated HA and separately authorized real-world acceptance are still outstanding.
