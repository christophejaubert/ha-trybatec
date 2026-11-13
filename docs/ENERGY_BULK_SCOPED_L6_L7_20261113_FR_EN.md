# 🤖 #88 — Admission L6 bornée / Scoped L6 admission and guarded L7

**Date / Date:** 2026-11-13  
**Propriétaire / Owner:** PR #158 ; convergence / integration #164 ; dépendances / dependencies #36, #37 ; MOE #45.  
**État / State:** development + isolated synthetic tests; **no production admission or Energy write authorization**.

## FR — Décisions du business owner

1. Une génération physique ou une tentative d'import reçoit un identifiant Recorder **distinct et jamais réutilisé**. La série importée et vérifiée est immuable par contrat ; les reprises douteuses sont mises en quarantaine dans des identifiants séparés, jamais réécrites ni automatiquement sélectionnées.
2. L'utilisateur compare les relevés affichés dans ha-trybatec au portail Trybatec et lui signale les incohérences. Le contrat n'atteste **pas** que Trybatec fournit l'exhaustivité historique de tous les compteurs.
3. Une période non attestée par l'API peut être retenue **après validation utilisateur ciblée**. Elle conserve sa provenance `portal_unattested_user_approved`, distincte des mesures `measured`. Cette approbation n'invente ni relevé fournisseur, ni date réelle de pose/dépose.
4. Le lissage linéaire `linear_user_approved` et la validation des plages demeurent sous la responsabilité de #36. L'utilisateur doit approuver **les jours, valeurs, compteurs et versions exacts** ; aucune approbation globale ne se substitue aux décisions individuelles.

L6 v1 exigeait une exhaustivité de compte non certifiable et un verrou global Recorder absent de HA 2026.11.1. Le nouveau contrat **v2 borné** ne rend pas ces exigences implicitement vraies : il les remplace par une preuve indépendante sur **les données effectivement sélectionnées**, un périmètre de dates, chaque génération choisie et un `statistic_id` unique. Les périodes hors sélection restent inconnues.

## FR — Séquence vérifiable

Le nouveau validateur pur est `custom_components/trybatec/energy_bulk_scoped_l6_88.py`, fonction `assess_scoped_selection_l6_88(selection, recorder_36, lineage_37, energy_audit)`.

`selection` décrit `account`, `lot`, `fluid`, `start`, `end` (jours inclus), `statistic_id`, `generation_ids` (générations réellement choisies) et `rows_hash`. Sa représentation canonique est liée par `selection_digest` aux attestations de **deux producteurs indépendants**. Un identifiant ne prouve pas seul son contenu.

| Contrat requis | Contrôles indispensables |
|---|---|
| `history_36_scoped_selection_v2` | Série `verified_immutable`, identifiant non réutilisé, journal sélectionné non en attente, aucune quarantaine de la version cible, persistance/buckets/métadonnées relus **après redémarrage** sur la bonne empreinte, catalogue borné des autres versions y compris mises en quarantaine, décisions utilisateur par jour + génération + version + valeur + révision, somme mesurée/estimée exacte |
| `lineage_37_scoped_selection_v2` | Unicité compte/lot/fluide/génération, identités actives/déposées sélectionnées, calendrier des contributions sans journée ambiguë, contrôle arithmétique et `provenance` propre à chaque contribution ; inconnues hors plage non certifiées, contrôle d'alternative et références statistiques propres au périmètre |
| `energy_audit` natif #88 | Relecture des préférences en mémoire **et** sur disque, même empreinte, inventaire des identifiants statistiques concurrents pour les séries sélectionnées, classement de **toutes** les références Énergie (sources principales et appareils) comme réellement disjointes de la sélection, refus de toute référence à la cible ou aux variantes en quarantaine, contrôle de version et relecture pré-/post-écriture |
| Sémantique Home Assistant | EF et ECS en `m³` → `water`, statistiques à somme et classe `water`. CET/chauffage en `kWh` avec classe `energy` **ne doit pas être présenté comme du gaz** ; source native chauffage non qualifiée = refus maintenu |

