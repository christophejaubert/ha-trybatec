# 🤖 #88 — Contrat de service administratif Énergie / Native admin service contract

**Base / Base:** `0.3.4b1` + convergence #153, sans fusion.  
**Code / Code:** `custom_components/trybatec/energy_bulk_admin_service_88.py`.  
**Essais / Tests:** `tests/test_energy_bulk_admin_service_88.py`, `tests/test_energy_bulk_transaction_l7.py`, `tests/test_energy_bulk_native_port_l7.py`.  
**Propriétaires / Owners:** backend #88; frontend #155 only.

## FR — Fonctionnement et sécurité

- **Service natif dormant :** `EnergyBulkAdminService88.preview(actor)` et `confirm(actor, before_fingerprint, plan_digest, confirm)`. Aucun endpoint WebSocket, enregistrement de service, automatisation, tâche au démarrage ou bouton n'est ajouté. L'activation exige une décision et une intégration séparées.
- **Authentification :** le port natif consulte `hass.auth.async_get_user`, exige un administrateur réel et fixe le compte à `coordinator.entry.unique_id`. Le frontend ne fournit jamais de listes de compteurs, de preuve ni d'indicateurs de complétude.
- **Prévisualisation :** lecture sans effet, plan L7 reconstitué côté serveur, statuts EF/ECS/CET, raisons de refus, empreintes, champs requis et navigation de repli vers l'assistant. Un aperçu valide ne constitue jamais une autorisation en soi.
- **Admission L6 :** indispensable : inventaire historique exhaustif et contradictoire résolu, preuve Recorder #36 de persistance et d'absence de writer tardif, filiation #37 des compteurs installés et déposés avec provenance par jour, sélection d'une seule consolidation et inventaire des séries alternatives. Les contrats actuellement publiés dans la convergence restent explicitement **non habilitants** ; aucun candidat réel n'est encore admis.
- **Conflits :** contrôle des index physiques distincts, dupliqués, unités inconnues, métadonnées Recorder, périodes et versions concurrentes ; refus si une autre source est déjà sélectionnée ou si une source tiers peut produire un double comptage. Aucune déduction d'exhaustivité depuis une absence dans un échantillon.
- **Unité/destination :** EF et ECS en `m³` dans `water`. CET en `kWh` est techniquement accepté dans le schéma `gas` de Home Assistant Core 2026.11.1, **mais ce schéma ne prouve pas que la catégorie gaz représente correctement le chauffage** ; admission bloquée jusqu'à validation sémantique du modèle et de sa présentation. Aucune conversion fictive en m³ de gaz.
- **Coûts :** aucun coût annuel/historique n'est ajouté sans statistique et calcul vérifiés ; les tarifs ne sont pas requis pour une consommation seule.
- **Transaction L7 conditionnelle :** confirmation explicite avec `before_fingerprint` et `plan_digest`; relecture des preuves et des préférences ; verrou ; sauvegarde native complète vérifiée ; journal durable `prepared` relu ; ajout strictement additif ; vidage de stockage, relecture disque/mémoire ; journal terminal `verified`. Le protocole existant refuse les divergences et le journal partiel.
- **Refus avant écriture :** utilisateur non administrateur, empreintes anciennes, admission incomplète, catégories non validées, autre source potentiellement concurrente, sauvegarde non certifiée, ancien journal non résolu, HA non compatible. La phase de prévisualisation ne déclenche pas de sauvegarde.
- **État du journal :** la prévisualisation expose uniquement le statut (`transaction.journal_status`) et le besoin de reprise, sans recopier les préférences Énergie, les identifiants de sauvegarde ou le contenu confidentiel du journal. Un état `prepared`, invalide ou illisible bloque la confirmation et demande une revue manuelle.
- **Incident :** si l'état disque et mémoire reste identique à l'original, journal `no_write_observed` ; si l'état est exactement le nouvel état, rollback conditionnel vers l'ancien puis relecture et journal `rolled_back_verified`. Si l'état est mixte ou modifié par un tiers, **aucune écriture corrective automatique** ; état `EnergyRecoveryRequired` nécessitant revue manuelle. Une sauvegarde déchiffrable ne prouve pas sa restauration effective.
- **Périmètre :** ne modifie ni `__init__.py`, ni Recorder, ni filiation #37, ni `trybatec-panel.js`. Aucun accès à une installation Home Assistant réelle.

