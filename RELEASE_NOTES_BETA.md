# 0.2.0b3 — Multi-customer historical safety (2026-11-07)

**Unofficial experimental pre-release. Not production-validated. No maintenance or support guarantee.** Back up Home Assistant (including recorder) before any historical import. Upgrading does **not** automatically migrate/import/change existing statistics.

## Historical support for different Trybatec customers

- **No assumed set of fluids:** water-only installations, hot-water-only configurations and sites without heating are supported. Current-year sensors are created only for fluids present among active meters.
- **Physical meter isolation:** historical readings are partitioned by **dwelling lot + fluid + physical serial number**. Distinct lots and distinct physical meters are never silently merged, even if serial strings coincide.
- **One meter or several replacements:** each serial gets its own `trybatec:history_v3_*` long-term statistic series (opaque ID, independent of the requested start date). A multi-meter point is listed chronologically in the preview, including *possible* replacement transitions; overlapping meter windows are flagged as ambiguous and never automatically joined.
- **Sparse/manual historical readings:** an index recorded in an old year is not proof of when it was physically measured. Gaps longer than daily cadence remain visible in the preview as **unallocated consumption** and are NOT interpolated or credited to their ending day/year in the imported statistics. A second annual breakdown groups only intervals wholly within one calendar year, while retaining the old ending-reading summary for comparison.
- **Daylight-saving safe:** accept 23-/25-hour daily intervals. Subhourly readings are not forced into one hourly statistic.
- **Anomalies:** conflicting or decreasing indexes block import of an affected meter by default. Optional `skip_anomalous_meters: true` skips those meters entirely without altering the remaining meters. `allow_gaps: true` allows only a **partial daily-cadence import**; it never reassigns excluded sparse consumption.
- **Missing fluids:** do not block imports of present selected fluids when another requested fluid does not exist.

## Security and safeguards

- `preview_history` and `import_history` now require an **authenticated Home Assistant administrator**; unauthenticated/internal automation contexts are rejected.
- Explicit `confirm: true` is required before any import. **No automatic recorder writing on update, setup, polling, or restart.**
- Before queuing any `recorder` writes, check a versioned **per-account persistent origin record**. Repeat imports with the same physical series must retain the original baseline and cover at least the already imported date range; otherwise reject. This avoids silently shifting cumulative statistics.
- The portal is restricted to known dwelling lots. Raw usernames, tokens, serials and dwelling IDs are never embedded in public statistic IDs or in diagnostic logs. Input sizes are bounded; contradictory API observations are rejected conservatively.
- Imported v3 statistics use new IDs, separate from old `0.2.0b1/0.2.0b2` external series and current live sensors. **Legacy statistics are not deleted or migrated.** Do not add both legacy and v3 series to the Energy dashboard or you would double count consumption.

## Remaining limitations

- The undocumented Trybatec API does not currently provide a verifiable *measurement timestamp vs. historical entry/import timestamp* distinction. The system only **flags** sparse/backfilled-looking intervals and does not assert they were manually entered.
- A chain of successive meters is *not* automatically combined into one logical meter, because overlapping or non-overlapping dates alone cannot prove a replacement. The future graphical wizard should enable evidence-backed matching.
- No CSV/XLS import, no guaranteed automatic historical synchronization, no automatic correction of older synthetic/misdated statistics, no merging with live-sensor statistics, and no historical accounting tariff recalculation.
- Heating allocation units must not be confused with kWh; heat import requires `include_heating: true` **and** `confirm_heating_kwh: true` after independent verification.
- Existing **live** meter sensors still use the legacy serial-based identity; v3's enhanced multi-lot protection applies to the historical import. A rare duplicate-serial collision in live-sensor discovery requires further remediation.
- Importing is opt-in via **Developer Tools → Actions**. Recorder queues are asynchronous and are not equivalent to persisted/verified data. The import state and metadata live in the Home Assistant backup. Test in a non-production instance first.
- Data from one consenting account were used to *review the problem*, while automated tests use only **fictitious** identifiers and synthetic meter readings. No public Trybatec API contract or broad cross-customer end-to-end verification exists.