**Jours sans relevé :** le contrat peut accepter une journée sans ligne statistique seulement si elle figure exactement dans `selection.accepted_missing_days` et si **#36 et #37 produisent chacun** une attestation identique de décision utilisateur (`approved_absences`, jour, version, révision et `quantity=null`). Le logiciel **ne crée pas de ligne à 0** ni d'index fournisseur fictif. Le diagnostic compte ces jours dans `approved_missing_days_without_fabricated_rows`, indépendamment des contributions mesurées/estimées réellement enregistrées. Une journée manquante non approuvée, ou une tentative de transformer cette absence en consommation mesurée à zéro, reste un refus. La production de ces reçus natifs indépendants est encore à développer chez #36/#37.\n\n**Sécurité des approbations :** toute consommation non mesurée a une référence `approval_ref` propre au jour et à la génération, ainsi qu'au `statistic_id`, à la valeur exacte et à une révision de source. Les quantités estimées sont confrontées aux quantités enregistrées ; une approbation ne peut devenir `measured`. Si une période n'est pas attestée, l'utilisateur doit en assumer explicitement le choix ; cela ne remplace pas le contrôle des unités, versions et autres sources.

**Règle essentielle :** le diagnostic retourne `eligible_for_scoped_review` avec `writes=false` et `activation_authorized=false` lorsqu'un *jeu fictif* satisfait le schéma. Il ne signe pas une attestation ; aucun navigateur ni ancienne empreinte ne peut fournir le contenu qui sera utilisé pour activer une mutation. Les contrats v1 actuels ne délivrent **pas** les attestations v2. En leur absence, les refus restent actifs. Le branchement de lecture `l6_diagnostics` dans `energy_bulk_admin_service_88.py` ne change aucun de ces verrous.

### Limites du modèle positif

- Le protocole de versions immuables doit être réalisé et validé par **#36** : interdiction de rejouer/réécrire la même série, ID nouveau par tentative, quarantaine attestée et sélection après relecture persistée et redémarrage.
- Les certificats par jour et génération doivent être délivrés par **#37** avec contre-vérification des décisions dans le ledger propriétaire **#36**. Aucun booléen navigateur ne suffit.
- L'inventaire des sources Energie doit être réellement obtenu côté HA et vérifié contre les autres producteurs/séries actifs. L'absence d'une série dans les quelques fenêtres Recorder observées n'est pas un certificat de son inexistence.
- Le contrat actuel **ne prouve pas de verrou transactionnel global inter-intégrations** ; des écrivains externes peuvent changer les préférences entre la lecture et l'écriture. La relecture optimiste, le journal et le rollback conditionnel réduisent les dégâts mais ne démontrent pas une absence de course. `l7_external_writer_commit_guarantee_not_qualified` reste bloquant.
- La lisibilité d'une sauvegarde ne prouve pas qu'une restauration a réellement fonctionné ; qualification de restauration isolée distincte.

## FR — Machine transactionnelle L7 / chemins de résultat

La base `energy_bulk_transaction.py` dispose d'une transaction native conditionnelle via `HAGuardedEnergyPort`. Son plan est désormais lié par empreinte aux candidats **et aux attestations L6**, afin que toute modification de liste d'alternatives, décisions ou versions rende la confirmation périmée. Aucune empreinte n'est un jeton d'autorisation.

| Phase | Succès synthétique | Refus/incident |
|---|---|---|
| Administration & prévisualisation | Compte/lot authentifiés, plan exact, source unique | Compte étranger, non-admin, unité/provenance/empreinte fausse : aucune sauvegarde |
| Confirmation sous verrou Trybatec | Nouveau contrôle du plan et des préférences | Source remplacée, catalogue d'alternatives modifié, concurrence détectée : aucun commit |
| Sauvegarde | Sauvegarde native contrôlée (modèle simulé) | Échec/backup incomplet : aucune écriture |
| Journal `prepared` | Persisté et relu avant la mutation | Journal non durable : aucune écriture |
| Écriture additive | Sources antérieures **inchangées** | Modification extérieure ou demi-écriture : blocage |
| Relecture mémoire/disque | `verified` uniquement après cohérence totale et journal terminal durable | Échec avant écriture : `no_write_observed` ; état exactement proposé : rollback conditionnel `rolled_back_verified` ; état concurrent/partiel : `EnergyRecoveryRequired` |
| Crash/annulation | Si après `prepared`, le journal reste `prepared` | Aucune relance silencieuse : revue manuelle avant nouvelle transaction |

