# 0.2.0b4 — Controlled historical review and safe statistics revisions

**Experimental, unofficial and unsupported.** Published as an experimental GitHub pre-release after automated checks. Back up Recorder **and** `.storage` before any import.

- Adds an account-scoped **Home Assistant options UI** to review flagged
  historical readings: accept unchanged, correct actual measurement date,
  choose separate accounting attribution time, reject, or postpone. Each action
  needs explicit confirmation; correction requires a written explanation.
- Local persistent decisions are hashed to the exact original reading;
  changed source timestamps/values invalidate stale decisions. Decisions do
  not modify Trybatec cloud records or the Recorder by themselves.
- In read-only `preview_history`, shows candidates and their current decisions.
  A new preview is needed after each saved choice.
- A transient decrease or conflicting vendor reading no longer necessarily
  invalidates all the other daily-safe intervals of the same physical meter.
- Accounting attributions are explicit, limited to source intervals and
  imported only on double opt-in, into **separate statistics** from measured
  near-daily usage. Year-end allocations use correct local hourly buckets.
- Creates new `history_v4` IDs distinct from b1/b2/v3, one per account, lot,
  fluid, physical meter and type of statistic. Identical/repeated data and
  append-only extensions retain IDs; backfills or corrections require an
  explicit revision and use a new versioned ID, retaining the original.
- Supports missing fluids, one meter, multiple successive or parallel meters,
  multiple lots, DST boundaries and account-specific sparse history.
- CI tests cover data isolation, authorization, fallbacks, date controls,
  origin bookkeeping and recorder import safety without real credentials.

**Remaining limitations:** Review is an options flow, not a dedicated full
wizard; no automatic Recorder migration, no file attachment proof-checking,
no automatic Energy dashboard reconfiguration, and no broad customer-account
end-to-end validation. Never add old and revised series simultaneously to
Energy. Installing this release never automatically imports history.
