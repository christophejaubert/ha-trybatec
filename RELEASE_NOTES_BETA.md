# 0.2.0b5 — Verified energy units, resumable reading review and Recorder audit

**Unofficial experimental pre-release.** Back up HA Recorder and .storage before any historical write. Installing this update never imports historical readings automatically.

- A Diehl Metering SHARKY 774 DN15 measures thermal energy, but can be configured for kWh, MWh or GJ. This model does not establish the numeric units in the Trybatec portal. Heating units are therefore selected explicitly for each physical meter, and verified values are converted to kWh. Unknown live CET readings remain unitless raw sensor values without energy-statistic eligibility.
- Live physical meter identity now incorporates account, lot, fluid and serial. Existing serial-only entities are not silently repurposed. Users must review their selected Energy/dashboard entities after upgrading.
- Accounting allocations may be moved before or after their source interval with an extra affirmative acknowledgement and a justification. Original source index and time remain unchanged, and accounting allocations remain separate from daily readings.
- Options review can continue through candidates using a RAM cache, avoiding another 24 portal requests after each decision. Review decisions and the saved review period survive restart; source readings are refetched on restart.
- Adds administrator-only, read-only `trybatec.plan_history` for an exact pre-import plan and `trybatec.audit_history` to compare all planned hourly Recorder rows against persisted statistics. An asynchronous queue is not equivalent to a verified import.
- Continues preserving account separation, no automatic meter merging, identity hashing and isolated review state.

**Limitations:** This does not make Recorder writes transactional. An interrupted import may require an audit and re-run. Earlier v1/v3/v4 series remain in Recorder; never select duplicates in Energy. Real multi-customer and Home Assistant UI end-to-end testing remain necessary.
