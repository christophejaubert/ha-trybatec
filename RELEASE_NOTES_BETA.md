# 0.2.0b16 — Defer first Trybatec synchronization until HA has started

- The first vendor index request runs **after** Home Assistant signals
  `homeassistant_started`, not during config-entry setup. On an integration
  reload while HA is already running, the initial refresh still starts
  immediately.
- Meter entities are created from a successful vendor response, without
  synthetic readings or speculative units. Existing entity and Recorder IDs
  remain unchanged.
- An initial network/data failure is retried by the coordinator after
  approximately one minute instead of waiting for the normal polling
  interval (default 12 hours). After success, the configured polling interval
  resumes. Authentication failures still request reauthentication.
- Pending first-poll listeners are canceled on integration unload; no
  historical Recorder import, Energy write or entity migration runs at startup.
- Isolated Home Assistant regression tests cover boot ordering, transient
  failure and recovery, and unload before the started event.

**Scope and limitations:** This targets startup timing and resilience; it
cannot guarantee availability of the external Trybatec service. Any
production history import, Energy switch or entity migration still requires
independent review, backup and explicit confirmation.

---

# 0.2.0b15 — Experimental beta (opt-in history and Energy tools)

**PR #38 was merged into `main` after successful mandatory CI. Installation or publication alone does not authorize a historical Recorder import or a change to Energy preferences on a real Home Assistant instance.**

### Changes currently implemented

- Configuration from username and password for a single unambiguous housing,
  plus a strictly validated full Index page URL fallback; native
  reauthentication retaining the same HA config entry.
- Persistent access problem notifications with delayed network-failure
  threshold and recovery dismissal.
- Configurable historical sparse-period and zero-day alert thresholds.
- Opt-in, read-only linear residual reconstruction from actual physical
  meter index bounds; explicit user-declared review decisions and confirmation.
  Retain raw measured index readings, including zeros and retired devices.
  Date-based daily proposals use Europe/Paris civil days and never represent
  estimated consumption as a measured index.
- A new native review path in integration options for manual/telemetry
  explanations and individual sparse periods. Decisions are locally
  stored against exact source fingerprints; changed source values invalidate
  stale choices.
- Read-only physical-meter alternative consumption variants: measured-only
  or measured plus confirmed linear gap estimates. Separate meter generations
  remain distinct; a logical dwelling+fluid consolidation adds consumption,
  never cumulative indexes.
- Experimental, **non-executing** modules to preview entity migrations,
  track V1/V2/V3 historical revision states, and prepare exclusive Energy
  preference replacements and rollback snapshots.
- API-visible retired meters can appear as historical-only index sensors,
  without being treated as continuously increasing live consumption.
- Synthetic Python and isolated Home Assistant tests have been added. Their
  complete status must be checked at the exact final PR head.

### Further implementation (not yet accepted on the target installation)

- `history_plan_b15.py` creates hourly UTC Recorder plans from Paris civil-day
  consumption, for each verified physical meter variant and one selected
  dwelling/fluid consolidation. Index readings are **not** combined.
- `trybatec.preview_b15` produces a source-specific fingerprint;
  `trybatec.import_b15` requires the same fingerprint, a confirmed backup and
  explicit approval. This stores the import journal before enqueuing new `_vN`
  Recorder IDs. Old generations are never overwritten or deleted.
- `trybatec.verify_b15` reads back every persisted hourly sum and only
  then marks imported versions as verified.
- `trybatec.preview_b15_energy` checks the exact Energy preference snapshot,
  Recorder verification and **all** same-dwelling physical alternatives.
  `trybatec.activate_b15_energy` is an explicit admin-only action that
  flushes and re-reads Home Assistant Energy preferences and the b15 version
  ledger. Audited, guarded rollback is attempted on failure, never
  overwriting a concurrent unrelated Energy edit.
- `trybatec.archive_b15_meters` persistently saves the exact identities
  and latest actual index observations of retired physical meters from the
  complete vendor history. After an integration reload, historical-only
  sensor devices remain consultable even if no longer returned by current
  portal polling.