L7 est toujours **désactivé en production** par `NATIVE_ENERGY_BULK_WRITES_ENABLED_88 = False` (code serveur). Les deux routes administrateur sont enregistrées, mais `confirm` refuse avant toute sauvegarde. Ne pas transformer ce verrou en `True` : il faut d'abord installer et tester les producteurs natifs v2, qualifier la restauration, vérifier les écrivains concurrents et obtenir une décision explicite d'activation. L'activation ne découle ni du succès de la CI ni de la comparaison du portail par l'utilisateur.

### Contrat frontend et reprise

`trybatec/energy_bulk_88/preview` : `entry_id`, `lot` côté utilisateur administrateur authentifié ; renvoie `energy_bulk_admin_actions_88_v1`, `l6_diagnostics` EF/ECS/CET, le statut, les motifs et `transaction.journal_status`. Une future attestation v2 peut être affichée avec `eligible_for_scoped_review`, `approved_unattested_contributions`, `quarantined_alternative_versions` et `global_supplier_history_attested=false`. Le bouton de confirmation reste **désactivé** jusqu'à preuve indépendante et autorisation distincte. Aucune reprise automatisée ni écriture au chargement du panneau.

## EN — Bounded, non-forged admission

The business owner has chosen immutable per-generation/per-attempt Recorder statistic IDs, quarantine for uncertain versions, user responsibility to compare displayed source readings with Trybatec and report discrepancies, and optional user-approved **unattested** periods. Those periods remain labelled `portal_unattested_user_approved`, never `measured`. Existing #36 user-approved linear smoothing remains `linear_user_approved`, bound to exact days, amounts, physical generations, source revisions and immutable selected statistic IDs.

An approved day with no Recorder row can remain **genuinely absent**: `accepted_missing_days` must equal the exact gap set and independently bound #36/#37 `approved_absences` receipts must identify the day, selected statistic version and user revision, with `quantity=null`. No invented zeroes or supplier readings are written. The diagnostic exposes `approved_missing_days_without_fabricated_rows`; real native issuance of these receipts is still pending.
\nNew `energy_bulk_scoped_l6_88.py` implements a **pure, bounded, synthetic qualification model**, not an authorization service. It verifies selected account/lot/fluid/date bounds, physical generation IDs, canonical selection digests shared by independent #36/#37 producer envelopes, daily Recorder/lineage arithmetic, immutable selected version/readback after restart, known quarantined alternatives, source reference classification and preserved third-party Energy preferences. No all-account or all-time completeness assertion is demanded. Any absent in-scope proof is rejected. EF/ECS m³ can use native `water`; thermal CET kWh is not silently relabelled to `gas`.

**Current v1 #36 and #37 contracts cannot issue a real v2 admission.** Only those owners may build their native producers, not the #88 diagnostic and not the browser. Quarantined versions are never selected automatically, and any conflict across source categories blocks. A positive fictional diagnostic remains `activation_authorized=false`.

L7 simulation covers native admin, fresh plan fingerprints that now bind L6 evidence/candidates, backup, durable prewrite journal, additive write, live/persisted readback, conditional rollback, manual recovery of ambiguous concurrent or interrupted states, and no blind replay. **External-writer atomicity, real native restoration, native #36/#37 proof issuance, and supported heating semantics remain unproven**. The backend write gate remains hard-disabled and requires another reviewed, explicitly authorized implementation/acceptance phase. No production HA, Recorder or Energy operation, backup, restore, merge, release or installation is included.

