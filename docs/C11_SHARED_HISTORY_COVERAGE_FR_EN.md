# 🤖 C11 — Contrat backend mutualisation / Shared historical evidence contract

**Dépôt / Repo:** `christophejaubert/ha-trybatec` — issue #155 (C11), MOE #45, interface #156.  
**Référence / Baseline:** published `main` / `0.3.4b1` (`8d621da9703b40662800b4a7c286707e8a7f895f`).  
**Nature / Scope:** backend **lecture seule / read-only**, no release or Home Assistant operation.

## FR — Comportement et preuves

- Une découverte `tariff_year_coverage` reste **explicite** et balaie la période prise en charge du **01/01/2000 à la date du jour dans Europe/Paris**, pour **tous les compteurs physiques du compte vérifié**. Le lecteur existant adapte la taille des fenêtres sous le verrou par compte et les plafonds de sécurité.
- Après retour et validation **intégrale** (`combine_payloads`), les réponses brutes déjà récupérées sont conservées uniquement en **RAM du coordinateur** (`_panel_history_source_evidence`), avec les bornes et preuves dérivées. Aucun second registre durable, aucun journal contenant les relevés, aucun changement Recorder/Énergie.
- `historical_preview` réutilise la découverte complète pour toute période comprise dans son périmètre : aucune nouvelle lecture fournisseur pour le même compte tant que la preuve est valide. L'analyse de lissage **reste limitée** aux dates explicitement choisies, aux garde-fous existants et aux décisions par compteur.
- Un aperçu borné acquis avant la découverte globale ne prouve que **son intervalle**. Il peut être réutilisé pour ce même intervalle, mais **n'établit jamais la première observation absolue du compte** et ne remplace pas un balayage global pour les tarifs.
- Les suggestions d'années sont **déduites des années civiles locales des premières et dernières observations vérifiées** ; elles ne prétendent pas qu'une observation existe pour chaque année intermédiaire. Les années déjà enregistrées et toute saisie manuelle de 2000 à 2100 restent indépendantes des suggestions.
- Les compteurs archivés et les compteurs courants restent distincts par `physical_key` (clé métier issue de `meter_key(lot, fluid, serial)`). Aucun rapprochement à partir d'un nom affiché ; chaque fluide garde sa propre identité.
- Le cache expire après **3 600 secondes**, au changement de date Paris, d'identifiant de compte/contrat, de lots ou d'inventaire physique. Il est éliminé en cas d'invalidation de sa portée. Un échec de lecture **n'écrase pas un cache valide antérieur**. Les informations de preuve ne sont **pas persistées** après un redémarrage.
- Les réponses d'API peuvent être interrompues, coupées par budget, trop volumineuses ou invalides. Le lecteur historique ne fournit **pas** de points de reprise persistants et vérifiés à granularité fenêtre. Par sécurité : **`retry_mode=restart_from_zero`**, **`retry_reason=no_atomic_window_checkpoints`**. Ne pas suggérer une reprise sélective tant que sa validité (identité, période, réponses atomiques, déduplication, expiration) n'est pas démontrée. Une recherche partielle/annulée n'est jamais publiée comme couverture complète.

## EN — Evidence and limitations

The user-initiated `tariff_year_coverage` scan reads **all physical meters** within the validated account scope, from 2000-01-01 to today's Europe/Paris calendar date. Existing adaptive windows, vendor response limits, per-account lock and safety ceilings stay intact. Only a **fully verified** reading is atomically stored in coordinator memory, including the source payloads and derived physical-meter bounds. A subsequent bounded historical preview can use these payloads without another supplier scan. A bounded preview is evidence for its own exact date range only and must **not** imply account-complete observation coverage. Local-calendar suggested years form a range from observed earliest/latest timestamps, **not proof of data in every year**. Manually entered tariffs remain editable regardless of discovery state. Cache is scoped to account/deal/lots/inventory, expires after 3,600 seconds or on Paris date rollover, and is never persisted. Failed/cancelled windows do not provide verified atomic checkpoints; retries restart the full requested query.

