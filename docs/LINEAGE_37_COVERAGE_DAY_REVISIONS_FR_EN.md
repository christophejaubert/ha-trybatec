# 🤖 #37/#81 — Exhaustivité, générations et décisions / Coverage, generations and day revisions

<!-- BO-DELIVERY-DOC-20261113 -->
## 🤖 Décision BO applicable / Governing business decision — 13/11/2026

**FR —** La découverte de tous les compteurs **observés par les données disponibles** et la comparaison avec un éventuel inventaire fournisseur demeurent importantes, mais **aucun certificat d'exhaustivité absolue de toute l'histoire d'un logement n'est exigé**. `historical_account_exhaustiveness_verified=false` décrit une **limite de portée**, pas un refus global automatique de toute période délimitée. Pour #88, fournir une qualification **sur les compteurs, journées, sources, révisions et fenêtres de l'opération sélectionnée** : attestée, partielle, inconnue ou contradictoire ; permettre une approbation explicite de périodes non attestées, avec provenance correctement étiquetée. Une inconnue hors sélection ne bloque pas mécaniquement ; une contradiction, un chevauchement, une double attribution ou une approbation non vérifiable **dans** la sélection bloque.

**Rappel #37 :** calculer les consommations **par compteur physique**, jamais l'écart d'index entre compteurs remplacés ; consolider uniquement les consommations compatibles sans recouvrement. Une journée sans relevé API n'est pas un zéro et reste éligible, sous #36, à un lissage linéaire validé avec estimation traçable. L'utilisateur compare le portail Trybatec et signale les incohérences au fournisseur.

**EN —** Observed physical lineage and supplier-catalog comparison are retained, but **no absolute full-property-history certificate** is required. A false `historical_account_exhaustiveness_verified` is a scope limitation, not an unconditional veto on a bounded selected operation. Provide attested/partial/unknown/contradictory qualifications **by selected physical generation, date, decision, source and revision**. Explicit user approval can include unknown spans without turning estimates into observations. Reject in-scope conflicts, overlap, duplicate allocations or unauthenticated decisions; don't reject only because of unrelated outside-scope unknowns. Meter readings are differenced within each physical generation, then compatible derived consumptions may be combined. Missing data are not zero.

**Coordination :** #37/#81 → #36 → #88 → #164; `docs/CONVERGENCE_CURRENT_FR_EN.md` sur #164. Les anciens constats d'inventaire global ci-dessous restent des limitations factuelles, non des prérequis de publication.

<!-- END-BO-DELIVERY-DOC-20261113 -->


**Périmètre / Scope:** contribution #160 uniquement, lecture seule, données de test fictives. / Draft #160 only, read-only, fictitious tests.

