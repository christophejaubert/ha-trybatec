# Preuves Énergie L3 / Energy Evidence L3

> Préparation locale pour l'issue #88, sans publication GitHub ni exécution sur Home Assistant.
> Local draft for issue #88; not published to GitHub or run on Home Assistant.

## FR — Contrat et architecture

**Référence de travail :** `main` à `6ebbd7245cbb5bff90c3fb98084a9a78fc47b4b6` (12 novembre 2026). La PR #82 reste indépendante. L3 ajoute exclusivement deux modules autonomes, le test synthétique et ce document. Ne pas modifier `__init__.py`, `sensor.py`, `panel_api.py`, `config_flow.py` ou `coordinator.py`.

- `energy_bulk_evidence.py` valide les instantanés collectés côté serveur, les scopes compte/lot/fluide, le registre B15, les métadonnées Recorder, les références Énergie et les informations de complétude. Il **ne contient aucun appel Home Assistant**. Le résultat comporte `status`, `inventories`, `candidates`, `blockers` et les invariants `writes=False`, `activation_authorized=False`, `prepared_under_assertions=False`, `blocked=True`, `integration_ready=False`.
- `energy_bulk_evidence_ha.py` contient un adaptateur **inactif tant qu'il n'est pas explicitement appelé**. Il exige un utilisateur administrateur authentifié, recontrôlé dans `hass.auth.async_get_user`, ainsi qu'un coordinateur appartenant réellement à l'instance. Il lit le cache courant des compteurs, les enveloppes JSON locales **en lecture stricte** des versions B15, de V5 et des préférences Énergie persistées (comparées à la mémoire), les métadonnées Recorder et des fenêtres limitées de statistiques persistées. Il lit également la version HA et valide le schéma natif `ENERGY_SOURCE_SCHEMA` de HA 2026.11.1 sur une **copie**.
- `preview_bulk_with_l3_evidence(evidence, preferences)` fournit le point de jonction avec `preview_bulk_energy_insertion(...)` de la PR #92. Tous les attributs d'exhaustivité historique et de références concurrentes demeurent explicitement `False` : la fonction vérifie que le plan résultant est `blocked` et que les préférences proposées sont strictement inchangées. Elle n'ouvre aucun chemin d'activation.

### Inventaires : sens exact de « complete »

| Inventaire | Actuellement observé | Exhaustif ? |
| --- | --- | --- |
| Identité courante | Entrée chargée, compte, identifiant de contrat et lot connu, seulement si concordants | Oui pour le lien **courant** vérifié ; pas pour le rattachement historique |
| Compteurs physiques | Lot, fluide, série, statut déposé et unité du cache courant | **Non** : le cache annuel ne prouve pas tous les remplacements passés |
| Registre B15 | Identités logiques, scopes, variantes, versions et états | Oui **à l'intérieur du registre B15 valide**, pas pour l'ensemble des générations historiques |
| Registre V5 | Présence et nombre de séries enregistrées | **Non** : identités/scope physique pas reconstituables avec certitude depuis les seuls identifiants opaques |
| Métadonnées Recorder | `statistic_id`, unité, `unit_class`, `has_sum` | Existence/métadonnées observables ; pas preuve de couverture |
| Données Recorder | Présence de `sum` finie dans quatre fenêtres échantillonnées de 45 jours (environ présent, N−1, N−3, N−5 ans) | **Non** : échantillon positif prouve des données persistées, échantillon vide ne démontre pas leur absence globale |
| Préférences Énergie | `EnergyManager` **déjà initialisé**, état mémoire comparé aux octets JSON persistés sans `Store.async_load` ; conservation des sources tierces | Exhaustif sur les champs connus si empreintes identiques ; **non exhaustif** pour les références de futurs schémas/consommateurs |
| Schéma HA | Version réelle et validation des sources existantes sur copie | Validation limitée au schéma pris en charge : `2026.11.1` |
| Continuité historique et compteurs déposés | Contradictions visibles, absence de série B15 pour un compteur déposé connu | **Non** : aucun graphe de filiation vérifié « tous compteurs historiques → consolidation » |
| Références concurrentes | Versions B15 et références dans les préférences connues | **Non** : V4/V5, anciennes générations de capteurs et consommateurs externes non couverts exhaustivement |

