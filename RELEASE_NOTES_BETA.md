# 0.2.0b2 — Historical diagnostics and brand icon (2026-11-07)

**Unofficial experimental beta. No guaranteed maintenance or support.** Back up Home Assistant including recorder before any historical import.

- Preview now reports **dates, physical meter serial numbers, old/new index values and differences** for decreases; precise intervals and durations for gaps exceeding three days; and conflicts for the affected fluid.
- Adds **year-by-year observed consumption estimates**, assigning each interval to its ending reading (no interpolation, not reliable for year-spanning gaps).
- Adds `include_cold_water` and `include_hot_water` to `trybatec.import_history` (both enabled by default) to import one fluid independently. Heating remains excluded by default and still requires explicit kWh confirmation.
- Ships the **user-selected original icon** inside `custom_components/trybatec/brand/icon.png` (256 px) and `icon@2x.png` (512 px), for Home Assistant 2026.3+. The README displays the same icon. This artwork does not use the Trybatec corporate logo; the project is not endorsed by Trybatec.
- Preserves the separate external-statistic IDs and requires explicit import confirmation; existing live sensor statistics are not overwritten by historical imports.

**Limits:** The importer still uses actions in Developer Tools, not an integrated graphical wizard. CSV/XLSX import and historical synchronization are not included. Trybatec API history availability and actual home installation behavior are not guaranteed. Preview responses include physical meter serials; do not post unredacted previews in public GitHub issues. Never import unreviewed decreases or unverified heating units.