**Références / Links:** [#37](https://github.com/christophejaubert/ha-trybatec/issues/37), [#81](https://github.com/christophejaubert/ha-trybatec/issues/81), [#36](https://github.com/christophejaubert/ha-trybatec/issues/36), [#88](https://github.com/christophejaubert/ha-trybatec/issues/88), [convergence #164](https://github.com/christophejaubert/ha-trybatec/pull/164), [MOE #45](https://github.com/christophejaubert/ha-trybatec/issues/45).

## FR — Source de vérité et portée

`main` contient déjà le modèle de filiation #125/#150/#153. #160 ne reconstruit pas le moteur historique #36 et n'exécute aucune recherche fournisseur. L'inventaire des compteurs physiques ne provient **jamais** de suffixes d'entités Home Assistant ni de statistiques Recorder : il est indexé par (compte, lot, fluide, série physique), avec statut en service/déposé/inconnu et bornes **observées** distinctes des dates de service **prouvées**.

La recherche C11 peut établir la complétude **d'une plage demandée** ; elle ne prouve pas, à elle seule, l'absence de compteurs remplacés avant cette plage ou jamais observés. `observed_catalog` compare les identités, les empreintes de source, les nombres de relevés et les bornes horodatées d'un catalogue *fourni* à l'union historique/cache/archive. `supplier_discovery.status=complete` désigne seulement le statut de la collecte fournie ; il ne valide ni le périmètre global ni son authenticité. Les entrées du catalogue absentes de l'historique deviennent visibles comme générations **inconnues et bloquées** ; aucune consommation n'est estimée et aucune disparition n'est déduite du catalogue incomplet. Les observations séparées de plus de 27 h sont exposées comme périodes à consommation inconnue, avec seulement 32 intervalles détaillés par compteur (nombre total conservé).

**Contrat `prepare_physical_continuity_37` :**
- Paramètres facultatifs `observed_catalog=[{lot, fluid, serial, observation_count?, source_fingerprint?, first_observed_at?, last_observed_at?, status?}]`, `supplier_discovery={status: complete|incomplete|interrupted|error|in_progress|never_started|not_started|running|failed|cancelled|queued|cache_invalidated|unknown}`. Les états C11 `not_started` et `running` restent explicitement non probants.
- Sortie `inventory_reconciliation` : `status` (contradictoire/partiel/inconnu), comptes, concordances, différences explicites, état de découverte, `historical_account_exhaustiveness_verified=false`.
- Les divergences de série, bornes, empreintes, nombre d'observations ou statut connu engendrent des refus déterministes. Une comparaison concordante reste **partielle**, jamais « inventaire historique complet ».
- Les dates `service_start/service_end` ne sont pas déduites de `first_observed_at/last_observed_at`. Un changement de compteur reste un lien confirmé sur preuve explicite, possible ou indéterminé ; une lacune n'est pas une consommation nulle.

### Décisions historiques et révisions #36

Le backend #36 expose aujourd'hui `selected_gap_fingerprints`, `raw` et `smoothed`. Cette liste sélectionnée n'est **pas** une carte jour→approbation. #160 accepte, **optionnellement**, un contrat plus précis `decision_daily_allocations` rattaché à la variante physique sélectionnée :

```python
{
    "interval-example": {
        "lot": "LOT-EXAMPLE", "fluid": "EF", "serial": "A",
        "source_fingerprint": "f" * 64,
        "revision_fingerprint": "a" * 64,
        "daily_estimated": {date(2026, 1, 2): "0.5"}
    }
}
```

Ce record contient une *allocation explicite* jour→quantité estimée, l'identité physique et une empreinte de **révision exacte** ; il ne contient aucune permission d'écriture. Il doit couvrir les décisions déclarées sélectionnées, respecter leur source et révision, ne pas réattribuer une journée à deux décisions et vérifier chaque montant face à `smoothed-raw`. La journée reçoit `decision_attribution=day_revision_candidate_unverified` et son `revision_fingerprint`; en l'absence d'allocation journalière, l'approbation demeure `approval_set_unattributed` (blocage). Une simple paire jour→référence demeure `day_candidate_unverified`.

Le qualificatif `candidate_unverified` signifie que **l'assertion est syntaxiquement et arithmétiquement rapprochée, mais non encore authentifiée** : #36 doit comparer l'allocation à ses véritables décisions persistées, leur fenêtre, leur révision, les index et le fingerprint source et le bon compte physique. Ni l'approbation globale ni l'empreinte émise par #37 ne confèrent d'autorité métier.

### Matrice transmissible à #88 : preuves et refus exacts

| Contrôle | Preuve produite par #37 | Qualification | Refus / preuve restante |
| --- | --- | --- | --- |
| Identités physiques | Compte/lot/fluide/série et empreinte source, état de dépôt | Structure vérifiée localement | `historical_account_exhaustiveness_not_attested` : découverte complète de tous les remplacements non démontrée |
| Catalogue fournisseur | Diff entre histoire, cache/archive et `observed_catalog` | Inconnu, partiel ou contradictoire | `physical_catalog_comparison_unavailable`, `physical_catalog_scope_not_exhaustive` ou `observed_physical_catalog_contradiction` |
| Découverte historique | Statut externe `supplier_discovery` annoté | Uniquement plage requise | `account_historical_discovery_not_complete` si absent/interrompu/erreur ; même « complete » reste non exhaustif du compte |
| Périodes physiques | Bornes de relevés, trous source et intergénérations, service nullable | Prévisualisation vérifiée localement | Lacunes non renseignées, chevauchement non autorisé, statut inconnu ; aucune date déduite |
| Décision estimée par jour | Jour, compteur, variante, montant, référence et révision **fournis et concordants** | Candidat non authentifié | `estimated_day_decision_not_individually_attributed`, `day_decision_requires_independent_36_match`, `day_revision_requires_independent_36_match` |
| Conservation de consommation | `measured + estimated == consumption`, cumul et identité de chaque contributeur | Vérifiée arithmétiquement | Incohérences refusées ; attestation indépendante de chaque fenêtre Recorder #36 absente |
| Absence de double source | Catalogues *observés* de versions/statistiques et préférences Énergie | Partielle seulement | `statistic_version_catalog_not_collected`, `energy_selected_references_not_collected`, `competing_energy_sources_selected`, `statistic_id_reused_across_logical_scopes`, `energy_selection_reused_across_logical_scopes` |
| Persistance et exclusivité | Aucun accès en écriture depuis #37 | Non démontrées | `recorder_persistence_verified=false`, `competing_versions_exhausted=false`, `energy_activation_authorized=false` |
| Identifiants hérités #81 | Références observées exactes, coexistence stable/legacy, suffixes HA | Audit partiel | Inventaire consommateurs externes non exhaustif ; `safe_to_migrate=false`, `safe_to_delete_legacy_entity=false` |

Les noms de refus dans cette matrice sont des éléments d'interface pour le service de qualification #88 ; une liste de refus vide *sur les données reçues* ne suffit jamais pour conclure « admissible ». Les versions Recorder V4/V5/B15 et les sources énergétiques tierces doivent être retrouvées **dans l'environnement autorisé** puis confrontées aux lectures persistées, à la configuration Energy active et aux versions alternatives.

### Fenêtres Recorder observées / Observed Recorder windows

Le transfert #37→#88 accepte désormais **facultativement** `known_statistic_windows={(lot,fluid): [{statistic_id, start, end, unit, owner}]}`, où `start/end` sont des journées ISO inclusives et `owner` vaut `trybatec`, `external` ou `unknown`. Cette preuve est uniquement un **inventaire fourni**, distinct des fenêtres effectivement relues dans Recorder. Les métadonnées de version historiques V4/V5/B15 doivent être collectées et comparées indépendamment par #36/#88.

Les nouveaux motifs de refus incluent `recorder_window_catalog_not_collected`, `statistic_window_metadata_incomplete`, `selected_energy_window_not_observed`, `recorder_window_unit_incompatible` et `overlapping_recorder_versions_require_exclusivity_review`. Un chevauchement entre deux versions historiques *possibles* n'est pas la preuve qu'elles sont simultanément actives, mais interdit de conclure à l'exclusivité sans examen des préférences et de la version active.

**EN:** Optional `known_statistic_windows` records observed statistic IDs, exact inclusive calendar windows, units and observed ownership. This is *not* native Recorder readback. Missing windows, incompatible units, cross-scope reused IDs, competing selections and overlapping candidate versions produce explicit fail-closed evidence reasons. Independent Recorder storage and live Energy preferences remain the authority boundary.

### Tests indépendants réalisés et limites

Scénarios synthétiques prévus : deux générations successives sans date de remplacement déduite, compteur déposé découvert uniquement dans le catalogue, observation manquante, contrôle des anomalies d'index, désaccord entre nombre/empreinte du catalogue, catalogue ne contenant pas toutes les générations observées, origine hors période, statut de recherche interrompue, approbation globale non attribuable, décision précise avec révision concordante ou contradictoire, journée attribuée deux fois, doublon statistique inter-fluides, références de consommateurs hérités. Tous les noms de compte, logement et compteur dans les tests sont fictifs.

**À acquérir séparément :** preuve d'inventaire fournisseur sur le périmètre complet de l'historique, borne de première existence du compte si vérifiable, attestation #36 des révisions et allocations, relecture native des fenêtres Recorder, inventaire des versions concurrentes et des sources Énergie, test transactionnel L7, sauvegarde/restauration et recette HA réelle. Ces opérations ne sont pas couvertes par #160.

## EN — Evidence boundary and next gates

The #37 lineage code now cross-checks an optional *observed* catalog against physical historical meters, current cache and archives: identity, source fingerprint, observation count, timestamp boundaries and conflicting status. It preserves catalog-only retired candidates as unknown/blocked generations and reports sparse observation spans as **unknown consumption**; neither service dates nor replacement transitions are inferred. A complete C11 **requested interval** is not independent proof of complete account history. Inventory scope remains `partiel` even when supplied records match, `contradictoire` for conflicts, `inconnu` without a catalog, and `historical_account_exhaustiveness_verified=false` invariably.

The optional `decision_daily_allocations` mapping requires an exact physical source, 64-character revision fingerprint and explicit daily estimated quantities that reconcile with the source variant. This is stronger *local* verification than a pooled approval list; it is still `day_revision_candidate_unverified` until #36 independently matches the actual decision ledger and persisted revision. Pooled approvals are never promoted to per-day approvals. #37 forwards day/contributor/source/revision/amount context and explicit blockers to #88, alongside observed statistic and Energy catalogs, cross-scope duplicate-ID checks and conservative unknown gaps.

#88 must independently qualify complete source inventory, competing versions, native Recorder readback, selected Energy references, non-duplication and transactional L7. #81 remains an audit only; suffixes such as `_2` are technical Home Assistant IDs, not physical generations, and no migration, deletion, restoration, Recorder write, Energy change, merge, release or Home Assistant mutation is part of this work.