### Contrat frontend C1–C11 pour #155

```json
{
  "schema": "energy_bulk_admin_actions_88_v1",
  "status": "blocked | confirmation_required",
  "preview": {
    "status": "blocked | already_configured | prepared_for_explicit_admin_review",
    "before": null,
    "after": null,
    "plan_digest": null,
    "proposed_count": 0,
    "explanation": [],
    "writes": false,
    "activation_authorized": false
  },
  "l6_diagnostics": {
    "EF": {"status": "blocked", "blockers": ["native_36_37_evidence_missing"], "activation_authorized": false},
    "ECS": {"status": "blocked", "blockers": ["native_36_37_evidence_missing"], "activation_authorized": false},
    "CET": {"status": "blocked", "blockers": ["native_36_37_evidence_missing"], "activation_authorized": false}
  },
  "fluids": {
    "EF": {"status": "insufficient_evidence", "reasons": []},
    "ECS": {"status": "insufficient_evidence", "reasons": []},
    "CET": {"status": "insufficient_evidence", "reasons": []}
  },
  "transaction": {
    "journal_status": "none | prepared | verified | rolled_back_verified | no_write_observed | invalid | unreadable",
    "recovery_required": false,
    "last_terminal_result": null
  },
  "prerequisites": {
    "independent_admission": false,
    "verified_no_conflicting_sources": false,
    "native_backup_restore": false,
    "supported_ha_schema": false
  },
  "blockers": [],
  "actions": {
    "preview": {"enabled": true, "effect": "read_only"},
    "confirm": {
      "enabled": false,
      "required_fields": ["before_fingerprint", "plan_digest", "confirm"],
      "explicit_confirmation_value": true,
      "effect": "transactional_energy_update"
    },
    "recovery": {"enabled": false, "effect": "manual_review_required"}
  },
  "fallback": "setup_assistant",
  "writes": false,
  "activation_authorized": false
}
```

L'exemple est **structurel** : les valeurs réelles proviennent exclusivement du backend, après authentification. L'interface doit afficher les refus et rendre le bouton indisponible en attendant les preuves. Ne pas lier le navigateur directement au port de transaction ni traiter un `plan_digest` comme un jeton d'autorisation. La confirmation nécessite un **nouvel appel explicite**, qui reconstruit toutes les preuves et le plan, puis applique le verrou et les contrôles L7.

### Qualification restante

1. Contrats #36/#37 de complétude et de quiescence indépendamment attestés, exhaustivité des sources Energy tierces et prévention du double comptage.
2. Preuve vérifiable de compatibilité sémantique CET/chauffage au-delà de la validation technique `gas`.
3. Assurance de non-concurrence avec les auteurs HA extérieurs au verrou Trybatec.
4. Sauvegarde **réellement restaurée** et exercice de reprise sur Home Assistant isolé, non réalisé.
5. Intégration de l'endpoint/service administrateur + UI #155, tests de permissions réelles, CI du SHA exact, puis recette HA de production exclusivement sur mandat distinct.

**Etat :** construit et testable de façon synthétique ; aucune activation réelle déclarée. Les tests L7 existants exercent des réussites et rollbacks *fictifs*, pas une preuve d'admission L6 ou de reprise réelle.

---

## EN — Contract and qualification gates

