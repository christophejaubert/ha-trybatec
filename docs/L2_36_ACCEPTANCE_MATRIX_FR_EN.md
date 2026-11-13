# 🤖 Issue #36 — Matrice de qualification L2 / L2 acceptance matrix

**Référence contrôlée / Verified GitHub reference (2026-11-12):** `main` = `a1bd6d8558c8fe1cc13cadeb1ff4aaa20528dc53`; PR #117 = merged as `a21906bada0b01a9a069afc2a1b84235b2590cc7`. Target release `0.3.4b1` approved **as a target only** by #45; not released. Issues #36, #37, #45, #81, #88 open. PR #82, #118, #120, #127 and #128 draft. These are **observed states**, not authorizations.

**Légende / Legend** — `impl.` = implementation seen in repository; `tests` = existing source test identified but **not re-executed here**; `local` = isolated tests; this matrix also distinguishes exact-head PR CI from Home Assistant business acceptance; `reste` = missing proof/work. A green CI in a previous PR does not validate the entire criterion on real Home Assistant.

| Exigence #36 / Requirement | Implémentation observée / Observed code | Test existant / Existing test | Preuve / Evidence status | Reste / Remaining work |
|---|---|---|---|---|
| Source immutable, appareils actifs/déposés / immutable source & retired meters | `history.py` (`build_history`), `history_review.py`, `history_devices_b15.py` | `test_history_review_b4.py`, `test_b15_alternative_variants.py`, `test_b15_recorder_plan.py` | CI prior to this audit; no real import proof | Full data lineage and R0 source inventory #37 |
| Index zéro N jours, zéro qualifié/non qualifié / zero thresholds | `history_review.review_candidates`, `history_reconstruction.propose_interval` | `test_b15_thresholds.py`, `test_l2_history_safety.py` | #117 merged; source tests inspected | Distinguish clean unchanged episodes after timestamp correction and real UI review |
| Diminutions d'index et conflits / decreases & conflict refusal | `history.py`, `history_reconstruction.py`, `history_review.py` | `test_b15_reconstruction.py`, `test_history_review_b4.py` | Existing tests identified | End-to-end contradiction after successive meter changes |
| Seuil sparse 27 h et DST / sparse + DST | `history.py`, `history_review.py`, `history_reconstruction.py` | `test_b15_thresholds.py`, `test_l2_history_safety.py` | #117 merged (UTC elapsed-time fix where touched) | Verify HA browser display and accounting offset |
| Lissage linéaire du résiduel / measured-first linear residual | `history_reconstruction.propose_interval`, `history_variants_b15.variants_preview` | `test_b15_reconstruction.py`, `test_b15_alternative_variants.py` | Pure function exists and has tests | Multiple partial observed buckets in one sparse period (end-to-end) |
| Bornes estimées sans faux index / approved estimated origin | `history_origin_decisions.py`, `history_origin_store.py`, `history_variants_b15.py` | `test_approved_origin_recorder_plan.py`, `integration_tests/test_ha_panel_origin.py` | Synthetic proof exists | Real approval & persistence acceptance |
| Jours mesurés / estimés / mixtes / daily provenance | `make_b15_plan` consumes `build_coverage_evidence`; `async_preview_b15` exposes server-only `daily_provenance` | `test_history_coverage_l2.py`, `test_b15_recorder_plan.py`, `test_l2_midnight_bucket_bounds.py` | **Developed, branch #127**; exact-head CI required; measured/estimated/mixed tested on synthetic data | Independent full-lineage #37 / Recorder #88, real HA acceptance |
| Couverture et lacunes explicites / coverage & gaps | `history_reconstruction.preview_sparse_intervals` + partial fields | NEW `test_history_coverage_l2.py` | Branch #127: bounded measured/estimated/mixed evidence, unknown bounds and grouped missing days; midnight/DST boundary tests | Independently prove full inter-generation coverage, native Recorder persistence and HA review |
| Série unique par logement/fluide, anciens compteurs / per-scope consolidation | `history_reconstruction.consolidate_consumptions`, `history_plan_b15.make_b15_plan` | `test_b15_reconstruction.py`, `test_b15_recorder_plan.py` | Existing non-duplication guards | #37 physical lineage, #88 verified selection contract |
| Revue: accept/reject/postpone/date/accounting | `history_review.py`, `history_store.py`, `history_smoothing_store.py`, `history_comparison.py` | `test_history_review_b4.py`, `test_history_comparison.py`, `test_history_options_b4.py` | Synthetic tests identified | End-to-end FR/EN/options/panel parity, persistence across reload |
| V1/V2/V3 immuables et sélection exclusive / immutable version ledger | `history_versions_b15.py`, `history_recorder_b15.py` | `test_b15_versioned_history.py`, `integration_tests/recorder_pipeline_spec.py` | Existing state transitions and 90-day readback guard | Failures after crash, recovered V3, independent live Recorder verification |
| Enqueue ≠ persisted / queue is not persistence | `history_recorder_b15.verify_b15_recorder`, `recorder_guard.py` | `test_history_actions_b3.py`, `integration_tests/test_ha_recorder_multimeter.py` | Existing code checks buckets | Need proof readback completeness and durable reboot in target HA |
| Reprise de batch partiellement écrit / partial batch recovery | `history_recorder_b15.verify_b15_recorder` uses read-only recovery classifier; branch #128 blocks unsafe `retry_pending` | `test_history_recorder_recovery_l2.py`, `integration_tests/test_b15_runtime.py`, `integration_tests/test_b15_recovery_crash_l2.py` | **Developed and CI tested on PR #128 SHA**; persisted rows never blindly replayed | Independent writer-quiescence, selective resume, real process restart and isolated database restoration |
| Changement Énergie sécurisé, restauration / Energy switch & rollback | `energy_runtime_b15.py`, `energy_switch.py` | `test_b15_energy_switch.py`, `integration_tests/test_b17_live_energy_handoff.py` | Static/CI evidence exists | Isolated HA 2026.11 transaction, staged backup & rollback; real HA separate |
| Énergie #88 : EF/ECS/CH without double count | `energy_bulk_plan.py`, `energy_bulk_evidence.py` & dormant L3 evidence (#121) | `test_energy_bulk_evidence.py`, `test_energy_bulk_plan.py` | Still intentionally blocked without full physical-history proof | Contract handoff from L2; no auto-enroll before independent gate |
| Compatibilité #81 / #120 sans migration / nonmigrating stable IDs | #120 draft new accounts, #82 draft migration | `tests/test_staged_greenfield_guards_81.py` on #120 | No permitted migration/release | Validate IDs and alias continuity on isolated HA only, PR #82 excluded |

