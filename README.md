# Trybatec for Home Assistant — UNOFFICIAL / EXPERIMENTAL BETA

<p align="center">
  <img src="custom_components/trybatec/brand/icon@2x.png" alt="Unofficial Trybatec Home Assistant integration icon" width="128" height="128">
</p>

**Current experimental beta: 0.2.0b4** — per-reading review in Home Assistant options, separate approved accounting allocations, and controlled recorder revision handling. Available as a GitHub pre-release; back up Home Assistant before any import.

**FR :** Intégration Home Assistant non officielle pour compteurs intégrés au portail Trybatec (eau froide, eau chaude, chauffage). Bêta expérimentale sans maintenance garantie.

**EN:** Unofficial Home Assistant integration for meters available via the Trybatec portal (cold water, hot water, heating). Experimental beta; maintenance not guaranteed.

[Français](#installation-fr) · [English](#installation-en)

> **EXPERIMENTAL BETA — UNSUPPORTED / MAINTENANCE NON GARANTIE.** The service endpoints were identified from the
> authenticated consumer portal, **not from a published Trybatec API contract**.
> They may change. This project is not affiliated with Trybatec, Home Assistant,
> HACS, or OpenAI. Test with your own account before using it for monitoring.

## Features

- User-interface setup with a portal username, password, and `dealId` obtained
  from the URL of the account's **Indexes** page (`/indexes/<UUID>`).
- Automatic `POST /api/v1/authenticate` and `GET /api/v1/indexes`, using an
  in-memory Bearer token. A rejected token is automatically retried once.
- Discovery of active EF (cold water), ECS (hot water), and CET (heating)
  meters. Each **physical meter serial number** has its own cumulative-index
  sensor; a replacement does not overwrite the old counter's statistics.
- Year-to-date consumption **estimates** based on the portal's `conso` field.
- Optional accounting tariffs, distinguished as `provisional` or `approved`,
  providing annual unit-price and year-to-date **estimated** cost sensors.
  When the current year's rate is unknown, the newest prior **approved** rate
  is used as an explicit fallback (otherwise the latest provisional rate).
- Default poll interval: 12 hours; minimum: 1 hour.
- Supports UI translations for French and English.
- Water-only installations are supported. Current-year fluid metric sensors are created only for fluids whose active meters are actually present.
- Historical readings handle one meter, successive physical meters, parallel meters, multiple dwellings, and sparse/backdated-looking observations without client-specific assumptions.

## Historical readings and Home Assistant recorder (proposed `0.2.0b4`)

**EXPERIMENTAL. NO AUTOMATIC RECORDER WRITES.** Back up Home Assistant
**including Recorder and `.storage`** before importing. No history is imported
on install, restart, update or daily polling. History actions require an
**authenticated administrator** and deliberate confirmation.

### Review historical data in the integration user interface

1. In **Developer Tools → Actions**, execute **`trybatec.preview_history`**
   with the widest credible start date. This read-only action returns
   `review_candidates` for long intervals, decreases and disputed source
   readings. It also caches the candidate list in memory for your account.
2. Open **Settings → Devices & services → Trybatec → Configure → Review historical
   readings** (*Paramètres → Appareils et services → Trybatec → Configurer*).
   Select a source reading belonging to the configured account/lot and choose:
   - **Accept unchanged:** retain source reading; this does **not** magically
     make a year-long interval a known daily consumption.
   - **Correct and accept:** select **actual measurement date** (with a
     supporting explanation), or **accounting attribution date/time** (only a
     convention for the amount observed between two indexes). Choose date and
     time in the local Europe/Paris timezone. Ambiguous/nonexistent local
     times during daylight-saving transitions are rejected.
   - **Exclude:** remove that exact source reading from subsequent import
     calculations, preserving the source and the surrounding safe intervals.
   - **Postpone:** similarly exclude the reading until the decision is revised.
3. Confirm the selected action on a separate screen. Choices are preserved
   locally with an audit timestamp and justification, keyed to a hash of the
   exact source reading (account store + lot + fluid + serial + timestamp +
   value). When Trybatec changes the source timestamp or value, the old choice
   does **not** apply blindly. The source portal is never modified.
4. **Run `preview_history` again** after a decision to inspect the effect.
   The preview action never writes to Recorder or persistent storage itself.
   The review interface stores choices in `.storage`; back it up with Recorder.

**Limit:** This is a native Home Assistant *options flow*, not yet a custom
full-page dashboard. A review requires a preceding preview to populate
candidates; a new preview is required after each saved choice. Only flagged
readings are selectable. The source API has no documented provenance flags,
so neither a backdated-looking entry nor a correction is called "manual" without
independent evidence. Text justification is requested but not verified by code;
no file upload or automatic proof verification is included.

### Explicit import controls

`trybatec.import_history` is still an opt-in administrative action. Run it
only after backing up and reviewing the preview. Use `confirm: true`.

- **Water-only accounts and accounts with no heating work:** absent fluids
  are skipped. You may disable cold or hot water separately with
  `include_cold_water` and `include_hot_water`.
- **Measured near-daily intervals** (up to 27 h, including DST changes) are
  stored in distinct per-physical-meter `history_v4_..._daily_...` series. Sparse
  intervals are NOT interpolated into fictitious daily consumption. A small
  index decline isolates uncertain increments without losing the whole meter.
  Contradictory readings are isolated; a fundamental identity collision
  prevents unsafe import of that meter.
- If the account has sparse intervals, set `allow_gaps: true` to explicitly
  permit a **partial measured-daily import**.
- **User-approved accounting allocations** of sparse consumption are stored
  in **separate** per-meter `history_v4_..._accounting_...` series, never made to
  look like measured daily usage. Opt in with `include_accounting: true` and
  `confirm_accounting: true`. The allocation timestamp must lie inside the
  observed source interval, and the amount is calculated as a verified
  nonnegative difference between two source indexes. For instance, a
  deliberate **31 Dec 23:59** selection is recorded into the **31 Dec 23:00**
  local hourly statistics bucket, not the following civil year.
- **Heating is OFF by default**. It can be imported only after independent
  confirmation of genuine kWh (not heating allocation units) using
  `include_heating: true` and `confirm_heating_kwh: true`.
- **Multiple serial numbers** stay separate even if they may be successive
  physical generations of a single lot's consumption point. Overlapping
  meters are never assumed to be successive.
- **Idempotent re-imports and later extensions:** when all previously written
  rows are unchanged, an identical re-import or append uses the same v4
  statistic ID. Backfills/corrections that would alter previous cumulative
  sums are rejected unless `confirm_revision: true`; then a **NEW versioned
  statistic series** is created and the old one remains untouched.
  **The user must manually replace the old series in the Energy dashboard**
  before using the new revision. Do NOT select old and new simultaneously.
- The import returns the queued series, skipped meters and any replaced old
  IDs. Queueing external statistics is asynchronous; verify persistence in
  **Developer Tools → Statistics** after the recorder has processed the data.

### Restrictions and known limits

- The new `history_v4_` statistics deliberately do not overwrite or migrate
  previous `history_...` or `history_v3_...` Recorder statistics. Using multiple
  generations of the same consumption in Energy may double-count it.
- A single annual interval's total can be attributed **by convention** to a
  chosen end-of-year bucket, but this never proves that the energy/water was
  consumed on that day. Keep accounting allocations distinct from daily use.
- The Trybatec `/api/v1/indexes` API is undocumented. Historical access is
  limited to 10 years per request with API and payload-size limits. Some
  vendor accounts may expose only partial or inconsistent history.
- The live/current sensor representation still uses serial-only identity;
  duplicate serials across different lots are isolated in historical
  statistics but not yet fully handled in live sensors.
- No complete CSV/XLSX ingestion, automatic conversion of sparse intervals
  to daily readings, provenance audit of source documents, full graphical
  bulk review, or automatic switching of revised Recorder statistics in the
  Energy dashboard is implemented.
- No broad live customer-account testing has been performed beyond a limited
  account preview. Synthetic tests are not a replacement for end-to-end testing.

## Logo / identity

The user-selected symbol (water, hot water and heating) is distributed locally as `custom_components/trybatec/brand/icon.png` (256×256) and `icon@2x.png` (512×512), following Home Assistant 2026.3+ custom integration branding rules. It is an independently designed, unofficial integration icon, **not** the Trybatec corporate logo and not an endorsement.

Preview action results may contain physical meter serials and index values. Redact this information before posting logs or screenshots publicly.

## Limitations / safety

- **Not production-validated:** only a limited live-account preview was inspected; no broad Home Assistant runtime or
  service contract was available for automated end-to-end tests. The format is
  based on a redacted, verified capture of the portal API response.
- **Historical 2021–2025 live-sensor backfill is not implemented:** the historical import creates distinct per-meter external recorder statistics. Historic rates
  can be stored, but current cost sensors use the **current civil year** only.
- Year-to-date consumption is **not an audited accounting statement**. Missing
  telemetry, corrections and replaced meters can affect the portal-reported
  `conso` field. Inspect the `coverage_warning` attribute. Accounting costs
  can also include fixed charges and distribution rules not represented here.
- Accounting figures may be disputed or incomplete; actual rates are **never
  included in this public repository**. Enter your own verified rates.
- Some building accounts express heating in **allocation units**, not kWh.
  **Do not enter such rates as EUR/kWh without confirming equivalence**.
- The underlying service is a cloud portal; this integration does not enable
  local sensor readings or operation when Trybatec is offline.
- Credentials are stored in the Home Assistant configuration entry (protected
  by Home Assistant's access controls, but included in its backups). A login
  token remains in memory. Avoid publishing logs, screenshots, or backups with
  sensitive information.
- This is an observed, **unofficial** web endpoint; verify any relevant portal
  terms and avoid excessive polling or unauthorized access.

## Installation (FR)

**Installation conseillée depuis GitHub (préversion)**

1. **Effectuer une sauvegarde complète de Home Assistant.**
2. Dans Home Assistant **2026.11 ou plus récent**, aller dans **Paramètres → Marketplace → Ajouter depuis un lien (Add from link)**. Sur une version plus ancienne, utiliser **HACS → Dépôts personnalisés**.
3. Ajouter l’URL de ce dépôt GitHub (de type **Intégration**).
4. Ouvrir ce dépôt dans Marketplace, puis activer **Pre-release / Préversions** dans les options du dépôt pour voir les versions expérimentales.
5. Installer la préversion voulue, puis ajouter **Trybatec (Unofficial Beta)** dans **Paramètres → Appareils et services**. Redémarrer Home Assistant si l’interface le demande.
6. Renseigner ses propres identifiants et son UUID de copropriété, sans jamais les transmettre dans GitHub.

**Installation manuelle de dépannage**

1. **Effectuer une sauvegarde complète de Home Assistant.**
2. Copier `custom_components/trybatec/` vers `<CONFIG>/custom_components/trybatec/`.
3. Redémarrer Home Assistant.
4. Ouvrir **Paramètres → Appareils et services → Ajouter une intégration → Trybatec (Unofficial)**.
5. Renseigner l'identifiant et le mot de passe utilisés sur le portail Trybatec.
6. Renseigner l'**UUID de la copropriété** visible dans l'URL de sa page *Index*
   (`https://portail.trybatec.fr/indexes/<UUID>`). Il n'est **pas** nécessaire
   de transmettre cette URL à un tiers.
7. Dans les options, définir un intervalle d'interrogation et, si souhaité,
   un tableau de tarifs JSON.

**Ne pas copier d'identifiants, de jetons JWT ou de données personnelles dans
GitHub.** La sauvegarde de `<CONFIG>` doit protéger le contenu des entrées de
configuration, y compris les mots de passe.

### Tarifs historiques

Configuration optionnelle dans les **Options** de l'intégration :

```json
{
  "2025": {
    "EF": {"rate": 5.0, "status": "provisional"},
    "ECS": {"rate": 12.0, "status": "provisional"},
    "CET": {"rate": 0.08, "status": "approved"}
  }
}
```

**Montants ci-dessus fictifs**, uniquement pour montrer la syntaxe. Pour une
année, chaque taux utilise les unités `EUR/m³` pour EF et ECS et `EUR/kWh` pour
CET. `status` vaut `provisional` ou `approved`. Les tarifs d'une année civile
sont réutilisables à titre de référence, mais ce premier prototype ne recalcule
pas rétroactivement l'historique du recorder Home Assistant.

### Capteurs

Pour chaque compteur **actif** : un index `total_increasing` en m³ ou kWh,
avec une identité stable dérivée du numéro de compteur. Pour chacun des trois
fluides : trois capteurs supplémentaires (consommation annuelle estimée,
coût annuel estimé, prix unitaire de l'exercice en cours). Une consommation
annuelle n'est pas supposée exhaustive lorsqu'il manque des relevés.

Les compteurs remplacés conservent leurs anciens identifiants HA. Vérifier les
changements de compteur avant de configurer le tableau de bord Énergie.

## Installation (EN)

Copy `custom_components/trybatec` into your HA configuration directory, restart,
and add **Trybatec (Unofficial)** from **Settings → Devices & services**. Supply
portal credentials and the UUID from the Indexes page URL. Add optional annual
prices in the integration options (see example above).

## Maintenance and support / Maintenance et assistance

**English:** This is a community-developed, experimental project provided **as
is**, without any commitment to ongoing maintenance, technical support,
compatibility updates, security patches, or response times. **The repository
owner may not maintain the project**, and contributions or issue reports do not
create an obligation to deliver fixes. Automated CI checks, when enabled, can
identify some problems, but **do not guarantee that anyone will investigate or
resolve them**. Future Home Assistant or Trybatec changes may break the
integration. Use at your own risk; contributions from the community are welcome
and may be reviewed on a best-effort basis.

**Français :** Ce projet communautaire expérimental est fourni **en l'état**,
sans engagement de maintenance, d'assistance technique, de suivi de
compatibilité, de correctifs de sécurité ni de délai de réponse. **Le
propriétaire du dépôt GitHub ne s'engage pas à assurer la maintenance**.
L'ouverture d'un ticket ou la proposition d'une contribution ne garantit pas
qu'une correction sera apportée. Les tests automatiques, lorsqu'ils sont
activés, ne garantissent pas qu'une personne analysera ou corrigera les
dysfonctionnements détectés. Une évolution de Home Assistant ou de Trybatec
peut rendre l'intégration inutilisable. Les contributions sont bienvenues,
avec examen éventuel selon les disponibilités.

## Developer notes / GitHub publication

`manifest.json` currently targets the intended repository `christophejaubert/ha-trybatec`. **Before publishing this repository to GitHub**:

1. Create that exact public repository (or update `manifest.json` to match the final owner/repository name).
2. Confirm that `documentation`, `issue_tracker` and `codeowners` in `manifest.json` point to the real repository and owner.
3. Run unit tests, syntax checks, and **Hassfest/HACS checks**, add repository
   topics, a real release, a compatible logo/brand asset as required by the
   current HACS publisher documentation, and enable issues.
4. Verify API behavior for at least two **consenting** accounts, including
   auth failure, downtime, missing readings and counter replacement.
5. Review the service's terms before distributing automated access code.

The repository includes CI for pure parsing tests plus a scheduled installation
and import check against the **latest published Home Assistant release**.
CI does **not** prove that a private Trybatec account keeps working or that a
HA upgrade will not introduce behavioral changes. The maintainer must inspect
failures and issue updates as needed.

## AI-assisted development disclosure

This software was developed with the assistance of **ChatGPT (OpenAI)** under
the direction of the repository owner. This is an independent community project,
**not** endorsed, officially authored, supported, or maintained by OpenAI.
**Neither OpenAI nor the repository owner commits to ongoing maintenance or
support.** AI-assisted code requires independent human review, security testing,
and licensing review before production use.

Ce logiciel a été développé avec l'assistance de **ChatGPT (OpenAI)**, sous la
direction du propriétaire du dépôt. Ce projet indépendant n'est ni affilié,
ni approuvé, ni officiellement développé, ni maintenu par OpenAI. **Ni OpenAI
ni le propriétaire du dépôt ne garantissent la maintenance ou l'assistance.**

## License

MIT — see [LICENSE](LICENSE).
