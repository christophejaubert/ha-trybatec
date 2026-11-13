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
| `meters[]` | `physical_key`, `first_observed_at`, `last_observed_at`, `covered_start`, `covered_end`, `provenance` |
| `suggested_years[]` | Local integer years within observed first/last range; may contain unobserved intermediate years |
| `suggested_years_basis` | `observed_first_last_range_not_yearly_proof` |
| `provenance` | `verified_supplier_history` for verified coverage, `verified_supplier_observation` per meter |
| `cache_reused` | Boolean: no vendor request for the served response |
| `periods_verified` | Number or `null`, from tracked reader if available; never fabricate a count |
| `api_requests` | Number; 0 when cache used; attempts can exceed verified periods |
| `verified_at`, `cache_expires_at` | UTC ISO timestamp; `null` with no valid evidence |
| `cache_invalidation_reason` | `null | identity_changed | date_changed | cache_expired | unverified_coverage` |
| `retry_mode`, `retry_reason` | `restart_from_zero`, `no_atomic_window_checkpoints` |

Job `progress` comes from the matched running task only (`http_requests`, `periods_verified`, `subdivisions`, elapsed, budgets). **Do not display individual validated windows or a resumable checkpoint**: their exact atomic boundaries are not retained.

Job `failure_type` remains an exception **class name only**. New `failure_category`: `cancelled | safety_budget | timeout_or_budget | supplier_response | supplier_validation | network | invalid_scope_or_period | unexpected_error`. Never surface a vendor error body, source URLs, personal identifiers, raw indexes or account credentials.

## Raccordement attendu PR #156 / Frontend integration checklist

1. Call `panel_history_discovery_status` on entering Historique/Tarifs, **without launching a scan**. Show explicit global-scan button only when needed, and keep current manual tariff controls active.
2. Use `discovery_status` independently of job `status`; do not call bounded `historical_preview` a full-account discovery. Display verified interval, inferred observation dates, provenance and completeness; unknown dates remain unset.
3. Prefill C9 account dates only from `coverage.first_observed_at`/`last_observed_at` with `completeness=account_full`. Meter dates from matching exact `coverage.meters[].physical_key`. A partial cache can prefill only if clearly labelled as **partial**, never as the true first or last account observation.
4. Display `progress.http_requests` and `progress.periods_verified` while running; count is not a list of committed windows. Display cached reuse, cache expiry and redacted error category.
5. On interruption/error, give the user `retry_mode=restart_from_zero` with its factual reason; no claim of safe selective resume. Preserve the current UI cancel flow and ensure late results do not override a changed selection/account.
6. Generate tariff suggestions from `coverage.suggested_years`, keeping **registered years** and **free year entry** separate, non-destructive, and never blocked by scan failure.
7. No changes to Recorder import, Energy writes or source-index units. Keep C1–C10 changes in PR #156; no `trybatec-panel.js` or translation edits in C11.

**État / Status:** implementation and synthetic tests in a **draft PR** only; GitHub CI and actual production acceptance must be reported separately on an exact SHA.
