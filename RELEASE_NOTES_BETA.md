# 0.2.0b1 — Experimental historical-data beta (2026-11-07)

**Experimental. Backup Home Assistant including the recorder database before using historical import. No guaranteed maintenance or support.**

- Adds `trybatec.preview_history` (read-only review of available past indexes and anomalies).
- Adds `trybatec.import_history`, which requires explicit `confirm: true` to queue **isolated external** Home Assistant long-term statistics; no automatic import or database changes on startup.
- Supports meter replacements, duplicate observations, missing intervals and index-decrease validation. No interpolation, no fabricated consumption; external history does not overwrite live sensor statistics.
- Includes cold/hot water by default. Heating historical import is blocked without explicit confirmation that the underlying unit is kWh.
- Uses separate anonymized series IDs and filters by current configured dwelling lot(s).
- **Limitations:** API history availability and compatibility remain unverified in live accounts; CSV/XLSX fallback and automatic ongoing historical synchronization are not implemented. Preview and verify first.
- 31 local tests before publication. Functional live Home Assistant recorder import requires post-installation validation.

Independent, unofficial Trybatec project developed with the assistance of ChatGPT (OpenAI). Not affiliated with Trybatec, Home Assistant or OpenAI. Maintenance, support, security fixes and future releases are not guaranteed.
