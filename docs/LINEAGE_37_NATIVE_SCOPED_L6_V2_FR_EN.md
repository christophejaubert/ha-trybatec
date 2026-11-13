# 🤖 #37 → #88 — Contrat v2 de filiation physique bornée / Scoped native lineage v2

**Dépôt / Repository:** `christophejaubert/ha-trybatec`. **Propriétaire / Owner:** PR #160, issue #37. **Consommateur / Consumer:** PR #158, `assess_scoped_selection_l6_88`. **Dépendance de preuve / Independent evidence:** #36 PR #159. **Convergence / Integration:** PR #164. No private site identifiers, production indexes or HA credentials in this document.

## FR — Portée et séparation des responsabilités

Le nouveau module `custom_components/trybatec/lineage_native_scoped_37.py` expose `generation_id_37` et `prepare_native_scoped_lineage_37`.

- **#37 source physique :** sélection limitée à `account/lot/fluid/serials/start/end`, avec `statistic_id`, `generation_ids` calculés à partir des séries **physiques** (jamais des suffixes `_2` de HA), `rows_hash`, `physical_snapshot_digest` et `accepted_missing_days`. Le snapshot doit correspondre au `selected_snapshot_37` du même compte, logement, fluide, bornes et variantes. Toute sélection périmée est rejetée.
- **Index API d'origine :** le raccordement reçoit, depuis le backend, les réponses `/indexes` déjà collectées, **en plus** de `history["__physical_meters__"]`. Il reconstitue les paires originales par compteur, vérifie leurs horodatages, valeurs et conflits, puis compare les deltas des paires consécutives de chaque compteur au journal physique de consommation. Aucun index de deux compteurs différents n'est soustrait. Les index d'origine ne sont ni réécrits ni transmis dans l'enveloppe L6 ; celle-ci transporte une **empreinte de paire** et la quantité calculée.
- **Corrections de revue :** `reviewed_readings` peut différer du fournisseur. Une paire non identique à la réponse d'origine **ne devient pas** une observation API attestée. Les intervalles longs restent des inconnues ; seuls les jours effectivement approuvés et attribués à une révision #36 peuvent porter une estimation. Une estimation ne peut pas contredire un delta brut journalier déjà attesté.
- **Périodes et générations :** une génération `depose` garde le statut `retired` et la provenance de ses index, sans devenir un capteur actif. `service_start/end=None` reste inconnu. Une inconnue **hors fenêtre sélectionnée** ne constitue pas un refus global. Les recouvrements, contributions dupliquées, delta négatif, jour étranger ou source non qualifiée **dans la fenêtre** entraînent un refus.
- **#36 décisions et Recorder :** le producteur #37 vérifie la concordance des références par **date, génération physique, série statistique, révision, source et montant**, contre les reçus du **producteur natif #36**, puis exige une relecture indépendante de ce registre par l'adaptateur de confiance. Les éventuels jours exclus comportent dans #36 un reçu `no_statistical_row=true`, `quantity=null` et une révision correspondante ; ils restent **absents**, sans zéro artificiel.
- **Version :** même `statistic_id` que la sélection, même `selection_digest` (hash du dictionnaire de sélection), version Recorder immuable et relue, empreinte de lignes persistées (`rows_hash`), statut pending/quarantine non actif, inventaire de versions et unicité de l'identifiant dans son périmètre. L'audit de toutes les références Energy concurrentes et le véritable verrou de sérialisation Recorder relèvent de #88/#36 respectivement.

### Adaptateur HA serveur natif et frontières de confiance

`async_collect_server_scoped_lineage_37(hass, coordinator, actor_id, selection, preview_37, read_native_recorder_36, ...)` est un **point d'intégration backend non enregistré en WebSocket/service**. Il relit l'utilisateur par `hass.auth.async_get_user` et exige ses droits administrateur, impose la correspondance avec `coordinator.entry.unique_id`, obtient un cache C11 toujours valide pour l'intervalle, relit en lecture seule les choix de revue historiques #36 et reconstruit par `build_history` les index du même compte/lot et la provenance physique. Il n'ouvre aucune nouvelle requête fournisseur et n'appelle aucune méthode d'écriture.

