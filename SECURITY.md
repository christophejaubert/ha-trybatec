# Security policy

**No guaranteed security maintenance.** This experimental community project
is provided as is. The repository owner does not commit to reviewing or fixing
reported vulnerabilities, issuing security releases or meeting response times.
Do not rely on this integration for safety-critical monitoring.

**Aucune maintenance de sécurité garantie.** Le propriétaire du dépôt ne
s'engage pas à corriger les vulnérabilités, à publier des mises à jour ni à
répondre aux signalements dans un délai donné.

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
- Vulnerability reports: if GitHub private vulnerability reporting is enabled,
  use it rather than a public issue. Submission does **not** guarantee review,
  a reply or a fix.
