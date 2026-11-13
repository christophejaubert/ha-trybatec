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
  "fluids": {
    "EF": {"status": "insufficient_evidence", "reasons": []},
    "ECS": {"status": "insufficient_evidence", "reasons": []},
    "CET": {"status": "insufficient_evidence", "reasons": []}
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
- **Recovery:** no-write outcome, conditional rollback and complete journal readback are distinguished. Mixed or externally modified states require manual review, never an automatic overwrite. Archive decryptability is not a tested real restore.
- **Frontend:** use `energy_bulk_admin_actions_88_v1` above. Always display blockers, preconditions and safe fallback; enable confirmation only after real independent attestation. UI ownership stays with #155.
- **Boundaries:** no Recorder, lineage, shared panel or installation mutation; no merge, release, production backup, restore or Energy update.
- **Still required:** exact SHA CI, isolated HA acceptance including genuine restore/concurrency, independently issued L6 admissions, approval of heat category and separately authorized production acceptance.