Les preuves `native_recorder_36`, `verify_user_selection`, `verify_36_day`, `verify_36_absence` sont fournies **uniquement par les propriétaires backend de confiance** : leur implémentation de production reste une dépendance #36/#88. Sans `read_native_recorder_36`, le résultat indique `selected_scope_reconciled=false`. Un callback de test peut démontrer le contrat sur un jeu fictif, mais ne fournit aucune attestation de persistance réelle. Le raccordement à C11 #162 doit être composé dans #164 ; le module #160 n'enregistre pas un nouveau flux HA.

**EN — Native read-only server adapter:** The adapter authenticates the HA administrator from the server auth store, matches the configured account, reads a still-valid account-scoped C11 cache and existing historical review decisions, rebuilds source physical indexes without any supplier scan, then delegates to independent #36/user verifiers. The #36 owner now supplies a scoped v2 native observation reader. #160 automatically uses it when present, but its explicit false restart/writer-fence/version flags keep admission blocked. This integration point is not registered as a WebSocket/service and cannot execute any Recorder, Energy or HA mutation.

### Entrée v2 de sélection du backend (forme illustrative fictive)

```python
{
    "account": "FICTIONAL-ACCOUNT", "lot": "FICTIONAL-LOT", "fluid": "EF",
    "start": "2026-01-02", "end": "2026-01-03",
    "statistic_id": "trybatec:fictional_v03",
    "serials": ["FICTIONAL-OLD", "FICTIONAL-NEW"],
    "generation_ids": ["trybatec:physical_<digest-old>", "trybatec:physical_<digest-new>"],
    "rows_hash": "<hash of native persisted rows>",
    "physical_snapshot_digest": "<#37 trusted source snapshot hash>",
    "accepted_missing_days": [],
}
```

Les empreintes entre chevrons sont des **emplacements descriptifs**, pas des valeurs et ne doivent pas être utilisées comme attestations.

### Identifiants natifs #88 et sélection enrichie côté serveur

`energy_bulk_native_scopes_88._selected_intents` accepte uniquement un **intent** limité à `fluid/start/end/statistic_id/generation_ids` ; son journal B15 utilise actuellement les **séries physiques fournisseur** comme `generation_ids`. Le producteur #37 accepte donc soit la liste exacte de ces séries, soit la liste de digests physiques dérivés, **mais jamais un suffixe technique HA fabriqué ni une liste mixte**. Il conserve séparément `physical_identity_digest` calculé à partir du compte/lot/fluide/numéro fournisseur. Les deux produits doivent provenir du même inventaire backend validé.

Le backend #88 doit **enrichir son intent depuis ses sources de confiance** avec `account`, `lot`, `serials`, `rows_hash`, `physical_snapshot_digest` et `accepted_missing_days` avant de l'envoyer au validateur L6 scoped. Il ne doit ni demander ces preuves comme indicateurs de sécurité au navigateur, ni réemployer une sélection de compteurs provenant de l'interface après changement d'empreinte. Les tests #37 comportent les deux représentations cohérentes, ainsi que le refus d'un faux `NEW_2`.

**EN — Exact native selection identity mapping:** #88's observed native B15 ledger currently uses physical supplier serials as generation IDs. #37 v2 accepts an exact full list of those scoped serials or its own exact opaque physical digests, never an HA technical suffix or mixed/foreign IDs. The #88 *intent* is deliberately minimal; trusted backend evidence must enrich it with account, selected source fingerprint, actual Recorder row hash and accepted missing dates before L6 validation. A browser cannot authorize these attestations.

### Sortie native v2 à remettre à #88