- `trybatec.preview_b15_migration` and `trybatec.apply_b15_migration`
  support a conservative **one-entity-at-a-time** technical unique-ID
  migration, only if same lot/serial/fluid/unit provenance can be verified.
  The actual Home Assistant `entity_id` is kept unchanged, preserving
  dashboard and automation references and Recorder history.
  Unprovable legacy identity cases remain blocked for manual review.

### Known validation limitations and safety requirements

- Validate all new Recorder, Energy and historical-device actions on
  isolated HA, including restart/recovery and genuine Recorder persistence.
- Verify Energy rollback on real current-version Home Assistant and
  compatibility with the schema used on the user's instance.
- Migrate or explicitly retain any legacy technical entities whose
  physical identity or source unit cannot be proven; no unsafe cleanup.
- Mandatory automated CI checks passed for the PR and the merge on `main`; the
  final release workflow must verify the exact tag target and the post-merge
  main CI before publishing.
- User-controlled acceptance of the final IHM and runtime behavior,
  with no automatic production import or settings modifications.

**Compatibility limitation:** accounts managing several copropriétés are not
validated as an automatic configuration scenario. Never silently select a
housing or use a portal UUID without checking that account's authorization.

**This is an experimental prerelease, not a claim of complete field acceptance.**
Do not perform production history imports, Energy switching or legacy migration
without isolated validation and backups.

---

# 0.2.0b14 — Unreleased candidate: full-range first, adaptive history recovery

**Pull request only — no merge, release, HACS installation or Home Assistant changes.**

- First request the **entire historical interval selected by the administrator**, without pre-splitting every 92 days or imposing a global duration/window/request ceiling.
- If a response is oversized, malformed, missing required structure, explicitly rejected as a window (HTTP 408/413/414/422), or times out, retry shorter overlapping intervals until all are obtained or the smallest interval still fails.
- Keep auth failures and unrelated network/HTTP errors fail-closed. Limit each individual response's bytes, lines and observations; space sequential requests. Do not log vendor payloads, tokens or credentials.
- Combine all authorized physical meters (including replaced/retired meters), deduplicating repeated timestamp/value pairs across overlapping intervals. Reject contradictory observations instead of selecting one silently.
- A persistently invalid one-day interval blocks the entire preview and any Recorder import; report its dates and a sanitized error reason. Preserve any previous successful review cache.
- Expose accepted/rejected window counts and a source-window coverage flag in the read-only preview. These prove successful API responses for requested ranges, **not** independent vendor data completeness.
- Remove aggregate history row/meter/reading ceilings that arbitrarily prevent otherwise valid multi-year collections. Keep vendor *per-response* safeguards and per-meter identity checks.
- Regression tests cover the full-range-first behavior, multi-decade requests, seven current/retired meters and 1,497 **synthetic** observations in a single successful response, adaptive splitting of large histories, duplicate boundary readings, unresolvable days, and API error classification.

**Publication gate:** all required CI checks, then explicit permission to merge/publish, followed by user-controlled live preview against the vendor. Synthetic tests cannot verify the vendor's undocumented behavior.

---

# 0.2.0b13 — Candidate correction: adaptive historical preview and readable unit facts

**Draft only — no tag or release; no installation or changes to Home Assistant.**

- Recover long Trybatec history previews when an API index response fails with a data-format/size error by retrying smaller, overlapping periods. This directly targets the reported October 1–November 9 window failure (a 39-day request), while the November 1–9 request succeeds. The **92-day segmentation is not a proven vendor limit**.
- Keep history integrity strict: do not omit any date, silently accept partial data, overwrite the previous preview cache, or import Recorder rows when any subwindow is invalid. There is no fixed total-request ceiling; individual responses remain bounded, and requests are sequential and briefly spaced.
- When even a single day is invalid, report the exact failing date window and a fixed, nonsensitive error category. Never log vendor bodies, credentials or tokens.
- Remove the global 10-year and 45-window ceilings. Count actual attempted requests, including rejected larger windows, in `api_requests`. Dates must be valid, ordered and no later than today.
- In the unit options form, show the physical meter, chart reference unit, and explicit API unit on **three separate Markdown lines** with **bold values**. Escape portal-supplied meter labels so they remain literal text.
- Add automated regression tests for recoverable oversized windows, a persistently invalid day, retrieval spanning more than six years and seven physical meters with over 80 requests, absence of cache replacement on failure, and French/English formatted labels.

