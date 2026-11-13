# 🤖 #36 — Recorder et contrat serveur #37/#88 / Recorder & server handoff

**Cible / Target:** `0.3.4b1` — PR #149 → draft candidate #147.  
**Responsable / Owner:** #36 ; interfaces avec / interfaces to #37 and #88.

## FR — Fonctions et garanties présentes dans la branche

1. Les index Trybatec authentiques restent distincts des lignes de consommation reconstituée ; le plan canonique est `make_b15_plan`. Les unités et empreintes de provenance découlent de l'historique qualifié, jamais d'une déclaration du navigateur.
2. Une importation b15 conserve le journal de versions dans `Store` **avant** toute mise en file Recorder. Aucun changement silencieux d'une Vn historique ; une nouvelle version possède son propre `statistic_id`.
3. `verify_b15_recorder` relit les fenêtres horaires UTC de 90 jours maximum, compare les sommes et horodatages attendus, refuse des lignes manquantes, en surplus ou incohérentes et valide les métadonnées natives : source, unité, classe d'unité, `has_sum`, `mean_type`. Seules les versions vérifiées franchissent la transition `imported → verified`.
4. `retry_pending` commence par une relecture ; une série déjà persistée n'est **jamais rejouée**. En cas de persistance incomplète, il attend le **commit Recorder natif** via `get_instance(hass).async_block_till_done()` sous le verrou serveur de l'import, puis relit. Une version totalement absente ne peut être remise en file qu'avec **une seconde attestation indépendante d'absence d'écrivain tardif**, en plus de la barrière Recorder et de la relecture. En Home Assistant 2026.11.1 cette attestation n'est **pas disponible** : le verrou `_independent_writer_quiescence_proof()` refuse donc toute reprise sélective sur production. Le journal prend en charge un compteur borné (trois intentions maximum) si un protocole fiable est ultérieurement qualifié ; il n'est pas un substitut à la preuve.
5. Toute lecture partielle, conflit, incapacité de synchronisation, absence d'autorisation explicite ou incohérence de journal interdit la reprise. L'entrée `retry_pending` demeure une action administrateur soumise aux confirmations et au plan source identique.

### Contrat de lecture pour #37/#88

`async_b15_recorder_handoff_36(hass, entry_id, plan)` dans `history_recorder_handoff_36.py`.

- **Entrée :** `plan` reconstruit **côté serveur** à partir des relevés vérifiés, des décisions approuvées et des unités confirmées ; `entry_id` du contexte autorisé ; aucune entrée du navigateur ne constitue une preuve.
- **Sortie :** `schema=history_36_recorder_handoff_v1`, `mode=native_server_read_only`, `plan_fingerprint`, `journal_pending`, `recorder_barrier_verified`, état de persistance par lot/fluide, `logical_id`, `statistic_id`, version Vn, variantes concurrentes, couverture et lacunes, quantités mesurées/estimées, provenance quotidienne, blocages motivés.
- **Preuve :** une version n'est reconnue comme persistée que si son empreinte source et son snapshot correspondent au journal, si sa portée/unité concordent et si Recorder restitue les buckets ainsi que les métadonnées de manière exacte à l'instant de lecture.
- **Non-autorité :** `admissible=false`, `activation_authorized=false`, `global_historical_lineage_attested=false`, `energy_exclusivity_attested=false`. #37 doit apporter un inventaire intergénérations exhaustif ; #88 doit apporter la preuve d'exclusivité de toutes les versions, des sources tierces, du support thermique et des transactions Energy/backup/rollback. Ne jamais déduire une permission d'écriture de ce contrat.

### Limites techniques à lever avant une recette qualifiante

