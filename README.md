# Trybatec for Home Assistant — UNOFFICIAL / EXPERIMENTAL BETA

<p align="center">
  <img src="custom_components/trybatec/brand/icon@2x.png" alt="Unofficial Trybatec Home Assistant integration icon" width="128" height="128">
</p>

**Version in `main`: 0.2.0b16** (after this PR is merged). The earlier b15 version was integrated through [PR #38](https://github.com/christophejaubert/ha-trybatec/pull/38). Check [GitHub Releases](https://github.com/christophejaubert/ha-trybatec/releases) for actual published versions; merging does not create a tag or release. No publication authorizes historical imports on a real Home Assistant instance. Back up Home Assistant before any separately approved import.

**FR :** Intégration Home Assistant non officielle pour compteurs intégrés au portail Trybatec (eau froide, eau chaude, chauffage). Bêta expérimentale sans maintenance garantie.

**EN:** Unofficial Home Assistant integration for meters available via the Trybatec portal (cold water, hot water, heating). Experimental beta; maintenance not guaranteed.

[Français](#installation-fr) · [English](#installation-en)

> **EXPERIMENTAL BETA — UNSUPPORTED / MAINTENANCE NON GARANTIE.** The service endpoints were identified from the
> authenticated consumer portal, **not from a published Trybatec API contract**.
> They may change. This project is not affiliated with Trybatec, Home Assistant,
> HACS, or OpenAI. Test with your own account before using it for monitoring.

## b16 — First synchronization after HA startup

Trybatec waits until Home Assistant emits `homeassistant_started` before
requesting meter indexes. Sensors are registered after the first successful
vendor response; a temporary first-fetch failure triggers approximately
one-minute retries until data becomes available, then returns to the
configured regular polling interval. An integration reloaded while HA is
already running refreshes immediately. This does not guarantee that the
external Trybatec API is always available.

## b15 experimental capabilities — opt-in; production acceptance pending

**Merged in [PR #38](https://github.com/christophejaubert/ha-trybatec/pull/38).**
The b15 integration supports read-only proposals alongside separately confirmed actions for versioned Recorder imports, Energy preference switching and conservative entity migration. None of these actions run automatically when installing or updating the integration. Passing CI tests does not constitute an acceptance test on the user's production installation.

- Intended stable target: one logical **consumption** series per dwelling and
  fluid; retain separate physical counters and their raw source indexes,
  including deposited counters. Never add physical cumulative indexes.
- Physical counter alternatives: raw daily consumption and explicitly reviewed
  linearly smoothed consumption. Only one alternative per physical counter
  may contribute to a logical Energy series.
- Linear interpolation is **proposal-only**: preserve verified measured daily
  amounts, distribute only the residual across uncovered civil days, and do
  not treat estimated days as measured index readings. Unreviewed zeros,
  changing physical counter, incompatible units and ambiguous overlaps block
  reconstruction. An absent previous index requires an explicit date and
  confirmation of an editable estimated initial index (initial suggestion: 0).
- An Energy preference replacement is prepared as a complete before/after
  preview with a fingerprint of the original settings. The preview never writes
  preferences. The separate activation action requires verified Recorder
  persistence, explicit approval and a complete preference backup; it
  performs a guarded write, readback and rollback on detected failure.
- **Multi-copropriété accounts are not supported in b15's current automatic
  discovery path.** Only one unambiguous authorized dwelling is automatically
  resolved. The explicit portal Index page URL is the controlled fallback.
  Do not enter JSON, Bearer tokens or UUIDs manually during normal setup.
- No historical Recorder import is performed on installation, upgrade or
  startup. Cleaning legacy entities requires separate user-facing migration
  preview, dependency analysis and confirmation.

**Changes introduced in b15 (merged into `main`; consult Releases for publication):**

- **Configure → Review sparse intervals** guides the operator through an
  individual interval, **no smoothing** or **linear residual smoothing**, a
  user-declared manual/telemetry reason, and a **separate confirmation screen**.
  Confirmed source-specific choices are stored locally with an audit timestamp.
  They cannot themselves import Recorder data, alter Energy preferences or
  change vendor measurements.
- **trybatec.preview_history** with
  `preview_linear_proposals: true` includes read-only
  `linear_proposals` and `alternative_series`. The alternative physical
  meter series are raw observed consumption versus observed plus individually
  approved linear gaps. Unverified units, source conflicts, unresolved zero
  readings and stale choices block proposals. Both variants are previews,
  **not automatically imported as Recorder statistics**. Import requires
  `trybatec.preview_b15`, verified fingerprint, a confirmed backup and
  `trybatec.import_b15`, followed by `trybatec.verify_b15`.
- `trybatec.preview_b15` prepares separate raw and smoothed physical
  consumption series plus a single consolidated series for each dwelling and
  fluid. Its fingerprint is validated again after re-fetching vendor data
  before `trybatec.import_b15` queues the new immutable `_vN` revisions.
  A durable pending journal and `trybatec.verify_b15` require **every**
  Recorder bucket to match before marking a version verified.
- `trybatec.preview_b15_energy` provides the exact Energy preference
  fingerprint and double-counting controls across the full dwelling and
  fluid, including physical alternatives. An administrator may explicitly
  invoke `trybatec.activate_b15_energy`, which records a rollback snapshot,
  writes and verifies the Energy preferences and the version ledger.
  Nothing is changed in Energy during installation or automatically.
- `trybatec.archive_b15_meters` can persist the actual identities and last
  vendor observations of retired physical meters. After a separate integration
  reload, sensors are restored as **historical-only**, without increasing
  consumption statistics. No fictional raw indexes are created.
- `trybatec.preview_b15_migration` and `trybatec.apply_b15_migration`
  offer a one-at-a-time technical unique-ID migration only when matching
  physical identity and source units are proven; the existing `entity_id`,
  related UI references and past Recorder rows are preserved. Ambiguous
  legacy objects are intentionally left untouched.

**Validation scope:** all mandatory automated CI checks passed for PR #38 and
its merge into `main`. Real Home Assistant acceptance, including restart,
Energy rollback and user-interface checks on a representative installation,
remains distinct from automated CI. Unsafe or unknown legacy migrations require
a separate manual decision. No production Home Assistant was modified by the
PR or its CI. Installation and release never authorize automatic imports or
Energy changes.

## Changes in 0.2.0b6 — Read before historical imports

- **No unit is inferred from a counter model.** The undocumented Trybatec response *may* include an explicit index-unit field; these names are candidates, not a verified API contract. If none exists, set an individual unit for **every** physical meter via **Configure → Verify meter units**, after checking the actual index scale. The former global `heating_unit` option is **ignored** in b6.
- Water EF/ECS indices accept **m³ or L** and are normalized to **m³**. CET accepts **kWh, MWh or GJ** and is normalized to **kWh**. Unknown, unsupported or conflicting units produce unavailable consumption, not an invented unit. Year-to-date summaries are withheld if any contributing meter lacks a verified source unit.
- b6 live sensors use **new entity unique IDs** and historic imports use **history_v5** IDs. Existing b5 entities/statistics are neither migrated nor deleted. **Never select both old and new generations of the same consumption in Energy.** This may require manual Energy configuration and cleanup.
- Use **trybatec.preview_history** to inspect raw vendor readings, per-meter source units and possible replacements. Physical meters remain distinct even when appearing successive. Use **Configure → Historical preview overview** and the review steps to save corrections/attributions.
- Import only via administrator-only **trybatec.import_history** with `confirm: true`, verified units, and other relevant flags. A persistent pending ledger blocks blind reimports. After Recorder processes queued rows, run **trybatec.verify_history** to compare every queued hourly sum with the recorded statistics. A failed or interrupted import remains pending; `retry_pending: true` permits only an identical retrial.
- The UI is still based on native Home Assistant options flows, **not** a full-page bulk history editor. The Recorder importer is still asynchronous and non-atomic. Source and accounting timestamps remain separate.


### b7 — Métadonnées de compteur depuis Trybatec

Une capture réelle de la fiche `device?id=UUID` confirme que l'API retourne les champs `serialNumber`, `fluidCode`, `lot` et **`unite: "KWh"`**. La b7 récupère cette réponse via l'authentification existante, vérifie l'UUID, le lot, le fluide, le numéro de série et, lorsqu'il est présent, le `dealUid`. Elle normalise par exemple `KWh` en `kWh`, et refuse toute identité, unité ou valeur contradictoire.

Découverte de l'UUID : d'abord un UUID explicitement présent dans la ligne d'index ; sinon, tentative bornée via `GET /api/v1/devices?dealId=...` (route **exploratoire, non documentée et non confirmée**). Si cette liste n'existe pas ou ne permet pas une correspondance univoque, **Configurer → Vérifier les unités → Compteur** permet d'indiquer facultativement l'UUID vu sur le portail. La b7 interroge alors la route réellement observée `GET /api/v1/device?id=UUID` ; il n'est plus nécessaire de recopier l'unité de la fiche. Ne pas confondre cet identifiant UUID avec le `deviceId` numérique des consommations journalières.

Les réponses de détail sont mises en cache uniquement en mémoire ; la tentative de répertoire est espacée de 12 heures et les appels sont bornés. Aucune fiche non associée au lot et au compteur demandé n'est utilisée. L'API n'étant pas documentée, la découverte entièrement automatique de tous les compteurs **reste à confirmer sur une installation réelle**.

Les nouveaux champs d'unité des index sont utilisés par les capteurs temps réel, les estimations annuelles et les prévisualisations historiques. Une unité contradictoire ou non vérifiée continue de bloquer l'import plutôt que d'inventer une échelle. Aucun relevé ou historique Recorder n'est importé automatiquement.

### b7 — Traitement des unités source et diagnostics

Le portail Trybatec affiche des unités de **consommation graphique** (notamment m³ et kWh). Ces unités ne prouvent pas que l'index brut fourni par l'API `/api/v1/indexes` utilise la même échelle.

- Le lecteur b7 cherche les champs d'unité *explicites* dans les propriétés de chaque compteur, ses métadonnées d'index et chaque relevé imbriqué. Si différents champs sont incompatibles, la source est signalée comme conflictuelle.
- `trybatec.preview_history` expose pour chaque compteur : `portal_unit` (unité source réellement trouvée, éventuellement nulle), `portal_display_unit` (référence graphique indicative), `source_index_unit_field_paths` (chemins des propriétés portant un nom d'unité, sans leurs valeurs) et `index_unit_status`. Les éventuelles clés d'unité inconnues sont diagnostiquées mais **jamais interprétées arbitrairement**.
- Les résultats `statistics` n'affichent plus `m³` pour un historique EF/ECS dont l'unité source est inconnue : `unit_status` distingue la confirmation de l'index et l'unité de présentation. Les totaux de relevés bruts sont indiqués comme **deltas d'index non normalisés** lorsqu'une unité source manque.
- Cette modification ne déduit pas automatiquement l'échelle de l'index CET à partir du modèle SHARKY ou de l'intitulé `kWh` d'un graphique. Sans propriété API explicite ni vérification manuelle de l'échelle, les statistiques d'énergie demeurent indisponibles. Aucun import n'est réalisé automatiquement.
- **Limite :** les noms exacts des champs de la réponse Trybatec restent non documentés. La présence d'une unité dans l'interface web ne garantit pas qu'elle existe dans les lignes retournées par l'endpoint d'index.

### b7 — Compatibilité des estimations annuelles avec Home Assistant

Les capteurs annuels EF/ECS (`water`) et CET (`energy`) qui présentent des consommations **estimées depuis le début de l'année** n'exposent plus `state_class: measurement`. Ils n'exposent volontairement **aucune state_class** : leurs valeurs sont susceptibles d'être révisées et de revenir à zéro au changement d'année, et ne doivent pas générer des statistiques Recorder de compteurs cumulés. Les capteurs d'**index physiques** vérifiés conservent `total_increasing` ; les séries d'import historique sont gérées séparément. Aucun identifiant d'entité n'est modifié par ce correctif.

### b7 — Aperçu historique simplifié (interface)

L'écran principal de l'aperçu utilise un **menu à deux choix directs**, « Examiner les relevés » et « Retour au menu principal ». Il n'y a plus de case à cocher suivie d'un bouton de soumission. La consultation détaillée des compteurs est accessible séparément depuis **Configurer → Détails des compteurs**. Les choix de navigation ne modifient ni les options ni les données historiques.

Dans **Configurer → Aperçu de l’historique**, la vue principale présente la période et les compteurs, avec des indicateurs agrégés par fluide (nombre de compteurs, lacunes et conflits), sans afficher les dates UTC de chaque compteur dans un paragraphe unique. Un sélecteur ouvre une fiche par compteur, avec ses dates converties dans le fuseau local de Home Assistant (Europe/Paris), son statut et ses anomalies. La fiche permet de revenir à l’aperçu, d’ouvrir la revue des relevés ou de retourner au menu. La navigation en lecture seule ne modifie aucune décision ni aucun index.

Les textes français/anglais utilisent désormais de vrais sauts de paragraphe, sans caractères littéraux `\\n`. Les relevés historiques restent accessibles uniquement après une prévisualisation et les imports Recorder nécessitent toujours une action administrateur distincte.

## Historical b7 development notes (archived)

The paragraphs in this section describe the earlier experimental b7 branch at the time of its development. They are retained as historical implementation notes, **not** as the current release status. Current published version: **b14**; b15 remains in development. No historical data is written automatically.

New administrator-only read-only Home Assistant actions:

- `trybatec.preview_costs` — approximate annual costs in **EUR**, calculated
  **only** from verified daily increments and separately reported,
  explicitly approved accounting allocations. Amounts use the manually entered
  tariff for the exact civil year and fluid. No extrapolation through gaps, no
  previous-year tariff fallback, no fixed building charges and no claim that
  a provisional or even an "approved" tariff means an approved invoice.
  Quantities are normalized using each physical meter's confirmed index unit.
  Unverified or fatally conflicting meters are withheld and itemized.
- `trybatec.diagnose_history` — read-only report of gaps, decreasing indexes,
  conflicting source observations, unverified units, and ambiguous replacement
  overlaps by physical meter and fluid. No index rewriting or presumed
  continuity between replaced meters.
- The Trybatec API client now bounds the maximum received JSON body, meters
  and readings; it retries HTTP 429/500/502/503/504 a limited number of times.
  Permanent errors and unexpected response structures fail safely.
- Both actions accept `start_date`, `end_date` and optional `entry_id` in
  Developer Tools → Actions, require an authenticated HA administrator, and
  do not queue or alter Recorder data. Previewing a ten-year period can issue
  many API requests; use an appropriately narrow date range.

Release publication, installation in Home Assistant and historical imports are separate operations. A published beta does not approve a production import or automatically migrate Energy dashboard statistics.

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
- Water-only installations are supported. Current-year fluid metric sensors are created only for fluids whose active meters are actually present. Estimates with unverifiable meter units are withheld.
- Historical readings handle one meter, successive physical meters, parallel meters, multiple dwellings, and sparse/backdated-looking observations without client-specific assumptions.

## Historical readings and Home Assistant recorder (`0.2.0b6`)

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
4. Each confirmed decision is persisted under Home Assistant storage, and candidates are recalculated in the same review session using the cached source payloads. No repeated vendor requests are needed until the cache is lost (for instance on restart). The source portal is not modified.

**Limit:** This is a native Home Assistant *options flow*, not yet a custom
full-page dashboard. The review fetches a preview if needed when opened, and allows continuing choices without repeated API calls. Only flagged readings are selectable. The source API has no documented provenance flags,
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
  stored in distinct per-physical-meter `history_v5_..._daily_...` series. Sparse
  intervals are NOT interpolated into fictitious daily consumption. A small
  index decline isolates uncertain increments without losing the whole meter.
  Contradictory readings are isolated; a fundamental identity collision
  prevents unsafe import of that meter.
- If the account has sparse intervals, set `allow_gaps: true` to explicitly
  permit a **partial measured-daily import**.
- **User-approved accounting allocations** of sparse consumption are stored
  in **separate** per-meter `history_v5_..._accounting_...` series, never made to
  look like measured daily usage. Opt in with `include_accounting: true` and
  `confirm_accounting: true`. Allocation outside the observed source interval requires an **extra explicit checkbox confirmation** and a justification; source dates are preserved. The allocated amount is a nonnegative difference between two source indexes, not the meter index itself. For instance, a
  deliberate **31 Dec 23:59** selection is recorded into the **31 Dec 23:00**
  local hourly statistics bucket, not the following civil year.
- **Heating is OFF by default**. Each source unit is verified separately for each physical CET meter: kWh, MWh or GJ, converted to kWh. Both `include_heating: true` and `confirm_heating_kwh: true` are required. SHARKY 774 DN 15 does not establish the source unit. Manufacturer: https://www.diehl.com/metering/fr/produits-et-solutions/produits/comptage-de-lenergie-thermique/sharky-774-compact-fr/.
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

- The new `history_v5_` statistics deliberately do not overwrite or migrate
  previous `history_...` or `history_v3_...` Recorder statistics. Using multiple
  generations of the same consumption in Energy may double-count it.
- A single annual interval's total can be attributed **by convention** to a
  chosen end-of-year bucket, but this never proves that the energy/water was
  consumed on that day. Keep accounting allocations distinct from daily use.
- The Trybatec `/api/v1/indexes` API is undocumented. Historical queries
  first request the **entire selected interval**, without a fixed 92-day or
  multi-year ceiling. Oversized, structurally invalid, explicitly rejected
  or timed-out responses are retried in overlapping, progressively smaller
  periods. A persistently unreadable one-day interval rejects the entire
  preview instead of reporting an incomplete extraction as complete.
  Per-response size and structure safeguards remain enabled; the integration
  cannot verify that the vendor returned all readings it possesses.
- Live meter parsing now uses collision-safe internal identities when a serial occurs in more than one lot or fluid. Legacy IDs are retained for non-colliding serials. Inspect previous HA entity registrations if collisions have already occurred.
- Recorder imports are asynchronous and not atomic or verified on queueing. Confirm actual persistence in Developer Tools → Statistics before relying on totals; no automatic migration or Energy dashboard series switch is implemented.
- Review session payloads are cached in memory, but each confirmed decision persists under Home Assistant storage across restarts.
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

### Unités des compteurs (b6)

Dans les options **Vérifier les unités des compteurs**, définir au besoin l'unité **du relevé transmis par Trybatec** pour chaque compteur. L'ancienne option globale `heating_unit` n'est plus appliquée. Vérifier l'unité sur l'afficheur et la mise à l'échelle du portail. Si l'unité reste inconnue, le capteur de consommation est indisponible. **Contrôler les anciens identifiants d'entités et les séries d'historique avant d'utiliser le tableau Énergie.**

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

`manifest.json` currently targets the intended repository `christophejaubert/ha-trybatec`. **For new maintainers and future releases**:

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