**Unverified until live testing:** whether October's real API response will become recoverable through subdivision, and the exact visual line-break rendering on a live French Home Assistant frontend.

No automatic history import, Recorder write, HACS install or publication is authorized by preparing this candidate. Merge is permitted only by the user's explicit instruction after full CI checks.

---

# 0.2.0b12 — Candidate corrective: default meter units and saved selections

**Draft candidate only; no tag or release, no merge, no changes to running Home Assistant.**

- The saved, user-confirmed unit of each physical meter (lot + fluid + serial) is the first choice when an options form is reopened, including retired meters found in the cached historical preview.
- If no unit was saved, propose an explicit valid API index unit, otherwise the configured portal chart display unit as the selected radio choice. Clicking **Save** confirms it as a manual choice; opening the form never writes any unit.
- Keep an explicit *Unknown* choice, strict allowed-unit validation, and existing safeguards against contradictory API index-unit evidence. Retain per-meter UUIDs and all other options.
- Remove misleading warnings and explain that the chart reference shown is configured rather than dynamically retrieved.
- Add focused tests for EF/ECS/CET, all saved per-meter selections, revisiting a form after a new options flow starts, and physically replaced meters.
- **Unrelated historical preview investigation:** a November 1–9, 2026 preview succeeded with one API window, whereas an October 1 start failed, also with one API window. The 92-day chunking cannot by itself explain the October failure. This candidate does not change historical fetching.

**Release gate:** all required CI controls followed by actual Home Assistant visual verification of radio defaults before approving a beta release.

---

# 0.2.0b11 — Corrective draft: restore direct, readable options navigation

**Not released. PR draft only; no change to a running Home Assistant installation.**

- Restore six direct principal destinations: Settings, Diagnostics, Meter units, History overview, Meter details and History review. Remove intermediate options menus introduced in b10 that produced blank entries in the real frontend.
- Select a meter and open its edit form directly; keep existing verified-unit persistence, UUID validation, logging options and safe historical writes.
- Keep mandatory explicit historical confirmation, without navigation-only commits or automatic Recorder imports.
- Test Home Assistant's real OptionsFlow manager and French/English backend translation loader, in addition to checking the shipped locale files and code-level menu names.
- **Publication is blocked until** the user validates the rendered menu and relevant screens on a real Home Assistant frontend. CI alone cannot establish this.

No actual Trybatec API, stored history, Energy settings, notifications, or HA configuration is modified by preparing this candidate.

---

# 0.2.0b10 — Saved-unit consistency and native one-click navigation

**Released experimental beta; user-reported UI regression.** Several menu entries appeared blank in the real Home Assistant frontend even though backend CI passed. This release must not be considered visually validated.

- Standardize all read-only navigation on Home Assistant native click-to-open menus with explicit links to the preceding level and to the main menu. Settings, diagnostics, meter selection and historical review have dedicated navigation menus.
- Remove the post-submit navigation radio field from editing and confirmation forms. Validate and save entered values before moving on; meter-unit changes return to the meter list by default. Selection radios remain only for actual data choices such as measurement units and source readings.
- Before an historical decision is persisted, provide a separate one-click navigation menu for approval, safe return to the previous step, or exit without saving. The final confirmation checkbox and out-of-period approval remain mandatory.
- Document the menu-versus-form UI contract for future screens in `docs/OPTIONS_UI_CONVENTIONS.md`.
- Recompute each meter's displayed verified unit from the current persisted options. List labels put the real status first (manual/API confirmation or needs confirmation), instead of relying on a stale coordinator snapshot.
- Choose units and meter/reading lists with explicit Home Assistant `SelectSelector(mode=list)`, which renders radio buttons even for more than five options. Keep selections separate from post-save navigation.
- On editable forms, validate and save the chosen unit/UUID, logging threshold or settings before returning to the main menu or meter list. Invalid inputs never navigate as if the save succeeded.
- On read-only menus and the historical review decision menu, use native one-click Home Assistant menu entries without an extra radio-button selection and Submit. Never record a historical decision until the separate explicit confirmation (and any required out-of-period confirmation).
- Preserve historical correction draft fields when navigating back; navigation to the main menu after an approved decision saves first, then returns.
- Replace the generic Developer Tools link with Home Assistant's official preselected action redirect for `trybatec.preview_history`. Opening the link does not execute the action.
- Add pure and actual Home Assistant options-manager tests for saved options, safe navigation, radio selectors, and published translations.

