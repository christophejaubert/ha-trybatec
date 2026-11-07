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

## Historical recorder access (0.2.0b3+)

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