- La barrière native garantit le traitement des tâches Recorder **précédant la barrière dans le processus courant**, mais `ImportStatisticsTask` peut se reprogrammer si son import échoue : un travail tardif peut subsister après la barrière. La barrière **ne prouve pas la quiescence** et le verrou Trybatec n'est pas un verrou global SQLite. Aucun rejeu sélectif n'est autorisé sans mécanisme de fencing durable supplémentaire.
- La relecture porte sur toutes les fenêtres **du snapshot attendu** ; une ligne étrangère située complètement en dehors de ces fenêtres n'est pas exclue par la comparaison actuelle. Une preuve native exhaustive de propriété et de bornes globales reste nécessaire pour une admission Énergie sans risque.
- Les tests de fixture simulent le commit-barrier ; ils ne remplacent pas une vraie validation du comportement Recorder 2026.11.1 et une restauration de SQLite sur une instance isolée. L'utilisateur ne dispose pas d'HA de test ; les pannes destructives restent exclusivement synthétiques.
- La sauvegarde et l'installation sur production, les écritures Recorder, les sélections Énergie et toute restauration sont des décisions **séparées**, non autorisées par la présente PR.
- Les tests REC-01..REC-16 doivent être requalifiés sur le SHA exact, et les items non prouvés rester **bloqués** ; aucune publication réduite de `0.3.4b1`.

## EN — Implementation and safety boundary

The canonical plan remains `make_b15_plan`; original meter indexes are immutable and distinct from estimated daily consumption. The durable version intent is saved before enqueuing any Recorder statistics. Native hourly readback compares every expected UTC timestamp and cumulative sum, rejects missing/extra/mismatched rows, and checks Recorder's own statistic metadata (source, unit, unit class, `has_sum`, mean type) before moving a version to verified.

`retry_pending` is server-side and approval-gated. It first re-reads existing rows; a fully persisted series is never requeued. If unresolved it waits for HA Recorder's native commit barrier and reads again. An additional independent no-late-writer proof is mandatory: HA 2026.11.1 does not offer such a stable proof, since failed `ImportStatisticsTask` jobs can reschedule after a barrier. Therefore **production selective requeue is deliberately denied**. A bounded retry intent counter is prepared for later proven implementations, not enabled by the barrier alone. Partial/conflicting data, failed synchronization or an inconsistent ledger are hard refusals.

The stable **read-only** `async_b15_recorder_handoff_36` contract exposes each dwelling/fluid's consolidated statistic, version, other version IDs, backend-qualified consumption provenance, coverage, unresolved gaps, journal state and native Recorder proof. Its admission and activation flags are always false: independent physical lineage is owned by #37 and Energy preferences, other sources, transactional backup and rollback by #88.

**Residual risks:** Recorder's barrier cannot prove the absence of tasks rescheduled after a failed import, unrelated future writers, or extra statistics *outside* audited time windows; fixtures do not simulate an actual live database restart. This is a technical evidence contract, not production or release authorization. No synthetic destructive fault tests may run against production.

## Recette production / Production-only acceptance

1. **Lecture seule d'abord / Read-only first:** relever versions HA, Trybatec, SHA, fluides, bornes, décisions, état du journal et diagnostics, sans publier de données réidentifiantes.
2. **Décisions distinctes / Separate approvals:** sauvegarde vérifiable puis installation, import ciblé, sélection Énergie et restauration éventuelle nécessitent chacune une autorisation spécifique de l'utilisateur et un plan de retour arrière. Refuser toute écriture si l'une manque.
3. **Prévisualiser / Preview:** vérifier les jours civils 23/25 h, les épisodes d'index nul, lissage résiduel, version Vn, diff et couverture réelle ; en cas d'ambiguïté, ne pas importer.
4. **Après autorisation d'import / Following import approval:** faire une seule écriture ciblée, contrôler journal puis synchronisation native et relire la persistance et les métadonnées. Ne pas valider sur le seul enqueue ; ne pas tenter un requeue en cas d'incertitude.
5. **Énergie / Energy:** seulement avec les attestations indépendantes #37/#88 et confirmation de transaction sauvegardée. Vérifier les sources tierces et l'absence de double sélection avant de conclure ; ne jamais pratiquer un test de corruption/restauration sur production.

**Références techniques / Technical sources :** [HA 2026.11.1 Recorder core](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/recorder/core.py), [statistiques Recorder](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/recorder/statistics.py), [service get_statistics](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/recorder/services.py). Liens fournis pour justification, non comme instructions opérationnelles / Links are evidence, not operational instructions.