## FR/EN — Tests et transferts / Tests and handoffs

- `tests/test_energy_bulk_scoped_l6_88.py` : sélection fictive positive et refus sur changement de plage, absence des producteurs, quarantaine, écriture non immuable, mauvaise unité, sommes Recorder, versions dupliquées, tiers non classés, références en conflit, divergence mémoire/disque, décision incorrecte, provenance falsifiée et CET.
- `tests/test_energy_bulk_transaction_l7.py` : plan invalide après modification du catalogue, annulations avant sauvegarde/après écriture, journal de reprise, préservation des autres sources (plus les tests antérieurs de rollback/idempotence).
- `energy_bulk_admin_service_88.py` : diagnostics bornés par fluide ; chemin v1 historique conserve ses refus ; chemin v2 reste bloqué par `l7_external_writer_commit_guarantee_not_qualified`, restauration et le verrou général.
- **#36 :** fournir le contrat natif v2 de version immuable persistée/relue, journal/quarantaine, dates et décisions avec révision.
- **#37 :** fournir le contrat natif v2 des générations et contributions **sélectionnées**, sans prétention d'exhaustivité globale.
- **#164 :** reprendre uniquement les blobs modifiés de la branche #158, jamais son historique #153/#147 ; vérifier la composition et toutes les CI au SHA résultant, en conservant la PR en brouillon.