**Attention aux classes :** la métadonnée Recorder d'une série externe de volume est `unit_class="volume"`. Le planificateur #92 attend `recorder_device_class="water"` après adaptation métier. Une unité `m³` et un `has_sum=True` ne prouvent jamais à eux seuls le type, l'existence de données ni leur continuité.

### Frontière de confiance et sécurité

- Ne jamais accepter les déclarations du navigateur comme preuves : l'API de collecte **n'est pas enregistrée**, les snapshots sont des objets internes, le serveur vérifie les rôles. Une future route doit utiliser également `@websocket_api.require_admin`.
- Ne jamais appeler `async_get_manager` seulement pour effectuer cet audit : sa première initialisation peut planifier un enregistrement. Lire uniquement une instance déjà initialisée puis lire directement son enveloppe `.storage/energy` par accès fichier strictement en lecture seule. **Ne pas utiliser `Store.async_load()`**, car HA 2026.11.1 peut migrer les données, renommer un stockage corrompu et créer une issue pendant cette opération. Pour L3, une enveloppe ancienne, inconnue, corrompue ou trop volumineuse reste non vérifiée et intacte.
- Ne jamais appeler `async_save`, `async_update`, `async_add_external_statistics`, `async_request_refresh` ou une méthode du fournisseur. Aucun initialiseur ou événement de démarrage n'est installé.
- Encadrer à 1 Mio les instantanés sérialisés, 1 500 compteurs et séries, 100 versions par série, 500 statistiques, fenêtres de 45 jours. Toute interruption, troncature, dérive de date, contradiction ou modification concurrente demeure un refus.
- Une empreinte B15 ou une version marquée `verified` ne démontre pas que toutes les plages et tous les compteurs physiques ont été vérifiés.
- Le rapport peut contenir des identifiants techniques et des préférences privées : ne jamais le publier dans des logs publics, une PR, un commentaire ou une pièce jointe GitHub. Les tests ne contiennent que des données synthétiques.

### Limites explicites et dépendances

1. **#36 :** absence d'une attestation consultable et stable de la correspondance exhaustive entre chaque fenêtre Recorder et une version consolidée, et des éventuelles séries V4/V5 valides.
2. **#37 :** absence de manifeste complet des compteurs physiques successifs, déposés, chevauchements et rattachements à la consolidation ; la liste du cache courant n'est pas une source d'exhaustivité.
3. **#81 / PR #82 :** en attente d'une interface stabilisée d'identités physiques. Ne pas dupliquer son scanner des consommateurs ni modifier ses fichiers.
4. **#88 :** absence d'inventaire indépendant et exhaustif des références concurrentes, notamment les générations de capteurs et références hors schéma connu, et absence d'accord métier CET→catégorie technique `gas`.
5. **Réalité HA :** l'absence de métadonnées ou de lignes dans une fenêtre consultée n'est pas une preuve d'absence totale. Les actions et permissions du backend dans une installation réelle ne sont pas testées.

### Raccordement futur et phases distinctes

**L6, intégration sécurisée :** après fusion de #82 et livraison des garanties #36/#37, fournir des adaptateurs de provenance exacts, collecter les preuves de filiation/exhaustivité et de références concurrentes, puis exposer une **route de prévisualisation** administrateur protégée avec empreinte, relecture et invalidation en cas d'évolution. Les critères manquants doivent continuer à bloquer. Effectuer une intégration synthétique contre les API Home Assistant et le vrai moteur #92 dans le dépôt.

**L7, transaction séparée :** uniquement après approbation spécifique et recette : verrou de concurrence, sauvegarde récupérable, confirmation explicite, contrôle du schéma et de l'état après préparation, sauvegarde/application, relecture durable, audit et rollback conditionnel ; aucun effacement de source tierce. Conserver les états `writes=False` et `activation_authorized=False` dans L3 et #92. Aucun bouton opérationnel avant L7.

**Tests disponibles :** tests unitaires et intégration synthétique avec doubles HA/Recorder et véritables fichiers JSON synthétiques, dont stockage corrompu, ancienne version et fichier trop volumineux laissés intacts. Les résultats locaux ne sont pas des exécutions CI GitHub et ne démontrent pas une recette métier sur Home Assistant réel.