```
schema = "lineage_37_scoped_selection_v2"
mode = "native_selected_generations"
account, lot, fluid, start, end, statistic_id = selection correspondante
selection_digest = SHA256 du même dictionnaire de sélection
unit = "m³" (EF/ECS), "kWh" (CET)
selected_generation_ids = exactement selection.generation_ids
selected_scope_reconciled = true UNIQUEMENT si chaque contrôle réussit
version_catalog_reconciled = true UNIQUEMENT si l'inventaire sélectionné est cohérent
competing_version_conflict = false UNIQUEMENT sans contradiction
generations = [
  {generation_id, unit, identity_verified, supplier_observation_attested,
   status: active|retired, physical_source_fingerprint, service_start, service_end}
]
daily = [
  {date, total, contributors: [
      {generation_id, amount, provenance: measured,
       source_observation_verified: true, reading_pair_hash}
      OU
      {generation_id, amount, provenance: linear_user_approved
       | portal_unattested_user_approved, approval_ref, revision_hash}
  ]}
]
approved_absences = copies des reçus exacts #36 vérifiés, sans statistiques
selected_total = somme des deltas par jour / par compteur sélectionné
source_api_attestation = "not_attested_by_trybatec_api"
historical_global_exhaustiveness = false
raw_physical_indexes_modified = false
blockers = motifs exacts et triés
energy_activation_authorized = false
writes = false
```

`selected_scope_reconciled` est une **qualification locale conditionnelle**. Les trois lecteurs de confiance (`verify_user_selection`, `verify_36_day`, `verify_36_absence`) sont des *interfaces d'injection*, et **ne sont pas raccordés à des sources persistées de production dans cette PR**. Ils doivent être fournis par un endpoint backend administrateur authentifié, jamais par des booléens de navigateur. Mise à jour du HEAD #159 `91ef18462d8cebf0db11611e33d67943ff3d98d1` : `async_read_native_scoped_selection_v2_36` produit désormais une **observation native v2**, mais en mode `native_scoped_readback_no_future_writer_fence` et non `native_immutable_readback`. Les garanties post-redémarrage, unicité/exclusivité et catalogue complet restent explicitement fausses. #37 la lit directement lorsque ce module est intégré, sans lever `selected_scope_reconciled`. En l'absence de #36 sur sa branche propriétaire, #37 refuse sans tenter de fabriquer la preuve.

### Matrice de refus du producteur #37

| Catégorie | Motifs représentatifs | Sort |
| --- | --- | --- |
| Identité/source | `selected_physical_source_missing`, `physical_source_fingerprint_mismatch`, `supplier_raw_index_response_conflicted_or_unavailable` | Refus |
| Index réellement fournisseur | `measured_day_without_supplier_raw_pair`, `measured_day_raw_index_delta_mismatch`, `decreasing_index_within_selected_generation` | Refus |
| Générations et calendrier | `concurrent_physical_generations_not_apportioned`, `foreign_physical_generation_contribution`, `unapproved_or_misattributed_missing_days` | Refus |
| Estimation | `estimated_day_revision_not_individually_attributed`, `native_36_exact_day_revision_receipt_mismatch`, `native_36_independent_day_approval_missing`, `estimated_day_overlaps_unaltered_raw_measurement` | Refus |
| Recorder | `native_36_selected_revision_and_scope_unavailable`, `native_36_daily_measured_estimated_mismatch`, `native_36_recorder_rows_hash_not_matched`, `selected_recorder_revision_not_immutable` | Refus |
| Consentement utilisateur | `selected_administrator_decision_not_authenticated` | Refus |
| Lacune acceptée | Correspondance exacte des `approved_absences` du v2 #36, `no_statistical_row=true` et `quantity=null` | Aucune ligne fictive ; candidature seulement si autres preuves positives |
| Hors sélection | Ancien compteur sans index avant la fenêtre ou après celle-ci | **Pas de refus global de ce seul motif** |

