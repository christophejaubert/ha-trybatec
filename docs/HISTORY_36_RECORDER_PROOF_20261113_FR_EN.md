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


---

## FR — Audit source Recorder 2026.11.1 et verdict renforcé (13 novembre 2026)

**Verdict précis : preuve indépendante durable impossible à démontrer avec les API actuellement exposées.** Les garanties **partiellement obtenues** concernent la sérialisation Trybatec locale, les instantanés versionnés et les relectures natives ; aucune ne verrouille le moteur Recorder ni les producteurs d'écritures tiers. « Impossible à démontrer » décrit le périmètre des API examinées, pas une impossibilité théorique si Home Assistant introduisait un contrat de fencing atomique, durable et reconnu par tous les writers.

### Chaîne source examinée (tag exact, pas `dev`)

| Référence HA 2026.11.1 | Comportement vérifiable | Conséquence |
|---|---|---|
| [`statistics.py`](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/recorder/statistics.py#L2873-L2907) | `async_add_external_statistics` met l'import dans la file ; réponse d'appel ≠ commit | Ne jamais assimiler enqueue et durabilité |
| [`core.py`](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/recorder/core.py#L1366-L1385) | `async_get_commit_future` retourne parfois `None` sur conditions de file et de session ; sinon soumet `SynchronizeTask` | Ne fournit aucune identité durable de writer, ni exclusion des tâches en vol |
| [`tasks.py`](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/recorder/tasks.py#L204-L222) | `ImportStatisticsTask.run` remet la tâche en queue si `import_statistics` retourne `False` | Un retry peut se trouver **après** un `SynchronizeTask` déjà ordonné |
| [`util.py`](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/recorder/util.py#L795-L848) | Le décorateur renvoie `False` pour certaines erreurs SQL transitoires | Chaîne du réenfilage confirmée dans le code cible |
| [`statistics.py`](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/recorder/statistics.py#L2910-L2945) | Une ligne `(metadata_id,start_ts)` existante peut être **mise à jour** | Une écriture tardive peut altérer les sommes déjà relues |
| [`core.py`](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/recorder/core.py#L467-L483) | La fermeture vide la file avant l'arrêt | Une interruption n'atteste pas qu'un batch a été importé ni qu'un producteur extérieur ne reprendra pas |

**Contre-exemple de file FIFO :** `Import(A)` (échec SQL transitoire) → `Synchronize` → `Import(A)` (nouvelle tentative insérée en queue). Après échec d'`Import(A)`, Recorder ajoute `Import(A)` en queue **derrière** `Synchronize`. La synchronisation se termine tandis que la nouvelle tentative peut encore écrire. Cela réfute la déduction « barrière terminée ⇒ aucun ancien writer ne peut publier ». Autre contre-exemple : la file peut être vide alors qu'une opération est déjà retirée de la file et exécutée, et `async_get_commit_future` peut emprunter son chemin de retour immédiat. Aucune de ces situations n'est détectable via un jeton public de génération par `statistic_id`.

### Portée réelle des verrous

- **Verrou `_history_import_lock`** : sérialise uniquement les appels coopérants pour **une entrée de configuration et un processus**. Ne verrouille ni plusieurs entrées partageant potentiellement un `statistic_id`, ni les appels websocket/API Recorder, ni les écritures d'autres intégrations, ni le travail déjà en cours dans le thread Recorder.
- **Store du journal B15** : enregistre intention, empreinte, sources physiques, unité, version, nombre de tentatives. Ce n'est pas un commit log transactionnel partagé avec Recorder ; crash entre `Store.async_save` et `async_add_external_statistics` laisse un état ambigu sans droit de rejeu.
- **Barrière native** : fournit une observation utile et éventuellement le traitement des tâches placées avant elle, pas une preuve d'exclusivité ou d'absence de tâches réenfilées après elle.
- **Relecture serveur** : compare sommes/heures et métadonnées au **moment de la lecture**. Elle ne prouve ni l'absence de writers futurs ni l'absence d'autres lignes situées entièrement hors des fenêtres lues.
- **Versionnement** : les `statistic_id` V1/V2/V3 distincts réduisent les collisions entre *versions coopérantes* ; ils ne garantissent pas qu'un autre producteur ne réécrira pas un même ID.

### Scénarios négatifs, état réel des preuves

| Scénario | Test source synthétique | Conclusion utilisable |
|---|---|---|
| Import réenfilé derrière Synchronize | `test_recorder_barrier_counterexamples_36.py` | Barrière non suffisante ; modèle FIFO, **pas test natif HA** |
| File vide, tâche déjà en vol | Idem | Le retour immédiat du chemin natif ne prouve pas zéro writer |
| Batch A persisté, B différé | Idem et `test_b15_selective_retry_36.py` | A jamais rejoué ; B refusé sans attestation indépendante |
| Arrêt/annulation du demandeur | Modèle FIFO | L'annulation de l'appelant n'est pas une révocation Recorder |
| Crash entre journal et mise en queue | `test_b15_recovery_crash_l2.py` + modèle | Journal conservé, état ambigu, aucun rejeu automatique |
| « Preuve » fictive, B devient persisté | `test_late_commit_during_independent_fence_is_not_requeued` | Seconde relecture ⇒ idempotence simulée, aucune réémission |
| « Preuve » fictive, B devient partiel | `test_partial_write_appears_after_synthetic_fence_and_blocks_retry` | Refus de toutes nouvelles émissions ; journal conservé |
| Plusieurs compteurs, aucune donnée, barrière réussie | `test_multi_statistic_empty_readback_native_barrier_is_not_a_fence` | Hook de production refuse toujours le rejeu |
| Écriture extérieure, même ID | Modèle FIFO + code natif d'UPDATE | Verrou local sans effet sur producteur extérieur |
| Redémarrage complet HA / SQLite | **Non testé** ; seulement recréation du Store et modèle | Aucune preuve de sécurité du redémarrage exploitable |

### Alternatives sûres, non activées

1. **Immédiatement utilisable en lecture seule :** conserver `pending`, relire les versions et métadonnées exactes, vérifier les empreintes, marquer séparément `verified` les séries effectivement persistées. Ne pas rejouer les absentes/partielles.
2. **Écarter une version ambiguë au profit d'un nouvel ID entièrement distinct** n'est *qu'une piste d'architecture* : elle requiert une procédure explicite d'abandon/quarantaine, un audit des références et des sources concurrentes, un journal d'opération durable et une approbation utilisateur distincte. Ne jamais masquer une ancienne version susceptible d'écrire tardivement ni forcer le changement Énergie. **Aucune implémentation ni activation ici.**
3. **Pour démontrer un vrai fencing** : requérir une interface native/contractuelle HA atomique entre enfileur et worker, un token générationnel durable par `statistic_id` consulté **au moment du commit**, le rejet de tout ancien token, un contrôle de tous les producteurs concurrents et des tests d'arrêt/redémarrage/DB sous différents backends. La simple lecture de la file, une durée d'attente, un verrou Python ou une base SQLite temporaire ne remplissent pas cette obligation.

### Handoff obligatoire à #37, #88 et #164

- **#37** : le contrat `history_36_recorder_handoff_v1` donne empreintes, portée physique, dates et provenance mesurée/estimée/mixte ; `qualified_bounds_no_gaps` n'établit pas une exhaustivité fournisseur ni intergénérations. La preuve de filiation indépendante doit rester séparée.
- **#88** : `recorder_barrier_verified=true` ou `recorder_persistence_verified=true` **ne signifie pas** `recorder_writer_fence_verified=true`. Il faut conserver l'exclusion des versions concurrentes, des autres sources Energy, le contrôle des unités (EF/ECS m³, CET kWh), la sauvegarde et une transaction Energy indépendante avant la moindre activation. Aucun booléen d'admissibilité ne peut être inféré du seul handoff #36.
- **#164** : les modules Recorder de #159 étaient déjà repris à l'identique sur la convergence au SHA `59ca822cbe8590151d32fc1db9061d4a79d19870`. Intégrer **uniquement le delta ultérieur** après vérification des SHA, sans reprendre les commits déjà copiés ni supprimer les verrous. Aucun changement de #164 n'est effectué ici.

**Statut REC-01..16 :** REC-05/07/16 demeurent bloquants pour la reprise sélective ; REC-01/06 exigent une panne/reprise sur HA totalement isolé ; REC-03/04 une interrogation exhaustive de Recorder hors fenêtres ; REC-10/11/13 dépendent de l'exclusivité Energy #88 ; REC-14 de la filiation #37 ; REC-15 du comportement exact du schéma natif cible. Tous les autres tests établissent des propriétés **synthétiques limitées**, aucune garantie de production.

## EN — Exact upstream Recorder analysis and unlifted fence

**Verdict: an independent durable absence-of-late-writers proof cannot be established using the exposed HA 2026.11.1 APIs.** The partial guarantees are limited to Trybatec's entry-local mutex, durable version intent, bounded server readback and a double readback in a *hypothetical* independently fenced path. Home Assistant's `ImportStatisticsTask` requeues after a retryable SQL error; a `SynchronizeTask` may complete before that requeued writer. `async_get_commit_future` can also return immediately based on a queue-empty/event-session condition which does not attest currently executing imports. Existing statistics sharing the same start time can be updated by a later write. None of these paths exposes a durable generation token or excludes non-cooperating writers.

The source-derived FIFO counterexample suite is a **model, not a live HA Recorder test**. Newly added isolated HA fixture tests cover late partial writes after a fictitious fence and refusal after native barrier success alone. Tests do not assert native durability after process crash, cross-process fencing or safety of production retries.

**Contract for #37/#88/#164:** retain `safe_to_offer_retry=false`, `retry_only_these_statistic_ids=[]`, `independent_writer_fence_verified=false`, `admissible=false`, `activation_authorized=false`. Existing per-window readback, source fingerprints, units, versions and measured/estimated provenance are necessary evidence, not writer exclusivity or Energy write permission. Alternative quarantine/new-ID approaches are future design candidates only, requiring explicit approvals and independent audits; none is active. No real Recorder access, HA mutation, merge, release or restoration is authorized.