**Documents sources / Sources:** [Home Assistant — Energy](https://www.home-assistant.io/docs/energy/), [Energy cards](https://www.home-assistant.io/dashboards/energy/), issues #36/#37/#88/#45 et PR #158/#164. Official Energy charts distinguish gas and water; they do not establish a native thermal category for CET. 


## FR — Collecteur HA réellement raccordé et inspection de reprise

**Modules développés dans #158 :** `energy_bulk_native_scopes_88.py` (lecture seule native), `energy_bulk_l7_recovery_inspection_88.py` (journal), raccordés par `HAGuardedEnergyPort.collect_native_scope_observations()` et `EnergyBulkAdminService88.preview()`. Ils ne sont pas des producteurs des certificats v2 réservés à #36 et #37.

Le collecteur authentifie l'administrateur dans `hass.auth`, vérifie la `config_entry`, le compte et le lot dans l'inventaire serveur, puis lit **sans migration ni écriture** les magasins B15, l'archive des compteurs déposés et les préférences Energy en mémoire et sur disque. Il confronte les identifiants des versions et générations physiques du compte, y compris la réutilisation d'un ID sur un autre lot, les versions en attente ou mises en quarantaine, les unités et les métadonnées Recorder natives. Les éléments non démontrables sont **énumérés comme des refus**, notamment la relecture intégrale des buckets d'une série immuable, les décisions signées par jour et la réservation d'un ID unique entre producteurs.

La commande admin `trybatec/energy_bulk_88/preview` accepte désormais, **facultativement**, une intention de sélection bornée :

```json
{
  "type": "trybatec/energy_bulk_88/preview",
  "entry_id": "synthetic-entry",
  "lot": "synthetic-lot",
  "selections": [{
    "fluid": "EF",
    "start": "2026-01-01",
    "end": "2026-01-31",
    "statistic_id": "trybatec:synthetic_ef_v1",
    "generation_ids": ["SYNTHETIC-GENERATION"]
  }]
}
```

Ces valeurs ne sont que des **choix**. Le serveur exige un `statistic_id` et des générations effectivement présents dans le journal chargé, une plage bornée (3660 jours maximum), une seule sélection par fluide et aucune propriété supplémentaire qui prétendrait à une preuve. L'aperçu renvoie `native_scoped_observations` avec les compteurs de versions, les sources concurrentes déjà sélectionnées, la validité des métadonnées, `selection_intent.native_ledger_ids_match` et `approval_and_daily_readback_verified=false`. Il n'expose pas les numéros de série de l'inventaire dans le statut compact. **Une correspondance d'identifiants n'est jamais assimilée à une admission positive L6** et ne peut pas produire une transaction.

Le même aperçu expose `transaction.recovery_inspection` : `none`, `terminal_journal_consistent`, `terminal_journal_diverged`, `prepared_no_write_observed`, `prepared_applied_without_terminal_audit`, `prepared_in_memory_only`, `prepared_disk_only`, `prepared_external_or_partial_divergence`, `journal_unreadable`, `journal_snapshot_or_fingerprint_invalid`, etc. La réponse est **sans contenu du journal ni identifiant privé de sauvegarde** et toujours `automatic_retry_allowed=false`, `automatic_rollback_allowed=false`. Toute divergence impose une revue administrateur, jamais une réparation déduite ou automatique.

**Ordre de transaction corrigé :** l'empreinte lie les candidats et toutes les preuves sélectionnées ; après confirmation administrateur, le plan est reconstruit, les préférences relues, une sauvegarde native identifiable est créée/vérifiée, **les preuves L6 sont collectées et confrontées une deuxième fois après cette sauvegarde**, puis les préférences sont relues avant journal `prepared`. Un changement de validation ou de version entre l'aperçu et la phase d'écriture provoque un refus **avant journal/écriture**, comme vérifié par les tests synthétiques. Les écritures additives, relectures et rollbacks conditionnels demeurent dans le moteur L7 existant, sans activation réelle.

**Contrainte native prouvée :** Home Assistant Core 2026.11.1, [`EnergyManager.async_update` dans `data.py`](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/energy/data.py#L844-L870), met à jour les préférences sans paramètre de comparaison atomique et programme l'écriture du Store. Le verrou L7 de Trybatec ne s'impose pas aux autres intégrations ni aux interfaces Énergie ; la détection avant/après et le rollback conditionnel ne sont pas une garantie native d'exclusivité inter-écrivains. **La confirmation reste désactivée** : aucune preuve de compare-and-swap global n'a été vérifiée. La solution sûre nécessite un protocole transactionnel commun/une API native d'écriture conditionnelle ou une isolation garantie de tous les écrivains pendant la transaction, et un exercice réel de restauration sur environnement isolé. Ne pas contourner ce refus.

**Schéma CET :** [`ENERGY_SOURCE_SCHEMA` HA 2026.11.1](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/energy/data.py#L642-L663) accepte `grid`, `solar`, `home`, `battery`, `gas` et `water`, **pas `heat`**. Un CET thermique en kWh ne doit donc pas être inscrit comme une consommation de gaz par commodité. Le parcours EF/ECS `water`/m³ est préparé pour recette réelle après publication et installation distinctement autorisées. Les blocages de la catégorie chauffage ne sont pas une obligation de preuve de recette réelle avant publication, mais empêchent l'écriture dans une catégorie sémantiquement fausse.

## EN — Native read-only scope evidence and durable recovery inspection

#88 now includes an authentic HA read-only ledger/retired-generation/Recorder-metadata/live-and-persisted Energy collector. Native authentication, account/lot membership, bounded user *selection intent*, cross-lot statistic ID collisions, duplicate versions, pending and quarantined attempts and expected units are checked. These observations are **facts**, not fake immutable-version, user-approval or independent #36/#37 v2 certificates. Selected source IDs are never accepted from the browser as proof.

A read-only L7 recovery inspector classifies pending and terminal journal against live/persisted fingerprints. It distinguishes no write, in-memory-only, disk-only, applied-but-unaudited and third-party-divergent states without leaking snapshots or backup identifiers or automatically rolling back. L7 now recollects independent L6 proof **after** native backup and aborts if the candidate/version/approval changed before staging.

HA Core 2026.11.1 EnergyManager's `async_update` is not a compare-and-swap transaction; Trybatec's lock cannot fence all other HA Energy writers. No native cross-writer atomicity or actual backup restoration has been proved. Registered admin confirmation stays backend hard-disabled and production writes remain unavailable. The Core Energy schema has `water` and `gas`, but no thermal `heat` source; CET kWh must not be mislabelled as gas. Isolated synthetic tests are not live HA acceptance.
