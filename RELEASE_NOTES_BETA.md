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
