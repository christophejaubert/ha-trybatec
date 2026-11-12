# 🤖 L2 #36 — Contrats d'intégration / Integration contracts

## FR — Sous-lot A : preuve de couverture en lecture seule

**Module préparé :** `custom_components/trybatec/history_coverage_l2.py`.

- Entrée strictement interne : `variants_preview(...)['meters']`, jamais une charge fournie par le navigateur ; option `source_bounds` issue de `reviewed_readings` qualifiés (première journée exclue) et des origines estimées confirmées.
- Une source doit préciser lot, fluide, numéro, unité normalisée, empreinte source exacte, variante `raw` et `smoothed` et empreintes des décisions approuvées. Toute unité incertaine ou variante incohérente est rejetée.
- Le volume mesuré provient uniquement de la variante `raw` qualifiée ; le volume estimé est le résiduel positif `smoothed - raw` et jamais l'intégralité du cumul fournisseur. Une présence simultanée produit `mixed`.
- Les journées inconnues sont absentes de la série et rapportées comme `gaps` uniquement si toutes les bornes sont qualifiées. Sans preuve de bornes, `coverage='unknown'` : aucun zéro fictif.
- Les contributions d'anciens compteurs sont conservées individuellement. Deux compteurs le même jour sont refusés, sauf groupe parallèle explicitement approuvé en backend.
- L'empreinte inclut l'origine, les décisions et les contributions ; le rapport renvoie `recorder_writes=False`.
- **Non raccordé** à `make_b15_plan` et au collecteur #88 : vérifier d'abord la convention d'affectation au jour local de `history._bucket`, les jours d'origine estimée et les sources physiques sans relevé exploitable. Aucun import/activation ne doit reposer uniquement sur ce module.

## FR — Sous-lot B : plan de reprise de batch Recorder en lecture seule

**Module préparé :** `custom_components/trybatec/history_recorder_recovery_l2.py`.

- Entrées internes : journal versions `schema=1` + lectures Recorder complètes de toutes les fenêtres attendues ; `queue_quiescent=True` seulement après preuve indépendante d'absence d'écriture en cours.
- Décisions : `persisted_verified_no_requeue`, `retry_candidate_requires_explicit_confirmation`, `writer_may_be_active_no_retry`, `readback_incomplete_no_retry`, `partial_or_mismatched_no_retry`, `conflicting_readback_no_retry`.
- Ne jamais remettre en file une statistique déjà entièrement persistée. Toute lecture partielle, doublon, métadonnée contradictoire ou version attendue absente bloque la reprise complète.
- Une proposition de nouvelle mise en file n'est **ni** une autorisation utilisateur **ni** une preuve de disponibilité de transaction Recorder ; aucun appel direct à `async_add_external_statistics`.
- **Non raccordé** aux chemins `retry_pending` de `history_recorder_b15.py`. Avant intégration, établir le protocole de quiescence, sauvegarde, reprise après redémarrage, et l'exactitude du readback HA/Recorder 2026.11 sur fixture.

## Interfaces attendues / Expected interfaces

| Producteur / Producer | Consommateur / Consumer | Contrat attendu / Expected contract | Verrou / Gate |
|---|---|---|---|
| `history.py` + décisions | `variants_preview` / lot L2-A | Bornes fiables par compteur, empreinte, variant brut/lissé, décision explicite | Pas d'origine ou de jour inventé / no invented origin or day |
| L2-A | `make_b15_plan` | Consommations par jour et part mesurée/estimée, provenance, couverture et `fingerprint` | Parité des totaux, tests de dates; aucune importation implicite |
| `make_b15_plan` | L2-B / version ledger | Plan `fingerprint`, scope, versions Vn, snapshots UTC | Journal durable, idempotence, aucun remplacement destructif |
| Recorder (backend) | L2-B | Fenêtres complètes, sommes, preuve lecture, absence d'écrivain | Refus de réécriture d'une Vn persistée |
| L2-A + L2-B | L3/#88 | Série consolidée physique ancienne/actuelle, unité, bornes, source hash, preuve Recorder | L3 dérive ses preuves lui-même, n'active rien sur la seule déclaration L2 |
| #81/#120 | L2 | Identité logique lot + fluide préservant comptes existants | Aucun changement de `entity_id`, `unique_id`, migration ni nettoyage historique |

## EN — Integration constraints

Both modules are deliberately read-only. The coverage adapter must use server-validated physical variants and genuine source bounds, distinguish measured/estimated/mixed, and avoid invented zero days. The Recorder recovery adapter must use complete trusted readback plus independently established writer quiescence; a preview never grants import permission. Adapter changes are pending isolated Home Assistant tests and exact-head CI. Neither #82 migration nor actual Energy/Recorder actions are in scope. Read and assess in #45 before any release decision.