No API polling, Recorder statistical import, Energy dashboard modification or external notification is triggered by navigation.

---

# 0.2.0b9 — Historical menu recovery, explicit unit provenance and diagnostics

**Experimental prerelease candidate.** Never automatically import real Recorder statistics or alter the Energy dashboard; approval for a future b9 GitHub release and a real Home Assistant installation remains a separate control.

## Changes
- Fix a Home Assistant flow-manager UnknownStep regression: all three historical no-preview/unavailable/empty menus now have actual handler methods, so they remain navigable instead of returning a bare error. The action and log links remain instance-relative and clickable.
- Replace escaped literal line breaks in translated historical recovery messages with real paragraphs.
- Preserve a previously confirmed meter unit when consistent with the API; otherwise preselect a clearly detected explicit API index unit. A chart display-unit reference is never auto-confirmed. A conflict or unrecognized API unit remains unverified.
- Clearly label the unit's origin (manual confirmation / explicit API detection / chart-only suggestion); provide revised French and English guidance for the optional device UUID and the unverified unit.
- Add **Configure → Diagnostics and logging** with ERROR / WARNING (default) / INFO / DEBUG. This is a shared Trybatec logger threshold on the Home Assistant instance, and is applied without reloading the integration when that is the only option changed.
- Add sanitized INFO/DEBUG diagnostics identifying portal fetch stage, elapsed time and number of meters, without response bodies, usernames, raw readings or tokens.
- Regression tests for Home Assistant's actual options-flow manager, blank-menu recovery navigation, API-first defaults, and logging option updates.

**Validation boundary:** Tests use simulated Home Assistant and invented meter data; real Trybatec API failures and future self-updating in the user's Home Assistant are not confirmed by CI.

---

# 0.2.0b8 — Unit confirmation recovery and actionable history review

**Experimental prerelease.** This update does not authorize historical Recorder imports or modification of Energy configuration.

## Fixes
- Confirming a unit for a physical meter now updates the active coordinator from the last successful bounded index response, without unloading the entire integration or sending another portal request. Saves with an unchanged/empty optional device UUID mapping no longer force reloads. A new verified meter entity is registered with its distinct stable identifier; the prior unverified entity stays without a usable index, avoiding accidental statistic reuse or double counting.
- Malformed previously saved unit overrides no longer prevent live meter polling: invalid overrides are ignored safely, with an error log and unverified index units.
- A failed initial portal fetch remains a retryable setup failure, rather than silently accepting unverified data. The sanitized exception category is logged without vendor payloads or credentials.
- Historical-review navigation no longer terminates in a bare error dialog when the integration is unavailable, the preview is missing after a restart, or the selection has expired. Each state has a clear explanation, a return-to-menu option and direct in-app links to Developer Tools → Actions and/or Trybatec logs.
- An actual preview with no flagged readings is explicitly distinguished from a missing preview; persisted review decisions remain unchanged.
- Annual monetary estimates no longer declare the unsupported Home Assistant MEASUREMENT state class; entity IDs remain unchanged.
- Additional synthetic Home Assistant runtime and UI regression tests cover options-save lifecycle, restart with confirmed units, invalid existing overrides and navigation.