**Limites temporaires explicites :** pour un même compteur un jour `mixed` associant du mesuré et de l'estimé reste **refusé** (`mixed_physical_day_not_representable_in_l6_v2`). Le v2 #88 actuel n'autorise qu'un enregistrement par génération/jour avec une provenance unique ; il doit être enrichi pour les contributions mixtes sans double comptage ni perte de mesure. Un jour avec deux générations simultanées reste refusé tant qu'une preuve de ventilation indépendante n'existe pas. Les unités doivent être validées, et le chauffage CET en kWh reste un critère de recette Home Assistant après publication, sans affirmer une compatibilité Energy native inexistante.

### Admission et opérations : frontières

Même un exemple synthétique « v2 positif » ne peut pas prouver la réalité de la source, des approbations, de Recorder ou d'Energy. #88 valide séparément **son propre** `assess_scoped_selection_l6_88`, inventorie les sources tierces et versions concurrentes, puis contrôle L7, sauvegarde et restauration, et la sécurité des écrivains. Le verrou effectif `NATIVE_ENERGY_BULK_WRITES_ENABLED_88=False` reste **inchangé**. La réussite des tests n'installe ni ne modifie Home Assistant.

## EN — Exact independent evidence boundary

#37 now provides a v2 envelope matching the exact consumer fields of `assess_scoped_selection_l6_88`. Physical generation identity is derived from account/lot/fluid/**supplier physical serial**, not Home Assistant's technical entity suffixes. Raw supplier `/indexes` payloads and independently built history are compared at the individual index-pair level: a manually corrected value is NOT silently promoted to a vendor measurement. Deltas are computed **only within one physical meter**; later generations contribute separately computed consumption, never a subtraction of different meter indexes. Selected windows, source snapshots, Recorder statistic IDs/versions and calendar-day user approval references are strictly matched.

An approved missing day remains absent with a separately verified `quantity=null` receipt, **not** an invented zero. All-time supplier meter-population completeness is **not** required. Unknown replacement dates and retired generations are retained. Actual conflicting or unknown evidence **inside the selection** is refused; unrelated unknown history outside it is not globally vetoed. The producer refuses stale source snapshots, bad readback, foreign sources, reused days, wrong revision/quantity and potential double counting.

Native #36 scoped v2 readback and durable day-revision approval collectors and authenticated administrator-choice retrieval are **not implemented by #37**; their absence keeps the producer fail-closed. A v2 synthetic positive proves the contract's arithmetic/shape, not production authority. The current #88 contract cannot yet represent mixed measured+estimated amounts for the same generation/day; that case remains blocked pending a separate #88 contract enhancement. #81 remains read-only, and all merge, release, migration, deletion, Recorder/Energy writes and HA operations remain outside this mandate.


---

## FR — Raccordement réel aux tentatives Recorder #36 (complément du 13 novembre 2026)

La tête de #159 produit la preuve native
`history_36_native_attempt_proof_v1` via
`async_native_attempt_proof_36` **et**, depuis le SHA `91ef1846`,
une observation `history_36_scoped_selection_v2` via
`async_read_native_scoped_selection_v2_36`. La seconde est authentique mais
explicitement **non immuable**. Sa lecture SQL double, les
métadonnées Recorder, le journal durable et les références de décisions sont
des observations utiles, mais ne valent pas garantie d'exclusion des écrivains
tardifs, de relance après redémarrage, d'inventaire complet des versions
sélectionnées ni d'exclusivité Énergie.

`lineage_native_scoped_37.audit_native_attempt_link_37(selection, selected_physical_days, proof_36)`
effectue désormais un recoupement distinct et **non autorisant** :

- même lot, fluide, ID statistique, unité, génération de tentative et révision
  exacte intégrées à l'identifiant natif ;
- même empreinte du snapshot Recorder et mêmes journées et contributions
  par compteur physique, sans soustraire leurs index respectifs ;
- conservation des étiquettes mesurée/estimée, des références journalières et
  de leurs empreintes de révision ; une contradiction est refusée ;
- les absences explicitement sélectionnées ne sont jamais transformées en zéro.