## EN — Contract and architecture

**Reference:** `main` at `6ebbd7245cbb5bff90c3fb98084a9a78fc47b4b6` on 12 November 2026; PR #82 remains isolated. L3 introduces two new modules, synthetic tests, and this bilingual document. It does not modify the five shared #82 files.

`energy_bulk_evidence.py` is a pure, server-snapshot assessor: no HA imports, network calls, mutations or automatic authorization. It explicitly returns `writes=False`, `activation_authorized=False`, `prepared_under_assertions=False`, `blocked=True` and `integration_ready=False`, plus per-inventory completeness and per-candidate diagnostics.

`energy_bulk_evidence_ha.py` is a **dormant privileged reader**, not a registered websocket or startup hook. It revalidates the user against HA's auth store; confirms the coordinator belongs to the loaded HA instance; reads only existing cached meters, B15/V5 on-disk JSON envelopes, a pre-initialized Energy manager with direct read-only JSON preference comparison, bounded Recorder metadata/persisted samples, and native schema/version. It never calls the supplier or writes state. Crucially, the Energy manager must **already exist**: invoking `async_get_manager` could schedule a settings save on initialization.

`preview_bulk_with_l3_evidence(...)` is an explicit interface to the existing #92 preview. All complete-history, physical-coverage, alternative-exclusivity, and final-schema authorization flags remain **false**, so the result must remain atomic and blocked, with unchanged Energy preferences.

**Proven observations vs unknowns:** current account/lot association; current-year observed physical meters; entries in the B15 ledger; a limited V5 inventory; Recorder metadata (`unit_class="volume"` for external water volume statistics); strictly sampled persisted `sum` rows; live versus persisted Energy preferences; known selected references; exact HA version and existing Energy schema. None of those establishes full historical physical-meter continuity, retired-meter lineage, absence of future/legacy competing references, semantic approval of CET in a `gas` category, or production acceptance. Empty Recorder samples are **unknown**, never global absence.

**Trust and limits:** snapshots are constructed only by authenticated server code, not browsers; a future websocket must also use `@websocket_api.require_admin`. Read operations only (bounded raw `.storage` JSON reads, `recorder/get_statistics`, metadata reads), no implicit initialization, writes, imports, migrations, provider calls or default audit logging. **Never call Home Assistant `Store.async_load()` in L3**: in Core 2026.11.1 it may invoke an on-disk migration, move corrupt storage aside, or create a repair issue. Refuse incompatible, truncated, or corrupt envelopes without modifying them. Bounded inventories, size limits, two-source-snapshot comparison, stale-cache rejection, safe errors and interruptions all fail closed. Never upload real identifiers or Energy preferences to GitHub.

**Dependencies:** #36 must supply authenticated, durable consolidated-series/Recorder continuity proofs. #37 must supply full retired/live physical-meter lineage including overlaps. #81/#82 must provide stable identities, reused rather than reimplemented. #88 must supply a complete competing-reference inventory and separate heating-category approval.

**L6:** connect trusted identity/history evidence adapters after the dependent work, with an administrator-only preview endpoint, recheckable state fingerprints, and synthetic integration against the actual #92 planner and HA APIs. **L7:** a separately authorized, reversible transaction with full backup, concurrency locks, explicit admin confirmation, durable write/readback, audit and guarded rollback; never add an operative button before that stage.

The local synthetic test results do **not** represent GitHub CI, real Home Assistant acceptance, a merged PR or a release.

### Verified source references / Références vérifiées

- [Issue #88](https://github.com/christophejaubert/ha-trybatec/issues/88), [PR #92](https://github.com/christophejaubert/ha-trybatec/pull/92), [PR #91](https://github.com/christophejaubert/ha-trybatec/pull/91), [PR #82](https://github.com/christophejaubert/ha-trybatec/pull/82).
- [HA Core 2026.11.1 — Energy data / schema](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/energy/data.py).
- [HA Core 2026.11.1 — Energy validation](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/energy/validate.py).
- [HA Core 2026.11.1 — authentication](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/auth/__init__.py).

- [HA Core 2026.11.1 — Store read/migration side effects](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/helpers/storage.py).