- **Dormant native administrator facade** exposes `preview` and `confirm`; no websocket, service registration, startup callback, background write or panel modification. HA native auth-store admin check and account binding are mandatory.
- **Server-owned evidence only:** the browser supplies no meter inventory, provenance, data-completeness flags or energy source catalog. An exact fingerprint or a successful pure planner is not admission.
- **L6 independent proofs remain pending:** #36 Recorder persisted history, late-writer quiescence, full coverage and version journal; #37 complete physical generations and per-day measured/estimated provenance; cross-checked concurrent statistic IDs and third-party Energy sources. The current non-authoritative contracts continue to deny new enrollment.
- **Units:** EF/ECS `m³` to `water`. CET `kWh` technically matches the Core 2026.11.1 `gas` energy-unit schema, but heat/gas semantic correctness is **not established**. No invented gas-volume conversion or unverified historical costs.
- **Conditional L7 phases:** native admin confirmation → immutable fingerprint/digest re-evaluation → exclusive lock → verified recoverable backup → durable prewrite journal and readback → additive update → flush and persisted/live verification → terminal durable journal. A crash, stale state, lost proof or conflicting third-party source fails closed.
- **Recovery status:** preview discloses only the journal status and whether manual recovery is required; never stored preferences or backup details. Pending, malformed or unreadable journal states block confirmation.
- **Recovery:** no-write outcome, conditional rollback and complete journal readback are distinguished. Mixed or externally modified states require manual review, never an automatic overwrite. Archive decryptability is not a tested real restore.
- **Frontend:** use `energy_bulk_admin_actions_88_v1` above. Always display blockers, preconditions and safe fallback; enable confirmation only after real independent attestation. UI ownership stays with #155.
- **Boundaries:** no Recorder, lineage, shared panel or installation mutation; no merge, release, production backup, restore or Energy update.
- **Still required:** exact SHA CI, isolated HA acceptance including genuine restore/concurrency, independently issued L6 admissions, approval of heat category and separately authorized production acceptance.


---

## FR — Admission L6 indépendante et enregistrement natif (extension du 13/11/2026)

### Matrice de preuve par fluide et compteur physique

Le module purement diagnostique `energy_bulk_l6_admission_88.py` recoupe les contrats publiés par leurs propriétaires #36 et #37 **sans leur attribuer une autorité qu'ils ne détiennent pas actuellement**. La réussite des tests synthétiques démontre la logique des comparaisons, non la disponibilité des preuves sur un Home Assistant réel.

| Contrôle | Producteur attendu | Condition d'admission | Situation du contrat courant |
|---|---|---|---|
| Compte, lot et fluide | Home Assistant / #37 | Périmètre authentifié, une série logique par lot et fluide | Périmètre vérifiable, exhaustivité non attestée |
| Identité physique | #37 | Séries/générations uniques, compteurs actifs et déposés, frontières de service connues, zéro inconnu | `physical_inventory_complete = false` |
| Contributions journalières | #36 + #37 | Jours, totaux, quantités mesurées/estimées et séries physiques concordants | Vérifications partielles, pas d'approbation exhaustive attribuée au jour/version |
| Estimation | #36 | Chaque consommation estimée liée au jour, à la version Recorder et à une décision valide | Contrat positif manquant |
| Persistance Recorder | #36 | Séries persistées et relues, métadonnées, sommes et périodes sans trous | Barrière de file d'attente insuffisante |
| Écrivains tardifs | #36 | Fencing indépendant de tous les écrivains et relecture après barrière, y compris après reprise | `independent_writer_fence` absent |
| Variantes concurrentes | #36 + #37 + #88 | Catalogues exhaustifs et unique version consolidée sélectionnable | Observations non exhaustives |
| Sources Énergie existantes | #88 | Mémoire = disque, toutes références des sections (sources et appareils) cataloguées, provenance disjointe vérifiée | Complétude et exclusivité non garanties |
| Unités et catégorie | #88 / Core cible | EF/ECS `m³` vers `water`; CET `kWh` jamais injecté dans `gas` au seul prétexte de compatibilité technique | EF/ECS schéma compatible, chauffage CET non qualifié |
| Reprise et rollback | L7 + HA | Journal préalable durable, sauvegarde restaurable, contrôle concurrent, relecture, rollback conditionnel | Tests fictifs seulement ; restauration réelle non effectuée |