Le producteur `prepare_native_scoped_lineage_37` expose ce diagnostic
dans `native_36_attempt_link` lorsque le schéma v1 est reçu.
Il maintient **toujours** `selected_scope_reconciled=false`
sur cette voie et ne produit aucun document de remplacement v2. Les causes
de refus incluent `native_36_scoped_selection_v2_not_issued`,
`native_attempt_future_writer_exclusion_unverified` et, selon
les observations, les conflits de jours, de séries ou de révisions.

Le chemin v2 déjà défini reste utilisable avec un **authentique producteur
backend #36** fournissant des lectures et décisions de la même révision.
La preuve documentaire #37, la preuve native Recorder #36 et
l'admissibilité L6 Énergie #88 sont trois résultats distincts. Les simples
drapeaux issus d'un test synthétique n'autorisent jamais une écriture HA.

La filiation refuse aussi les reçus d'approbation ou d'absence étrangers,
les versions dupliquées ou simultanément déclarées vérifiées et les journées
hors bornes de service connues. Une date de remplacement inconnue reste
inconnue ; aucune migration #81 ni intervention sur les entités HA n'est faite.

**Reste à fournir par #159/#158/#164 :** producteur natif v2 authentifié,
contrôle de révisions post-redémarrage et des écrivains concurrents,
inventaire des versions, relecture indépendante des décisions et audit Énergie
au moment de L6/L7. Aucun résultat positif de tests fictifs n'équivaut à
une recette de l'installation réelle.

## EN — Actual #36 native attempt interoperability (13 November 2026)

PR #159 now emits both `history_36_native_attempt_proof_v1` and
`history_36_scoped_selection_v2` in the explicitly non-authorizing
`native_scoped_readback_no_future_writer_fence` mode.
The new pure `audit_native_attempt_link_37` checks
the selected scope, exact versioned statistic ID, persisted snapshot
fingerprint, daily per-physical-meter amounts, provenance and approval revision
references. It reports mismatches and never subtracts indexes from separate
physical meters. Approved absences remain absent.

When a native v1 proof is supplied, the #37 producer places its diagnostics
under `native_36_attempt_link` and **keeps L6 blocked**.
A genuine independently authenticated v2 producer, post-restart readback,
complete scoped version inventory, future-writer protection and Energy
exclusivity are still dependencies. Unknown replacement dates are retained,
while contradictory dates, extra approvals, competing verified versions and
out-of-service contributions are rejected. #81 identity migration, Home
Assistant changes, merge and release remain outside this PR.

**Synthetic coverage:** `tests/test_lineage_native_recorder_link_37.py`
and `tests/test_lineage_native_scoped_37.py` cover positive
physical arithmetic, successive generations, unknown/contradictory dates,
missing approved days, mismatched revisions, duplicates and competing versions.
Only the v2 #36/#37/#88 chain can be an actual L6 candidate after the
independent native producers have been implemented and verified.


### FR — Adaptation au nouveau lecteur natif #159 v2

Dans `async_collect_server_scoped_lineage_37`, l'absence de
lecteur injecté déclenche la découverte locale du lecteur serveur
`async_read_native_scoped_selection_v2_36` de #159, uniquement
lorsque le module #36 existe. La sélection est d'abord contrôlée contre
l'administrateur HA, le compte configuré, le lot et les sources C11.
Le résultat restitue `native_36_scoped_observation` en
distinguant l'observation SQL réelle d'une preuve de persistance après
redémarrage et de l'exclusion d'écrivains concurrents. Les indicateurs v2
négatifs de #159 restent négatifs ; une preuve observée n'est jamais promue
en révision `verified_immutable`.

### EN — Latest native #159 v2 reader

The #37 server adapter now auto-discovers #159's scoped v2 reader
when both branches are integrated. It authenticates the HA administrator
and configured account before reading the source. The result reports the
native SQL observation separately from post-restart and concurrent-writer
protection. No native v2 observation is upgraded into an immutable L6 proof.