## Contrat WebSocket / WebSocket contract

Existing commands remain compatible:

- `trybatec/panel_history_job_start` with `kind=tariff_year_coverage` **without** `start_date/end_date` starts the global account scan; with `kind=historical_preview`, both bounded dates are mandatory. One active panel job per config entry, no implicit auto-start.
- `trybatec/panel_history_job_status`, `trybatec/panel_history_job_cancel` retain their existing authenticated-admin contract and job ID; only the matching job can be cancelled.
- `trybatec/panel_tariff_years` returns full history coverage, while `trybatec/panel_history_preview` returns a date-bounded analysis.
- **NEW, read-only:** `trybatec/panel_history_discovery_status` with `entry_id` (admin only). It reports the latest job or current validated cache **without starting a scan**.

Existing job `status`: `running | complete | failed | cancelled` **means the job outcome**, not whether the whole account has been scanned.

**New `discovery_status`**: `not_started | running | incomplete | complete | error | interrupted`.
- `complete`: whole supported account range 2000–today verified.
- `incomplete`: only an explicitly bounded interval verified, **or** a successful bounded job whose completeness is not global.
- `interrupted`: cancellation; `error`: failed source read/validation; neither counts as complete.
- `not_started`: no current valid evidence or active/retained job.

**New `coverage` object** is attached to successful tariff/year and preview results and to completed job/status snapshots:

| Field | Type and invariant |
| --- | --- |
| `status` | `not_started | incomplete | complete` (source extent, not job state) |
| `completeness` | `unknown | bounded_period_only | account_full` |
| `coverage_start`, `coverage_end` | ISO `YYYY-MM-DD`, verified **requested source interval**, not observed endpoints |
| `first_observed_at`, `last_observed_at` | ISO timestamps or `null`; first/last **observations** in covered data |
| `meters[]` | `physical_key` (exact 24-hex opaque key), `fluid` (EF/ECS/CET), `first_observed_at`, `last_observed_at`, **`last_source_observed_at`** (same timestamp; panel-compatible alias), `observed_years[]`, `covered_start/end`, `provenance` |
| `observed_years[]` | Sorted union of calendar years **actually containing dated supplier observations** in the validated source; never inferred from the outer interval |
| `suggested_years[]` | All local integer years between earliest and latest observations; can include years without readings; suggestions only |
| `suggested_years_basis` | `observed_first_last_range_not_yearly_proof` |
| `provenance` | `verified_supplier_history` for verified coverage, `verified_supplier_observation` per meter |
| `cache_reused` | Boolean: no vendor request for the served response |
| `periods_verified` | Number or `null`, from tracked reader if available; never fabricate a count |
| `api_requests` | Number or `null`; `0` when source cache serves without a new request; `null` for failed/cancelled jobs when their completed request count is not known; attempts can exceed accepted periods |
| `verified_at`, `cache_expires_at` | UTC ISO timestamp; `null` with no valid evidence |
| `cache_invalidation_reason` | `null | identity_changed | date_changed | cache_expired | unverified_coverage` |
| `retry_mode`, `retry_reason` | `restart_from_zero`, `no_atomic_window_checkpoints` |

The discovery endpoint also returns **`verified_coverage`**: a snapshot of the **currently valid** cache, independently of the last job outcome. On a running/failed/cancelled job, `coverage=null` (that job has not produced an accepted new result) while `verified_coverage` can still be `complete` or `incomplete` from an earlier valid scan. When there is no retained job, `coverage` and `verified_coverage` are identical, including `cache_invalidation_reason`. An expired or scope-invalidated completed job is not exposed as a successful current discovery. On the discovery command, `coverage.cache_reused=true` means this **status query** did not read the supplier; the job-level `cache_reused` and `api_requests` continue to describe the original job, not the status poll. / Le statut de job et la preuve encore en cache sont **indépendants** ; une erreur ou annulation n'efface pas une preuve antérieure encore valide.

