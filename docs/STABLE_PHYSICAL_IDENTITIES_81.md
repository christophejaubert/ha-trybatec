# Issue #81 — stable physical-meter identity: implementation gate

**Status (2026-11-12):** phase A, review-only implementation on a dedicated branch. No registry migration, new runtime identity selection, Recorder import, Energy change or Home Assistant production write is implemented or authorized by this patch.

## Verified baseline

- In `sensor.py`, current b6 live meter `unique_id` includes the verified source unit (or `unverified`), which intentionally isolated historical statistics with assumed units.
- `migration_runtime_b15.py` supports an existing separately confirmed b15 migration and b17 coexistence. Its checks must **not** be bypassed by changing the generator in `sensor.py`.
- Physical meters, retired physical-meter snapshots and versioned Recorder statistics are distinct identities. A meter-unit change is not a physical meter replacement.

## Implemented in this PR (phase A)

The pure `meter_identity.py` helper:

1. Derives a canonical SHA-256-based ID from the exact *account scope, lot, fluid and physical serial*, excluding source unit and release string.
2. Recognizes known b6 legacy identity forms (including the collision suffix) without treating a suffix or friendly name as proof of ownership.
3. Declines to attribute an unscoped serial-only legacy ID to any one lot when that serial is reused.
4. Computes an immutable, read-only compatibility inventory and marks foreign owners, multiple legacy generations and coexistence as blockers.
5. Never edits the entity registry, local settings, devices, statistics, Energy selections, dashboards or automations; absent registry entries do not prove absent historical statistics.

The helper is intentionally **not yet wired into sensor creation**. Existing IDs and statistics retain their present behavior. This staging prevents a seemingly harmless code change from implicitly reusing Recorder history of another scale.

## Next implementation phases before enabling new IDs

### Phase B — HA runtime preflight and greenfield selection

- Verify account/config-entry scope and canonical physical identity against the HA device/registry entries.
- Audit presence of existing Recorder statistics and Energy references, including unscoped legacy IDs, before deciding whether a genuinely **new** installation may register a stable ID.
- Store durable evidence of the first verified source unit or an equivalent independent baseline: otherwise a subsequent unit correction across HA restart could reuse a stable statistic ID with incompatible historical scale.
- Keep a meter with no verified unit visible without producing misleading long-term statistics. Updating unit metadata must not create a second entity.
- Reject source-unit corrections whenever persisted statistics cannot be reconciled, rather than resetting or silently reinterpreting cumulative values.
- Handle restoration and restart, temporary API errors, multiple lots/accounts, duplicate serials, physical replacements and truly unavailable data.

### Phase C — explicit migration of existing identities

- Build a **read-only** source→target plan with exact registry ownership/device identity, all known references and raw vs canonical unit metadata.
- Require a recoverable HA/Recorder backup, explicit confirmation and a before-state fingerprint; prohibit any implicit deletion or reassignment of occupied entity IDs.
- Verify after write, support interrupted/resumed execution, and retain a rollback snapshot.
- Preserve all b6/b15/b17 Recorder series and verify one consolidated source per fluid in Energy, in coordination with #36/#37.
- An incomplete Recorder/automations/dashboard dependency inventory prohibits cleanup; a zero warning count is not proof of safety.

### Phase D — CI and business acceptance

- Unit/identity/compatibility test matrix with synthetic fixtures; Python and HA integration tests on the *exact* PR commit; HACS/hassfest/security/CI.
- Production **read-only** inventory before any migration, then independent authorization for any real write.
- Manual Home Assistant acceptance (UI, restore, ID continuity, Recorder, Energy) is separate from successful CI.
- Before publication, confirm that the new runtime path is actually integrated, not just previewed.

## Deployment / migration rule

**Do not merge or publish this as a completed #81 fix.** Phase A is an implementation foundation and does not change current generated IDs. Keep the PR in draft until remaining phases, validations and a deliberate migration strategy are complete.

References: [#81](https://github.com/christophejaubert/ha-trybatec/issues/81), [#37](https://github.com/christophejaubert/ha-trybatec/issues/37), [#36](https://github.com/christophejaubert/ha-trybatec/issues/36).