## Risques techniques identifiés / Technical risks

1. In current `main`, `retry_pending=True` can blindly re-enqueue unresolved journal entries. **PR #128** prevents this, preferring a verified idempotent result or a safe refusal. Until #128 is integrated and independent writer-quiescence is proved, do not use selective retries on a live database. No production incident is claimed.
2. The new pure coverage proof derives its `measured` quantity from the existing **raw consumption variant**, not directly from index readings. It must be fed only by the trusted backend after source qualification. It **cannot** be accepted as a browser-supplied declaration.
3. **PR #127** aligns source coverage boundaries with the existing UTC hourly `_bucket()` convention. Added synthetic tests for 00:20 local observations, DST 23/25-hour transitions, explicitly estimated midnight origins and timestamp corrections without source mutation. This is not proof of all timezone/recorder production cases.
4. `history_recorder_b15.verify_b15_recorder` compares the planned hourly buckets with readback; a live failure/restart/delayed Recorder write remains an acceptance item. Never infer successful persistence from enqueue status.
5. A new evidence field must be bound to a complete source/decision fingerprint, and L3/#88 must check it against Recorder and physical inventory independently. No activation based on metadata alone.

## Qualification gates / Portes de qualification

- **G1 — Pure:** both new modules, 21 synthetic test cases locally passed, no Home Assistant imports, no writes.
- **G2 — Integration:** partial: #127 feeds trusted server-side B15 variants into the provenance proof and exposes it through admin read-only preview; #128 feeds HA Recorder readbacks into the recovery classifier, blocks unverified resubmission and adds isolated HA fixture tests. Neither is merged or proven by a full standalone HA restoration.
- **G3 — CI:** [#128](https://github.com/christophejaubert/ha-trybatec/pull/128) validated at `ba7e25c8669743ba9a39837b93431035fb879133`: 20 passed, one intentionally skipped manual release step. [#127](https://github.com/christophejaubert/ha-trybatec/pull/127) requires exact-head CI recheck after these changes. No previous green SHA qualifies a later commit or real HA acceptance.
- **G4 — HA isolated:** partial: synthetic Store re-instantiation, interrupted two-series queue, Recorder readback, V1/V2/V3 gates and Energy rollback unit/fixture tests exist. **Not proven**: full HA process restart, restored SQLite Recorder, independent writer-quiescence, native metadata and Energy schema revalidation on the target HA version.
- **G5 — HA real:** not done and **not authorized**: any Recorder write, real Energy switch, migration or restore.

## EN — Summary

The existing repository already provides reviewed source indexing, a linear measured-first residual algorithm, immutable conceptual V1/V2/V3 ledgers, Recorder post-enqueue verification, and an explicitly confirmed Energy switch path. Two pure modules are now **wired through controlled read-only backend paths on draft PRs**: (a) selected B15 provenance with bounded coverage and (b) HA Recorder readback recovery classification. Branch #128 blocks unsafe retries; branch #127 aligns civil-day statistical boundaries and source-review proofs. Integration CI on final exact SHAs and real HA business acceptance are separate gates. They do **not** modify Recorder, existing data, Home Assistant, or Energy. They must not be described as wired, HA business-accepted, merged, released, or installed. The key boundary is trusted server-generated evidence, not browser claims. Release target `0.3.4b1` is not approved for publication.

## FR — Raccordement L2-A en cours (12/11/2026)

- `make_b15_plan()` consomme désormais `build_coverage_evidence()` sur les variantes physiques calculées côté serveur. Les bornes proviennent des `reviewed_readings` et, lorsqu'elle est approuvée, de la date d'origine estimée ; aucune mesure physique n'est synthétisée.
- Les preuves par lot/fluide incluent `rows[].provenance` (`measured`, `estimated`, `mixed`), contributions physiques, parts journalières et totaux, lacunes, couverture et empreinte. Les données de consommation sélectionnées doivent correspondre à celles du plan consolidé (tolérance explicite).
- `async_preview_b15()` expose `daily_provenance` à l'administrateur sans effectuer d'écriture Recorder ou Énergie. Le plan d'import existant conserve sa signature et ses confirmations.
- Le statut `qualified_bounds_no_gaps` signifie **aucune journée manquante à l'intérieur des bornes fournies**, et non exhaustivité historique absolue : #37 doit encore démontrer la filiation des compteurs, #88 la persistance et l'exclusivité.
- Correction de compatibilité : un compteur conflictuel échoue avant la construction des preuves, avec le même contrat de refus qu'avant #127.

**Garde de livraison :** qualification automatisée sur le SHA exact de la PR, comparaison réelle FR/EN des parcours et recette HA isolée restent distinctes. Les autres critères de #36 ne sont pas déclarés terminés.

## EN — L2-A B15 wiring in progress (2026-11-12)

- `make_b15_plan()` now derives daily evidence from trusted server-computed physical variants and reviewed source bounds, extended only by explicitly approved estimated origins.
- The administrator B15 preview exposes per-day measured/estimated/mixed quantities, physical-meter contributions, known gaps and fingerprints without Recorder or Energy writes. Consolidated selected daily values must agree with the independent provenance calculation.
- `qualified_bounds_no_gaps` proves only completeness within the supplied qualified boundaries, **not** full historical continuity or Recorder persistence. #37 owns meter lineage and #88 owns independent Energy eligibility checks.
- Earlier fail-closed B15 behavior for conflicted meters remains unchanged. CI on the final SHA and isolated HA acceptance are separate requirements.


---

## 🤖 Réconciliation #36 / #36 completion ledger — PR #149, 13 novembre 2026

**FR — Périmètre exact :** branche `feat/36-recorder-finalization-034b1-20261113` empilée sur la candidate brouillon #147. Les développements #127/#128 préexistants ont été réutilisés, sans modification de #37 ni #88. La qualification CI doit être rattachée au **SHA final**, non aux commits intermédiaires. La recette sur HA de production et toute écriture nécessitent des autorisations distinctes.

| REC | Développé / Development | Intégré dans #149 / In branch | Test synthétique identifié / Identified synthetic test | Recette réelle / Production acceptance | Statut bloquant / Blocker |
|---|---|---|---|---|---|
| REC-01 | Journal initial préparé/importé | Oui / Yes | `test_b15_versioned_history`, `test_b15_recovery_crash_l2` | Oui / Required | Test de crash réel isolé manquant / actual isolated crash absent |
| REC-02 | File différée, lecture partielle | Oui / Yes | `test_b15_runtime` | Oui / Required | Persistance native réelle non attestée / no live native proof |
| REC-03 | Buckets et sommes exacts, métadonnées natives | Oui / Yes | `test_b15_runtime`, `test_b15_selective_retry_36` | Oui / Required | Extérieurs à la fenêtre non exhaustifs / out-of-window rows not exhausted |
| REC-04 | Surplus, doublons, somme changée bloqués | Oui / Yes | `test_history_recorder_recovery_l2`, `test_b15_runtime` | Oui / Required | Frontières globales restant à prouver / global boundaries pending |
| REC-05 | Batch persistant/absent/partiel indépendant | Oui / Yes | `test_b15_recovery_crash_l2`, `test_b15_runtime` | Oui / Required | Rejeu absent interdit sans fencing / absent replay denied without fencing |
| REC-06 | Journal relu après réinitialisation du Store | Partiel / Partial | `test_b15_recovery_crash_l2` | Oui / Required | Aucun redémarrage complet HA+SQLite / no full HA/SQLite restart |
| REC-07 | Refus si writer incertain | Oui / Yes | `test_b15_selective_retry_36` | Oui / Required | Pas d'attestation indépendante anti-écrivain tardif / no independent late-writer fence |
| REC-08 | Relecture idempotente, aucun rejeu persisté | Oui / Yes | `test_b15_runtime` | Oui / Required | Vérification cible HA requise / target HA acceptance required |
| REC-09 | V2 demande approbation, V1 préservée | Oui / Yes | `test_b15_versioned_history` | Oui / Required | Confirmation IHM à recetter / UI confirmation pending |
| REC-10 | V2 vérifiée sans activation, garde d'empreinte | Oui / Yes | `test_b15_versioned_history`, `test_b15_energy_switch` | Oui / Required | Énergie #88 non qualifiée / #88 Energy not qualified |
| REC-11 | V1→V2→V3, activation conceptuelle exclusive | Oui / Yes | `test_b15_versioned_history` | Oui / Required | Transaction native Énergie #88 non qualifiée / #88 native transaction pending |
| REC-12 | Échec journal et rollback préférences simulés | Oui / Yes | `test_b15_runtime` | Oui / Required | Restauration HA réelle interdite sans accord / live restoration unauthorized |
| REC-13 | Sélection/retour d'une ancienne version gardés | Oui / Yes | `test_b15_versioned_history` | Oui / Required | Vérification réelle d'exclusivité à faire / actual exclusivity pending |
| REC-14 | Générations physiques et 23/25 h | Oui / Yes (source préexistante) | `test_l2_midnight_bucket_bounds`, `test_ha_recorder_multimeter` | Oui / Required | Filiation complète #37 / complete #37 lineage |
| REC-15 | Unités/sommes invalides, refus natif | Oui / Yes | `test_b15_selective_retry_36` | Oui / Required | Service et schéma HA réels à vérifier / live native schema pending |
| REC-16 | Concurrence : empreinte et verrou Trybatec | Partiel / Partial | `test_b15_energy_switch`, `test_b15_selective_retry_36` | Oui / Required | Aucun verrou global writer Recorder ni exclusion tierce / no global writer fence |

**Point de sécurité / Safety point :** `async_block_till_done()` attend le traitement des tâches Recorder antérieures, **mais ne suffit pas** à exclure une tâche d'import réenfilée après échec (`ImportStatisticsTask`). Ainsi `_independent_writer_quiescence_proof()` refuse par défaut la reprise sélective. Les seuls tests du chemin conditionnel lui substituent une preuve synthétique explicite ; **aucun adapter de production prétendument fiable n'est déclaré disponible**.

**Interface stable / Stable handoff:** `history_recorder_handoff_36.async_b15_recorder_handoff_36` fournit en lecture seule l'empreinte du plan canonique, les séries logiques consolidées, versions concurrentes, `statistic_id`, somme et métadonnées effectivement relues, couverture, provenance quotidienne, lacunes, refus. `admissible=False` et `activation_authorized=False` en toutes circonstances ; #37 garde la responsabilité de la filiation exhaustive et #88 celle de l'exclusivité, des sauvegardes et des transactions natives.

**EN — Qualification boundary:** this is implemented on #149, with isolated synthetic tests, but not signed off for production. Recorder's commit barrier is not a durable global writer fence; selective requeue remains blocked. Real acceptance, complete REC-01..16, #37 lineage, #88 Energy and exact-head CI are independent delivery gates. No merge, release, migration or production mutation is authorized.