Job `progress` comes from the matched running task only (`http_requests`, `periods_verified`, `subdivisions`, elapsed, budgets). **`periods_verified` counts supplier response windows accepted by the bounded reader, not an independently proven complete physical-meter history**. A later `combine_payloads` check can still fail the overall request. Counts are operational progress only, not resumable checkpoints; exact atomic windows are not retained. / Le compteur de périodes est une progression technique, **pas** une preuve d'exhaustivité ni un journal de reprise.

Job `failure_type` remains an exception **class name only**. New `failure_category`: `cancelled | safety_budget | timeout_or_budget | supplier_response | supplier_validation | network | authentication | authorization | invalid_scope_or_period | unexpected_error`. Never surface a vendor error body, source URLs, personal identifiers, raw indexes or account credentials.

## Exemples synthétiques / Synthetic status response examples

**FR.** Ces exemples sont des **extraits JSON** des réponses de `trybatec/panel_history_discovery_status`. Les champs systématiques supplémentaires (`kind`, `started_at`, `elapsed_seconds`, `periods_verified`, `api_requests`, `recorder_writes=false`, `energy_writes=false`, `retry_mode=restart_from_zero`, `retry_reason=no_atomic_window_checkpoints`, etc.) sont documentés ci-dessus. Les dates, identifiants `aaaaaaaaaaaaaaaaaaaaaaaa` et compteurs sont entièrement synthétiques. **Aucun extrait ne déclenche un accès fournisseur.**

**EN.** These are **JSON excerpts** from the status API, not complete wire payloads. All identifiers, dates and amounts are synthetic. Additional invariants are documented above; each example represents a read-only, zero-vendor-request status observation.

### 1. Non lancé / Never started

```json
{"id":null,"status":"not_started","discovery_status":"not_started","progress":null,"failure_category":null,"coverage":{"status":"not_started","completeness":"unknown","coverage_start":null,"coverage_end":null,"meters":[],"suggested_years":[],"observed_years":[],"cache_invalidation_reason":null},"verified_coverage":{"status":"not_started","completeness":"unknown"}}
```

### 2. En cours / Running

```json
{"id":"0123456789abcdef01234567","kind":"tariff_year_coverage","status":"running","discovery_status":"running","coverage":null,"verified_coverage":{"status":"not_started","completeness":"unknown"},"progress":{"http_requests":4,"periods_verified":2,"subdivisions":1},"failure_category":null}
```

### 3. Complet / Complete account scan

```json
{"id":"0123456789abcdef01234567","kind":"tariff_year_coverage","status":"complete","discovery_status":"complete","coverage":{"status":"complete","completeness":"account_full","coverage_start":"2000-01-01","coverage_end":"2026-11-13","first_observed_at":"2022-01-01T00:00:00+01:00","last_observed_at":"2025-06-01T12:00:00+02:00","meters":[{"physical_key":"aaaaaaaaaaaaaaaaaaaaaaaa","fluid":"EF","first_observed_at":"2022-01-01T00:00:00+01:00","last_observed_at":"2025-06-01T12:00:00+02:00","last_source_observed_at":"2025-06-01T12:00:00+02:00","observed_years":[2022,2025],"covered_start":"2000-01-01","covered_end":"2026-11-13","provenance":"verified_supplier_observation"}],"observed_years":[2022,2025],"suggested_years":[2022,2023,2024,2025],"suggested_years_basis":"observed_first_last_range_not_yearly_proof"},"verified_coverage":{"status":"complete","completeness":"account_full"}}
```

**Important :** 2023 et 2024 sont des **années suggérées sans observation attestée dans cet exemple**. / The intermediate years 2023 and 2024 are suggestions, **not verified observation years**.

### 4. Incomplet / Verified bounded interval only

```json
{"id":"0123456789abcdef01234567","kind":"historical_preview","status":"complete","discovery_status":"incomplete","coverage":{"status":"incomplete","completeness":"bounded_period_only","coverage_start":"2022-01-01","coverage_end":"2022-12-31","first_observed_at":"2022-04-01T10:00:00+02:00","last_observed_at":"2022-08-01T10:00:00+02:00"},"verified_coverage":{"status":"incomplete","completeness":"bounded_period_only"}}
```

