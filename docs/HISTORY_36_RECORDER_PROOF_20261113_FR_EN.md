# 🤖 #36 — Preuve Recorder et refus conservés / Recorder proof and retained denials

**Base observée / Observed base:** `main` `8d621da9703b40662800b4a7c286707e8a7f895f` (0.3.4b1), 2026-11-13.  
**Périmètre / Scope:** #36 uniquement ; #37 et #88 consommateurs en lecture seule.  
**Preuves / Evidence:** chemins et tests du dépôt ; le statut des contrôles CI du SHA de cette branche doit être consulté séparément. Aucune recette ni opération Recorder réelle.

## FR — Décision de sûreté

**La reprise sélective Recorder ne peut pas être autorisée en production à ce stade.** Dans Home Assistant, `async_add_external_statistics` place un travail asynchrone dans Recorder. La synchronisation native `Recorder.async_block_till_done()` atteste le traitement des travaux précédant sa barrière, **pas** l'absence future d'un `ImportStatisticsTask` reprogrammé ou d'un écrivain tiers. Le verrou d'import Trybatec est local à l'entrée et au processus, pas un verrou exclusif durable de la base. Il manque une preuve **indépendante, durable et par `statistic_id`** du non-retour des écritures retardées, y compris après incident ou redémarrage. Ni une attente temporelle, ni une file apparemment vide, ni le succès d'un test mocké ne comblent cette lacune.

Le contrat modifié de `preview_pending_recovery` distingue désormais :

- `retry_preflight_candidate` : uniquement une *classification diagnostique en lecture seule*, calculée après un éventuel `queue_quiescent` natif ; aucune autorisation ;
- `retry_candidates_requiring_independent_proof` : les IDs entièrement absents, à contrôler exclusivement après obtention d'une attestation indépendante ; 
- `safe_to_offer_retry=false`, `retry_only_these_statistic_ids=[]`, `independent_writer_fence_verified=false` : **refus exposé à tous les consommateurs**, même si la préqualification est positive ;
- `blocked_statistic_ids` : versions non vérifiées non rejouables au stade du diagnostic ;
- `all_persisted=true` : seulement quand chaque bucket attendu a été relu ; ne prouve ni absence de lignes hors fenêtres, ni absence d'un écrivain tiers futur.

Le serveur `queue_b15_plan` exige toujours une attestation indépendante via `_independent_writer_quiescence_proof` **qui lève une exception en production**. Il relit maintenant Recorder **après** l'acquisition hypothétique de cette attestation : une série devenue persistée pendant l'acquisition est traitée de façon idempotente, jamais rejouée. Une divergence ou une lecture partielle déclenche un refus. Les tests de reprise positive remplacent cette preuve par une fixture fictive : ils ne la démontrent pas sur Home Assistant.

**Aucune opération sur production n'est impliquée.** Les garanties d'exclusion globale, de restauration fiable et de non-interférence restent non qualifiées.

## FR — Matrice REC-01 à REC-16

Légende : **S** = simulation/test identifié dans le dépôt (à confirmer par CI du SHA courant) ; **R** = reste une preuve indépendante ou HA isolé ; **B** = bloque toujours une reprise ou activation réelle. Aucun résultat ci-dessous ne constitue une recette de production.

| Critère | Preuve logicielle/fixture identifiée | Limite et décision |
|---|---|---|
| REC-01 | S : Store journalisé avant enqueue, `test_b15_recovery_crash_l2` | R : véritable crash HA/SQLite isolé |
| REC-02 | S : réponse différée, `test_b15_runtime` | R : engagement natif durable |
| REC-03 | S : buckets/sommes et métadonnées, `test_b15_selective_retry_36` | R : exhaustivité **hors** fenêtres prévues ; B pour admission #88 |
| REC-04 | S : doublons/surplus/discordances, `test_history_recorder_recovery_l2` | R : frontières globales de la série |
| REC-05 | S : batch partiel et seconde lecture post-attestation, `test_b15_recovery_crash_l2`, `test_b15_selective_retry_36` | B : aucun rejeu sans fence durable |
| REC-06 | S : Store recréé à partir du journal | R : arrêt complet + redémarrage isolé avec base Recorder |
| REC-07 | S : barrière seule rejetée, `test_native_barrier_alone_cannot_authorize_a_late_writer_retry` | **B** : écrivain tardif et externe non exclu |
| REC-08 | S : persistance complète → retour sans enqueue | R : recommencer après redémarrage isolé |
| REC-09 | S : V2 préparée avec consentement, V1 conservée, `test_b15_versioned_history` | R : revue HA isolée |
| REC-10 | S : V2 vérifiée ≠ activée, comparaison empreinte | **B #88** : exclusivité Energy native |
| REC-11 | S : V1/V2/V3 et états exclusifs fictifs | **B #88** : transaction native et lecture des préférences |
| REC-12 | S : échec/compensation simulés | R : restauration exclusivement sur environnement isolé |
| REC-13 | S : restauration version archivée confirmée | **B #88** : lecture réelle Energy et rollback |
| REC-14 | S : jours civils 23/25 h et identités physiques distinctes | **B #37** : filiation et couverture intergénérations exhaustives |
| REC-15 | S : unité incompatible, métadonnées natives, snapshots malformés | R : schéma/version exacte d'HA sur système isolé |
| REC-16 | S : empreinte, verrou local, lecture post-fence fictive | **B** : pas de mutex global ou de jeton de génération Recorder durable |