La condition `eligible_in_synthetic_contract` renvoyée par ce **diagnostic pur** n'est jamais convertie en jeton d'action : ses sorties conservent `activation_authorized: false` et `writes: false`. Les contrats actuels #36/#37 sont eux-mêmes non habilitants ; un jeu de données fictives positif n'est donc pas une attestation de production.

### Points d'enregistrement HA et contrat UI #156

Dans `__init__.py`, uniquement après l'enregistrement du panneau administrateur, `async_register_energy_bulk_admin_88(hass)` installe deux commandes **WebSocket natives**. Le chargement de Home Assistant n'exécute aucune collecte fournisseur, sauvegarde, modification Recorder ou Énergie.

| Commande | Entrée du navigateur | Contrôle serveur | Effet |
|---|---|---|---|
| `trybatec/energy_bulk_88/preview` | `entry_id`, `lot` | `require_admin`, utilisateur HA via `hass.auth`, coordinateur chargé et lot effectivement présent | Lecture seule, réponse `energy_bulk_admin_actions_88_v1` |
| `trybatec/energy_bulk_88/confirm` | `entry_id`, `lot`, `before_fingerprint`, `plan_digest`, `confirm: true` | Même contrôle, plus **verrou backend constant `NATIVE_ENERGY_BULK_WRITES_ENABLED_88 = False`** | Refus `energy_bulk_not_qualified` sans même instancier L7 |

**La route de confirmation est enregistrée mais son exécution est désactivée.** La constante est définie dans `energy_bulk_activation_gate_88.py`, commune à la route et à la façade. Elle ne peut être modifiée ni par le navigateur, ni par une option utilisateur, ni par un événement d'automatisation. Toute levée nécessiterait une nouvelle modification de code auditée et une décision explicite couvrant l'activation, en plus de l'achèvement indépendant de #36/#37, d'un essai HA isolé et d'un contrat de restauration qualifié.

Les autres routes natives existantes (dont les basculements b17) **ne font pas partie de l'ajout groupé #88**. Il ne faut pas les recycler pour contourner les refus L6.

### Interactions frontend et exemples

Requête d'aperçu (WebSocket HA, authentification déjà établie) :

```json
{"type":"trybatec/energy_bulk_88/preview","entry_id":"synthetic-entry","lot":"synthetic-lot"}
```

Résultat : `schema = energy_bulk_admin_actions_88_v1`, `status = blocked`, `preview`, `fluids.EF/ECS/CET`, `l6_diagnostics.EF/ECS/CET`, `prerequisites`, `blockers`, `transaction.journal_status`, `transaction.recovery_required`, `actions.preview.enabled = true`, `actions.confirm.enabled = false`, `fallback = setup_assistant`. La réponse ne contient jamais les copies de préférences ou les identifiants de sauvegarde.

Confirmation (conservée pour le futur protocole, **actuellement refusée**) :

```json
{"type":"trybatec/energy_bulk_88/confirm","entry_id":"synthetic-entry","lot":"synthetic-lot","before_fingerprint":"<hash SHA-256 issu de l'aperçu>","plan_digest":"<empreinte du plan issu de l'aperçu>","confirm":true}
```

Remplacer ces marqueurs par les champs réellement retournés par l'aperçu : **ne pas les inventer**. Sur le code actuel, la route refuse avant toute tentative de sauvegarde ou d'écriture. Pour les états en cours, résultat transactionnel, reprise manuelle et nouvelle prévisualisation, réutiliser les statuts L7 déjà documentés ; il n'existe pas aujourd'hui d'endpoint d'avancement asynchrone ou de restauration automatique. Ne jamais présenter un `journal_status = verified` comme une autorisation d'une nouvelle écriture.

