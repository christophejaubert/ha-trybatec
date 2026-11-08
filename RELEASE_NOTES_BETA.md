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