## FR — Contrat C10 pour la conversation UI (#155)

Le backend actuel persiste **uniquement après confirmation explicite** un choix `mode` (`none`, `linear`) et un motif qualifié `reason` (`manual_periodic`, `telemetry_failure`, `other`) attachés à l'empreinte de l'intervalle et horodatés. `save_panel_smoothing_choice` exige `confirm=true`, réévalue l'intervalle courant sous verrou et refuse un lissage non éligible. `history_smoothing_store.validate_choice` refuse tout autre motif à l'écriture **et à la lecture** du journal ; les décisions approuvées déjà présentes sont préservées à l'identique.

**`undetermined` / « Origine indéterminée » est exclusivement une valeur d'interface non qualifiante, jamais un `reason` envoyé à `trybatec/panel_smoothing_choice`.** Tant qu'aucune cause n'est déclarée, ne soumettre ni motif par défaut `manual_periodic` ni commande de sauvegarde. Si l'utilisateur sélectionne un motif connu, demander une confirmation avant persistance. Ne jamais convertir silencieusement `undetermined` en `manual_periodic` ; ne jamais écraser une ancienne décision approuvée lors de l'ouverture du formulaire. Si la cause reste inconnue, afficher l'état non qualifié et expliquer pourquoi un lissage exigeant un motif est bloqué.

## FR — Interfaces et responsabilité

Le contrat **read-only** `async_b15_recorder_handoff_36` (`history_36_recorder_handoff_v1`) reste inchangé : états de versions, empreintes, provenance `measured/estimated/mixed`, bornes, lacunes, métadonnées et lecture Recorder. **`admissible=false` et `activation_authorized=false`** demeurent inconditionnels. #37 vérifie l'inventaire physique complet et la continuité ; #88 vérifie la sélection unique des statistiques, les préférences Energy, sauvegarde, réconciliation et rollback. Aucune consommation brute n'a été déplacée ou remplacée.

## EN — Safety contract and remaining blockers

Selective requeue is **still denied**. Recorder's native synchronization only establishes a local queue-processing boundary, not a durable per-statistic no-late-writer fence. A pure recovery preview now exposes candidates solely as read-only preflight, with `safe_to_offer_retry=false` and empty authorized IDs. The production independent-fence hook always raises. If a genuinely independent fencing implementation becomes available and independently qualified, the importer must still re-read every pending statistic after acquiring it, then refuse any changed, partial or conflicting series.

REC-01..16 above identify existing or added **synthetic test sources**, not proven live behavior. Outstanding: isolated process crash/restart and durable database recovery (REC-01/06), global statistical bounds (REC-03/04), independent writer fencing (REC-05/07/16), physical lineage (#37), native exclusive Energy activation/rollback (#88). There is no authorization to merge, release, install, back up, restore or write to Home Assistant.

For UI C10, `undetermined` is an **unapproved draft sentinel**, not a persisted `reason`. Only explicitly confirmed `manual_periodic`, `telemetry_failure`, or `other` may be saved; `none` / `linear` are treatment methods, not reasons. Approved old choices must remain unchanged. The source index is never reclassified as a reconstructed measurement.

**Reference source / Référence technique :** [Home Assistant Recorder core](https://github.com/home-assistant/core/blob/dev/homeassistant/components/recorder/core.py), [statistics insertion](https://github.com/home-assistant/core/blob/dev/homeassistant/components/recorder/statistics.py); review against the exact HA version before any change to the safety gate.