### Qualification indépendante et Gitleaks

Les nouveaux tests `tests/test_energy_bulk_l6_admission_88.py` exercent un scénario **fictif** avec un compteur déposé, un compteur actif, des journées mesurées/estimées et l'exhaustivité des références Énergie. Ils vérifient des refus sur le fence absent, les générations inconnues, décisions non attribuées, version incorrecte, divergence mémoire/disque, autres sources non classées, conflit de sources et CET en kWh sans catégorie chauffage native. `integration_tests/test_ha_energy_bulk_88.py` valide les routes sur environnement HA isolé. Les tests L7 antérieurs gardent la responsabilité des échecs avant/après écriture simulée, journal, sauvegarde, idempotence, rollback et concurrence.

L'échec de Gitleaks historique de la précédente PR #158 survient après un **scan incrémental sans fuite**, sur l'historique accessible de la branche empilée #153. La convergence #164 reconstruite depuis `main` a un scan Gitleaks réussi sur son propre SHA ; il faut réconcilier ces faits avec la conversation CI/CD et l'issue #124, sans exception ni réduction du périmètre de contrôle. **Ne jamais publier la valeur d'une éventuelle détection.**

**Handoff #164 :** seuls les chemins effectivement changés dans la PR #158 sont à reprendre, en conservant les contrôles et tests du SHA final. Le diff empilé complet ne doit pas servir à recopier #147/#153. Ne pas fusionner automatiquement.

## EN — Independent L6 and registered, fail-closed L7 endpoints

The pure `energy_bulk_l6_admission_88.py` diagnostic checks exact independently owned #36 Recorder and #37 physical-lineage envelopes: true native Recorder persistence and a **durable all-writer fence**, complete retired/active meter inventory with known service dates, per-day measured/estimated totals and version-bound approvals, selected consolidated IDs, complete alternative statistics, persisted-vs-live Energy preferences, and independently disjoint third-party references across all Energy sections. An absent proof is a **blocker**, never an empty or implicitly successful result.

The positive test builds **synthetic, fictional** future-owner evidence and cannot mint an authorization: the diagnostic always returns `writes=false` and `activation_authorized=false`. Current published #36/#37 producers remain unable to give such a positive attestation. The Core gas dashboard is for **gas**; its technical kWh compatibility does not qualify thermal CET as gas. EF/ECS m³ maps to native `water` only after all independent guards.

Two HA WebSocket routes are registered after the admin panel: `trybatec/energy_bulk_88/preview` (authenticated admin, strict native account/lot scope, read-only) and `trybatec/energy_bulk_88/confirm` (authenticated admin, explicit fingerprint/digest/boolean, **hard-disabled** by the shared non-configurable backend constant `NATIVE_ENERGY_BULK_WRITES_ENABLED_88 = False`). The disabled route returns `energy_bulk_not_qualified` before constructing a transaction port. No startup Energy/Recorder mutation, provider scan, backup or restore is performed.

Frontend #156 owns only presentation of `energy_bulk_admin_actions_88_v1`: per-fluid states and blockers, independent `l6_diagnostics` (all `activation_authorized=false`), native prerequisites, immutable preview token fields, journal/recovery status, disabled confirmation and setup fallback. Do not expose backup IDs, internal journal preference snapshots or any browser-controlled proof flag. No automatic recovery endpoint is supplied.

Isolated HA route tests, synthetic positive/negative cross-contract cases and existing L7 transaction regressions must pass on the exact SHA. Live fencing, actual restore, category semantics, external-writer concurrency, native acceptance, and CI security remain separate **blocking** requirements. Historical Gitleaks failure should be reconciled by CI/CD (#124), not bypassed. No merge, release, deployment or real HA mutation is authorized.
