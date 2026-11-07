# Security policy

This integration communicates directly from the user's Home Assistant host to
`https://portail.trybatec.fr` using HTTPS. It does not use a third-party proxy.

- Never publish credentials, private API responses, housing IDs, meter serials,
  bearer tokens or HA configuration backups in GitHub issues.
- If a JWT appears in a public screenshot, treat it as potentially exposed;
  ask Trybatec support for session/token revocation if required.
- Home Assistant's stored configuration entries contain the portal password.
  Protect backups and limit access to administrators.
- The API endpoints are undocumented. Verify service terms and test limited
  request frequency before using this integration publicly.
- Vulnerability reports: contact the repository maintainer privately using
  a GitHub security advisory **after** the repository is published.

## Historical recorder access (0.2.0b4+, proposed)

Historical preview and import actions require an **authenticated Home Assistant
administrator**. Automated or unauthenticated contexts are refused by design.
Only the explicitly confirmed import may write to recorder or the integration's
`.storage` origin ledger. Historical data are filtered by known dwelling lots,
and all external statistic identifiers hash the account, lot and serial.

The importer places strict limits on incoming Trybatec rows and observations;
conflicting values, meter overlaps and unknown reading dates must never be
silently treated as exact daily consumption. Long intervals are not interpolated.
A failed origin consistency check stops import before any recorder write.

History previews and service responses may expose meter serials and dwelling
lot references to the current HA administrator: **do not post these publicly**.
Persistent origin records and the portal password are included in HA backups.
Do not enable public HA access without authentication, and secure backup files.
Legacy b1/b2 statistics are not automatically removed or converted.

## v4 historical decisions and revisions

Review decisions are persisted in the local Home Assistant `.storage` directory.
The decision key is an exact-source hash that includes the lot, serial, fluid,
source timestamp and index value. The stored data include the choice, any
user-entered justification, date correction and audit timestamp. Administrators
should avoid entering confidential details into justifications; protect and
back up `.storage`. A changed vendor source does not inherit old decisions.

Option-flow controls require an administrator to access integration settings;
the history import actions independently check administrator identity and
explicit confirmation. A separate confirmation is required for accounting
allocations and for any non-append revision to existing statistics.

A failed or interrupted asynchronous Recorder queue may leave a pending
external-statistics write. Re-running an unchanged import is designed to be
idempotent, but the user must check actual Recorder persistence before trusting
any totals. Backfilled revisions create distinct external series and never
silently delete the old one. Switching the Energy dashboard remains manual.

## 0.2.0b5 safeguards

SHARKY 774 energy unit must be confirmed per physical meter; no automatic
assumption of source kWh, MWh or GJ. Raw unverified CET live readings are not
published as eligible energy statistics. Live identities include account, lot,
fluid and serial; previous legacy entities are not silently reassigned.
Review decisions are durable and raw historical API payloads are cached only
in RAM. Recorder audit is read-only and requires an authenticated administrator.
A queued import is not considered verified before an audit confirms persisted
statistics. Audits do not make Recorder transactions atomic.