### 5. Interrompu / Cancelled

```json
{"id":"0123456789abcdef01234567","status":"cancelled","discovery_status":"interrupted","coverage":null,"verified_coverage":{"status":"incomplete","completeness":"bounded_period_only"},"failure_category":"cancelled","retry_mode":"restart_from_zero","retry_reason":"no_atomic_window_checkpoints"}
```

### 6. Erreur réseau / Supplier network failure

```json
{"id":"0123456789abcdef01234567","status":"failed","discovery_status":"error","coverage":null,"verified_coverage":{"status":"not_started","completeness":"unknown"},"failure_type":"TrybatecConnectionError","failure_category":"network","retry_mode":"restart_from_zero","retry_reason":"no_atomic_window_checkpoints"}
```

### 7. Cache valide sans job / Valid cache, no retained job

```json
{"id":null,"status":"complete","discovery_status":"complete","coverage":{"status":"complete","completeness":"account_full","cache_reused":true,"verified_at":"2026-11-13T11:00:00+00:00","cache_expires_at":"2026-11-13T12:00:00+00:00"},"verified_coverage":{"status":"complete","completeness":"account_full","cache_reused":true},"api_requests":0,"failure_category":null}
```

### 8. Cache invalidé par expiration / TTL-invalidated cache

```json
{"id":null,"status":"not_started","discovery_status":"not_started","coverage":{"status":"not_started","completeness":"unknown","cache_invalidation_reason":"cache_expired","verified_at":null,"cache_expires_at":null},"verified_coverage":{"status":"not_started","completeness":"unknown","cache_invalidation_reason":"cache_expired"},"progress":null,"api_requests":0}
```

**FR — Précisions :** `running` et `error` décrivent la dernière tentative, jamais la preuve antérieure. `complete` pour un job ne signifie pas nécessairement que le **compte entier** est exhaustif : contrôler `completeness`. Le cache ne garantit pas l'actualité des index fournisseur au-delà de la période vérifiée et de sa validité locale.

**EN — Caveats:** Job status and verified evidence are orthogonal. Successful bounded jobs are not account-wide scans. No response implies an observation for each intermediate year or guarantees a recoverable vendor window. There are no Recorder, Energy or supplier writes in this status pathway.

## Raccordement attendu PR #156 / Frontend integration checklist

1. Call `panel_history_discovery_status` on entering Historique/Tarifs, **without launching a scan**. Show explicit global-scan button only when needed, and keep current manual tariff controls active.
2. Use `discovery_status` independently of job `status`; do not call bounded `historical_preview` a full-account discovery. Display verified interval, inferred observation dates, provenance and completeness; unknown dates remain unset.
3. Prefill C9 account dates only from `coverage.first_observed_at`/`last_observed_at` with `completeness=account_full`. Meter dates from matching exact `coverage.meters[].physical_key`. A partial cache can prefill only if clearly labelled as **partial**, never as the true first or last account observation.
4. Display `progress.http_requests` and `progress.periods_verified` while running; count is not a list of committed windows. Render `verified_coverage` separately when a new job is running/failed/cancelled, never presenting it as the new job's result. Display cache expiry/invalidation and redacted error category.
5. On interruption/error, give the user `retry_mode=restart_from_zero` with its factual reason; no claim of safe selective resume. Preserve the current UI cancel flow and ensure late results do not override a changed selection/account.
6. Generate tariff suggestions from `verified_coverage.suggested_years` **only when its `completeness=account_full`**; `observed_years` means actual dated observations, while suggested intermediate years are not observed. Keep **registered years** and **free year entry** separate, non-destructive, and never blocked by scan failure.
7. No changes to Recorder import, Energy writes or source-index units. Keep C1–C10 changes in PR #156; no `trybatec-panel.js` or translation edits in C11.

**État / Status:** implementation and synthetic tests in a **draft PR** only; GitHub CI and actual production acceptance must be reported separately on an exact SHA.