**Limits:** The underlying cause of the user's live Trybatec API failure has not been confirmed without HA traceback. Vendor API connectivity and response format remain outside CI coverage. No real vendor data or production Recorder is used in these tests.

---

# 0.2.0b7 — Historical diagnostics, cost estimates and import safeguards

**Experimental pre-release.**
Publication of this beta does not approve production historical import, change Energy settings or modify any Home Assistant installation.

### Changes from b6

- Read-only diagnostics for sparse intervals, declining/conflicting indexes,
  overlapping or replaced physical meters, and unverified source units.
- Read-only annual historical cost estimates in EUR with physical-meter
  isolation and separate, explicitly authorized accounting allocations.
- Explicit water index conversion (L and m³ to m³), thermal conversion
  (kWh, MWh and GJ to kWh), and refusal of missing, conflicting or incompatible
  source units. Chart display units do not certify raw meter index units.
- Fix annual energy/water YTD estimate sensor state classes: no misleading
  `measurement` statistics for annually resetting or revisable estimates.
- Protect `retry_pending`: immutable source and approved plan fingerprints
  prevent requeueing if the vendor supplies changed source readings or
  import parameters. Unfingerprinted pre-existing pending entries require
  verification rather than blind retry.
- Harden Recorder readback: mismatched, missing and ambiguous duplicate
  hourly buckets cannot be marked verified. An import returns a pending state
  until explicit `verify_history` confirms every expected statistic.
- Expanded synthetic unit, Recorder SQLite, HA process-restart and
  multi-meter interruption tests. No test interacts with a real vendor account.

### Migration / cautions

- Back up Home Assistant configuration, Recorder and `.storage` before any
  attempted import; verify access to restoration material and keys.
- Existing b5/b6 statistics are not deleted or migrated automatically.
  Do not use two generations of the same usage simultaneously in Energy.
- Confirm each real meter's index unit and review each abnormal historical
  reading before accepting an import. Manual confirmation is required.
- Simulated failure tests do not establish transaction-level crash recovery
  inside the Recorder SQLite thread. Costs remain estimates rather than
  approved building charges.
- Publication requires explicit authorization and passing all release gates.

---

# 0.2.0b6 — Per-meter units, Recorder verification and historical preflight

Experimental pre-release. Back up Home Assistant, including Recorder and .storage, before import.

- Explicit source units: recognize known unit fields if Trybatec returns them. No assumption that those fields actually exist on every account. If absent, require a manual unit per physical meter (also for old meters visible in the history preview).
- Water: m³ or L → m³. Thermal: kWh, MWh or GJ → kWh. Incompatible and conflicting units remain unavailable; old global heating-unit setting is no longer used.
- Separate b6 meter entity IDs and history_v5 statistic IDs; no automatic migration, deletion or Energy dashboard switching. Do not select multiple generations of the same usage in Energy.
- Import stages a pending journal before Recorder queueing, blocks blind reimports and provides administrator action trybatec.verify_history. It checks every expected hourly bucket and sum against recorder.get_statistics. This verification is a separate step after Recorder processes the queue; import is not atomic.
- Added per-meter unit UI and graphical read-only history overview. Displays possible replacements and overlaps without merging different physical meter histories.
- Improved test coverage for missing/conflicting units, multiple lots, pending journals and recorder bucket verification.

Remaining limits: no evidence that the undocumented Trybatec API exposes unit metadata, no full-page bulk review editor, no automated Energy dashboard migration, no production proof across multiple Trybatec accounts. Installing or updating never automatically writes historical statistics.

## Fix included in b7: Home Assistant annual sensor state classes

- Corrects the runtime warning: annual estimated cold/hot-water usage had device class `water` and heating usage had `energy`, but all three incorrectly used `state_class: measurement`.
- YTD estimated usage now declares no state class: a revision or calendar-year reset must not be misinterpreted as a continuous meter statistic.
- Verified physical meter index sensors continue to use `total_increasing`. Existing entity IDs and Recorder history are not rewritten by this fix.
