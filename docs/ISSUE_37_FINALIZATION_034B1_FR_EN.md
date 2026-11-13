# 🤖 Finalisation #37 — continuité physique / Physical lineage continuity (0.3.4b1)

**Statut / Status :** travail de développement ciblé, PR en brouillon ; aucun changement Home Assistant, Recorder ou Énergie. / Targeted development, draft PR; no HA, Recorder or Energy mutation.

**Références / References:** [#37](https://github.com/christophejaubert/ha-trybatec/issues/37), [#36](https://github.com/christophejaubert/ha-trybatec/issues/36), [#88](https://github.com/christophejaubert/ha-trybatec/issues/88), [#45](https://github.com/christophejaubert/ha-trybatec/issues/45), [candidate #147](https://github.com/christophejaubert/ha-trybatec/pull/147), [source #125](https://github.com/christophejaubert/ha-trybatec/pull/125).

## FR — Périmètre réalisé

Le contrat #37 reprend les modules existants **sans second stockage** :

- `meter_lineage_37.py` : identité physique immuable par compte/lot/fluide/série ; états en service/déposé/inconnu ; références de source, variantes retenues, bornes observées et dates de service prouvées seulement ; une, deux et trois générations ou plus ; successions confirmées, possibles, chevauchantes et parallélismes soumis à vérification indépendante. Les intervalles inter-observations sont fournis explicitement avec `consumption: null` : ce ne sont ni des dates de remplacement ni une preuve de consommation nulle.
- `lineage_history_bridge_37.py` : union conservatrice des compteurs issus de l'historique qualifié #36, du cache actuel et des archives physiques. Une seule variante quotidienne sélectionnée par compteur ; les compteurs absents des variantes empêchent tout total consolidé du groupe. Contrôles de statut, unité, source, filiation et périmètre. Les décisions d'estimation multiples sont empreintées **en tant qu'ensemble**, sans prétendre que la première décision autorise chaque journée.
- `lineage_energy_handoff_37.py` : enveloppe de preuve **non autoritaire** destinée à #88. Identités et statuts observés, compteurs déposés/inconnus, contributions et somme exacte, lacunes, empreinte de l'inventaire physique, empreinte des lignes journalières et catalogue optionnel des versions/statistiques et références Énergie déjà observées. Les catalogues manquants sont signalés comme tels. Le SHA du groupe inclut maintenant les empreintes de source et de contribution, sans rompre le calcul v1 attendu par #88.
- `tests/test_lineage_final_37.py` : cas fictifs multi-générations, scénarios de lacunes, recouvrements, parallélismes, unités, collisions de fluide, provenance et estimations, conflits, références Recorder/Énergie, empreintes, rechargement, fausses attestations et non-écriture.

La présence d'un compteur au sein des éléments observés **ne prouve jamais** que tous ses prédécesseurs ont été retrouvés. Le statut historique d'un appareil déposé ne lui attribue aucune mesure temps réel.

### Cas et garanties

| Scénario | Résultat attendu |
| --- | --- |
| Un seul compteur / Single meter | Consommation calculée du compteur, état non autoritaire |
| Deux ou trois générations et plus | Conservation des identités ; somme des *consommations* par jour, jamais somme d'index |
| Période non observée | Intervalle explicite, quantité inconnue et aucune mesure inventée |
| Chevauchement non approuvé | Refus de consolidation ; autorisation parallèle seule = prévisualisation et revue indépendante |
| Unité manquante ou incompatible | Série du compteur bloquée et groupe incomplet |
| Diminution d'index, conflit de statut/source | Groupe bloqué, aucune variante partielle silencieusement exclue |
| Même série sur plusieurs fluides/logements | Identité composée, groupes séparés |
| Déposé/actif/inconnu | État conservé ; statut inconnu non converti en actif |
| Estimations linéaires | Uniquement décisions qualifiées #36 ; aucune inférence « manuel/automatique » |
| Versions Recorder et source Énergie existante | Références observées signalées ; alternatives et exclusivité restent à attester indépendamment |
| Redémarrage simulé / reprise | Sérialisation JSON déterministe de l'enveloppe, aucun nouveau registre |
| Écriture native | Toujours interdite dans #37 ; sauvegarde/activation régies séparément par #36/#88 |

### Contrat définitif producteur #36

Le producteur #36 fournit, depuis un backend de confiance : (1) **tous les compteurs physiques connus** par lot et fluide, avec clés exactes et empreintes de source ; (2) relevés bruts horodatés et conflits ; (3) unités vérifiées et consommations *journalières* approuvées par compteur, `raw` ou `smoothed` ; (4) justification de chaque estimation et lacune, avec provenance `measured`, `estimated_linear_confirmed` ou `mixed` ; (5) inventaire des versions Recorder candidates et de leurs fenêtres persistées. Le pont #37 valide les clés, le périmètre, les choix, les sommes et les incohérences, **mais ne certifie pas** le caractère exhaustif du portail, ni la persistance réelle Recorder. L'attribution d'une décision à un jour précis doit être prouvée côté #36 ; une empreinte de décisions en ensemble n'en tient pas lieu. Ne pas modifier les `statistic_id` existants ni les versions historiques.

### Contrat définitif consommateur #88

Le consommateur #88 reçoit `lineage_37_energy_handoff_v1`, avec `groups` et `fingerprint` calculé à partir du JSON canonique des groupes (compatible avec `reconcile_draft_provenance_l6`). Les nouveaux champs de chaque groupe comprennent :

- `physical_scope_fingerprint` : lie comptes de provenance, identités, statuts, bornes, unités et empreintes de source réellement **observés** ;
- `daily_evidence_fingerprint` : lie journées, provenance, quantités, cumul et variantes retenues ;
- `observed_unread_intervals` : nombre d'intervalles connus sans attestation de consommation ;
- `statistic_reference_catalog_observed` et `observed_competing_statistic_ids` : versions candidates éventuellement observées ;
- `selected_energy_catalog_observed` et `observed_selected_energy_statistic_ids` : références Énergie éventuellement déjà sélectionnées ;
- `blockers` : lacunes, chevauchements, identités non prouvées, catalogues manquants, références concurrentes ou étrangères.

Les références restent **des instantanés d'observation**, et non des certificats d'exhaustivité. Pour les renseigner, #88/#36 doivent collecter indépendamment les IDs Recorder existants (V4/V5/B15 et autres), le ledger #36, leurs métadonnées et fenêtres lues en retour, **toutes** les préférences Énergie actives, les propriétaires de statistiques externes et l'inventaire historique du portail. Les catalogues sont optionnels dans l'API pour conserver la compatibilité avec l'adaptateur lot B existant ; toute absence engendre des motifs explicites de refus.

Le consommateur #88 **doit** vérifier indépendamment les preuves ; la présence ou la correspondance d'une empreinte interne n'est jamais une autorisation. Toujours `physical_inventory_complete=false`, `recorder_persistence_verified=false`, `competing_versions_exhausted=false`, `energy_activation_authorized=false`, `writes=false`. Il ne peut activer deux sources couvrant la même consommation. Le branchement effectif à une transaction L7 native et la reprise appartiennent à #88.

### V-01 à V-12 — qualification sans glissement de périmètre

| Critère | État de travail, avant recette HA |
| --- | --- |
| V-01 Nettoyage entités techniques obsolètes | **Exclu** de 0.3.4b1 : audit seulement ; migration/effacement prohibés |
| V-02 Exposition anciens appareils/capteurs | **Partiel** : mécanismes existants d'archivage et capteurs historiques, qualification effective et exhaustivité à recetter |
| V-03 Statut explicite | **Développé**, recette de l'IHM/appareils requise |
| V-04 Identité, unités, bornes, anomalies | **Développé** dans le contrat, sources réelles à auditer |
| V-05 Continuité multi-remplacements | **Développé**, tests synthétiques, validation réelle des générations requise |
| V-06 Inclusion des anciens dans Énergie | **Partiel**, dépend des écritures et preuves opérationnelles #36/#88 non validées |
| V-07 Tests, sauvegarde, non-régression | **Partiel** : tests synthétiques ; migrations exclues ; sauvegarde/reprise HA sous autorisation distincte |
| V-08 Origine manuelle/automatique inconnue | **Développé**, ne jamais déduire de la fréquence |
| V-09 Pas d'hypothèse sur le portail | **Développé** côté contrat, règles de répartition #36 |
| V-10 Inventaire intergénérations exhaustif | **Partiel**, union conservatrice observée ; exhaustivité réelle non attestée |
| V-11 Migration d'identifiants hérités | **Exclue** de 0.3.4b1 : PR #82 non reprise |
| V-12 Continuité et exclusivité Énergie | **Partiel**, garanties de prévisualisation et refus, activation effective #88 non qualifiée |

### Recette en production — consultation uniquement

**Conditions :** aucune installation, modification, sauvegarde, migration, import Recorder, changement des préférences Énergie, restauration ou nettoyage ne découle du présent protocole ; chacune nécessite sa propre autorisation.

1. Après autorisation distincte d'installation d'une version construite sur un SHA qualifié, vérifier en **lecture seule** l'inventaire physique du logement et des fluides EF/ECS/CET : en service, déposés, inconnus, numéros de série, unités, première/dernière observation, bornes et sources de chaque statut.
2. Rapprocher les générations avec les relevés **bruts** réellement consultables et les archives, sans déduire une date de remplacement d'une simple absence de relevé. Noter en privé les lacunes, décroissances, anomalies et source de preuve de chaque filiation.
3. Vérifier la visibilité des appareils/capteurs historiques et la stabilité des entités existantes **sans action sur le registre** ; comparer les dépendances des tableaux de bord et automatisations en lecture seule.
4. Vérifier les métadonnées Recorder, les versions concurrentes et leurs plages de dates par requêtes **sans écriture**. Relever, sans publier de données réidentifiantes, les conflits de versions et les statistiques historiques encore utiles.
5. Lire les références du tableau Énergie sans les modifier ; vérifier qu'une référence existante reste conservée et qu'aucune double source n'est activée. Confronter totaux journaliers admissibles et preuves de conservation des contributions.
6. Exécuter les scénarios destructifs, défaillances, restauration et double comptage **uniquement sur des jeux de données fictifs**, jamais sur l'instance réelle. Classer chaque critère satisfaisant, partiel, exclu ou non recetté avec SHA et horodatage.
7. Conserver journaux, identifiants personnels et relevés chiffrés **hors du dépôt GitHub public**. Ne publier que conclusions agrégées non réidentifiables.

**État de recette** : non effectué. Aucun de ces points ne peut être marqué « validé sur production » par la seule CI.

## EN — Implementation, obligations and acceptance

The #37 code reuses the existing meter-lineage engine, history bridge and Energy handoff without creating a new database or a separate historical truth. It preserves account/lot/fluid/serial identities, current/retired/unknown service status, qualified units and source fingerprints. The exact history intervals without observation are exposed as **unknown consumption**, not fabricated zeros or inferred replacement dates. Parallel contributors require independent authorization; raw indexes from different meters are never added. Selected, qualified daily consumption variants are summed only after checking physical membership and duplicate-day constraints.

The #36 interface remains the exclusive producer of qualified raw readings, revised daily consumption, approved smoothing decisions and Recorder version/persistence evidence. A fingerprint covering multiple decisions **does not prove which approval applies to a particular day**; that attribution remains a #36 dependency.

The #88 v1 envelope remains compatible with the existing L6 groups-only SHA-256 check while the added group-level physical and daily fingerprints bind the actual sources, selected variants, dates and contributions. Optional read-only catalogs carry observed competing statistic IDs and currently selected Energy references; their absence and conflicts are explicit blockers. **None of these catalogs proves completeness.** #88 must collect and independently reconcile exhaustive legacy/current Recorder versions, metadata and persisted windows, all live Energy references, meter inventory and supported fluid schema, then enforce exclusive selection and safe L7 rollback. No #37 output grants activation.

V-01 and V-11 legacy-ID cleanup/migration are excluded; V-02/V-06/V-07/V-10/V-12 remain partly unqualified pending full source inventory, native wiring and production acceptance. Other #37 physical-identity and conservation behaviors have synthetic code coverage, not live acceptance.

The production-only read-only acceptance sequence above checks physical generations, historic devices, existing entity/statistic references, incomplete coverage and consumed Energy sources, without making any changes. Destructive restoration, writer failure and duplicate replay scenarios belong exclusively to fictitious isolated tests. Every production-affecting action requires separately scoped user authorization. The issue remains open until all in-scope functionality and independent evidence are genuinely qualified.
