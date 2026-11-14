# 🤖 Archive de l'issue #39 avant nettoyage / Issue #39 pre-cleanup archive

> **FR :** Copie de référence historique du corps de [#39](https://github.com/christophejaubert/ha-trybatec/issues/39) relevée le 14/11/2026, **avant réduction des listes redondantes**. Les cases ci-dessous sont seulement des instantanés de l'ancien suivi, **ne constituent pas des gates actifs et ne doivent pas être cochées**. Le suivi actif est dans #39 et les propriétaires ; la traçabilité F dans [REQUIREMENTS_F01_F62_FR_EN.md](../REQUIREMENTS_F01_F62_FR_EN.md).
>
> **EN:** Historic snapshot of [#39](https://github.com/christophejaubert/ha-trybatec/issues/39) before removing duplicate checklists. The old boxes below are **archived text, not live release gates**. Current gates live in #39 and owner issues; F traceability is in [REQUIREMENTS_F01_F62_FR_EN.md](../REQUIREMENTS_F01_F62_FR_EN.md).

---

# 🤖 Phase 1 — Préparation de la première version stable / First stable release readiness

<!-- F01-F62 SCOPE RECONCILIATION 2026-11-14 -->
## 🤖 Arbitrage fonctionnel F01–F62 / Functional scope decisions — 2026-11-14

**FR — Décision de cadrage explicitement autorisée par l'utilisateur (documentation uniquement).** 62/62 exigences examinées : **10 autonomes en première stable**, **6 autonomes en incubateur**, **46 absorbées dans les spécifications propriétaires**. L'absorption signifie déduplication de la spécification, **jamais suppression de fonctionnalité, preuve de test, ni dispense de critère**. Ne **pas** cocher les listes F d'origine sans preuve sur un SHA exact. F01–F62 conservent leurs numéros. Les fonctions différées ne doivent pas être annoncées comme livrées. Ce mandat documentaire n'autorise aucune modification HA, fusion, publication, migration, restauration ou activation.

**EN — User-authorized documentation-only scope decision.** All 62 requirements reviewed: **10 standalone stable**, **6 standalone incubator**, **46 absorbed into owning specifications**. Absorption deduplicates requirement ownership; it **does not delete functionality, prove tests or waive acceptance gates**. Do not check the original F acceptance items without SHA-specific evidence. Keep the F01–F62 IDs unchanged. Deferred functionality must not be advertised as delivered. No HA change, merge, release, migration, restore or enablement is authorized by this documentation update.

| Ref | Décision / Decision | Responsable / Owner | Critère conservé / Retained criterion (FR / EN) |
|---|---|---|---|
| F01 | Stable | F01 / #39 | Authentification d'un compte portail ordinaire, protections renforcées / Ordinary portal-user authentication with strengthened safeguards |
| F02 | Incubateur | F02 / #39 | Plusieurs copropriétés / Multiple condominiums |
| F03 | Incubateur | F03 / #39 | Plusieurs logements ; F54 stable reste limitée au logement configuré / Multiple dwellings; stable F54 covers configured dwelling |
| F04 | Stable | F04 / #39 | Liaison compte/logement/lot/compteur vérifiable / Verified account-dwelling-lot-meter binding |
| F05 | Stable | F05 / #39 | UUID, dealUid et identifiants exacts sans confusion / Exact identifiers and no identity ambiguity |
| F06 | Stable | F06 / #39 | Accès refusé/révoqué, aucune donnée inventée, historique conservé / Revoked/denied access, no fabricated data, history retained |
| F07 | Stable | F07 / #39 | Réauthentification sans perte ni doublon / Non-destructive reauthentication without duplicates |
| F08 | Stable | F08 / #39 | Dérive de schéma API : refus sûr / API schema drift: fail closed |
| F09 | Stable | F09 / #39 | Budgets API, délais, tentatives et taille / Bounded API requests, timeouts, retries and payloads |
| F10 | Incubateur | F10 / #39 | Essais multi-comptes réels différés ; tests synthétiques de sécurité restent requis en stable / Real independent-account tests deferred; synthetic isolation/security tests remain mandatory |
| F11 | Stable | #81 / #37 | Identité physique stable, préservation des anciens IDs jusqu'à migration distinctement autorisée / Stable physical identity; preserve old IDs absent separately approved migration |
| F12 | Stable | #37 | Compteurs déposés et historiques conservés / Retired meters and histories preserved |
| F13 | Incubateur | #37 / #36 | Gestion avancée des successions différée ; pas de delta entre compteurs ni faux index en stable / Advanced replacement workflow deferred; no cross-meter delta or fake reading in stable |
| F14 | Incubateur | #84 / #36 / #81 | Provenance avancée des unités différée ; écritures refusées si unité non vérifiée / Advanced unit provenance deferred; no unverified-unit Recorder/Energy writes |
| F15 | Absorbée / Absorbed | #84 / F14 | Choix explicite par compteur, inconnu possible, origine et persistance / Explicit per-meter choice including unknown and provenance |
| F16 | Absorbée / Absorbed | F40 / #81 / D07 | Conversion et précision contrôlées, aucune réinterprétation implicite / Verified conversions, scale and precision |
| F17 | Absorbée / Absorbed | #36 / #37 | Pas de delta fictif, baisse/reset à qualifier / No invented consumption after reset/decrease |
| F18 | Absorbée / Absorbed | #81 / F11 / F43–F51 / #37 | IDs indépendants des unités et migration non destructive autorisée séparément / Unit-independent IDs and separately approved non-destructive migration |
| F19 | Absorbée / Absorbed | #37 / F06 / F08 / F12 | Absence temporaire ≠ suppression, ni valeur zéro ; retour sans double identité / Missing meter ≠ removed or zero; reappearance preserves identity |
| F20 | Absorbée / Absorbed | #81 / F04 / F05 / F11 / F39 | Différencier collisions techniques et physiques ; pas de fusion hasardeuse / Detect identity collisions; no unsafe merge |
| F21 | Absorbée / Absorbed | #36 / #37 V-04 / F22 / F25 | Conserver bruts datés, compteur, provenance malgré corrections / Preserve raw dated physical evidence through revisions |
| F22 | Absorbée / Absorbed | #36 / #37 V-08/V-09 | Mesuré/corrigé/interpolé/inconnu, provenance et persistance / Measured/corrected/interpolated/unknown with durable provenance |
| F23 | Absorbée / Absorbed | #36 / #37 V-10 / F26 | Qualifier années 2021–2023 et autres années anciennes : bornes, lacunes, compteurs successifs / Qualify 2021–2023 and older dates, bounds, gaps and replacements |
| F24 | Absorbée / Absorbed | #36 / F37–F38 / F35–F36 / F41 | Variantes lissées/non lissées conservées ; consultation avancée régie par F38 / Preserve alternatives; advanced browsing scoped by F38 |
| F25 | Absorbée / Absorbed | #36 / #37 V-09 / F22 | Jamais présenter une estimation comme une mesure ; méthode/bornes/provenance / Never label interpolation as measurement |
| F26 | Absorbée / Absorbed | #36 / #37 / #81 / F17 / F20 / F23 / F39 | Lacunes, overlaps, doublons ; harmoniser parsing.py/history.py pour conflits au même instant / Gaps, overlaps, duplicates; harmonize contradictory same-time readings |
| F27 | Absorbée / Absorbed | #36 / F23 / F26 / F28 | Année civile vs année du relevé final ; réconciliation des totaux / Civil-year vs ending-reading-year totals |
| F28 | Absorbée / Absorbed | #36 / F27 / #37 | UTC, Europe/Paris, 23/25 h, instants ambigus et limites civiles / DST, UTC and local civil-day boundaries |
| F29 | Absorbée / Absorbed | #36 / #88 / F30–F32 | Relecture Recorder post-import : lignes, sommes, unités, empreintes / Post-import Recorder readback and integrity |
| F30 | Absorbée / Absorbed | #36 / #88 / F29 / F31 / F39 | Idempotence, pas de reprise aveugle, conflits/concurrence / Idempotent import, no blind retry |
| F31 | Absorbée / Absorbed | #36 / F29–F30 / #88 | Journal durable des imports interrompus, reprise vérifiée/quarantaine / Durable pending-import journal and safe recovery |
| F32 | Absorbée / Absorbed | #36 / #37 V-07/V-11 / #81 | Sauvegarde récupérable, protection historiques, restauration prouvée avant opération / Recoverable backup, preserve statistics, proven restore when required |
| F33 | Absorbée / Absorbed | #36 / #37 V-05/V-06 / F39 | Série consolidée par logement/fluide, pas de somme d'index inter-compteurs / One dwelling-fluid consolidated consumption, never sum disparate indexes |
| F34 | Absorbée / Absorbed | #37 V-04/V-05 / F11 / F20 / #81 | Identités physiques et données distinctes / Distinct physical-meter identities and records |
| F35 | Absorbée / Absorbed | #36 / #37 V-12 | V1/V2 et versions suivantes immuables et réversibles / Immutable, reversible consolidated revisions |
| F36 | Absorbée / Absorbed | #36 / #37 V-02/V-04 / F24 | Séries par génération physique conservées / Preserve physical-meter alternative history |
| F37 | Absorbée / Absorbed | #36 / F24 / F38 | Deux variantes raw/smoothed par compteur, source intacte / Per-meter raw/smoothed variants with intact source |
| F38 | Incubateur | #36 / F24 | Interface de consultation avancée hors Énergie différée ; stockage et intégrité maintenus en stable / Advanced browsing deferred; preservation/integrity mandatory |
| F39 | Absorbée / Absorbed | #88 / #36 | Une seule série par périmètre Énergie, protéger les sources tierces / Single Energy selection per scope; protect third-party sources |
| F40 | Absorbée / Absorbed | #88 / #81 / #36 / F16 | Unité, classes et statistic_id exacts ; chauffage kWh sans sémantique gaz supposée / Correct HA metadata; no unjustified gas semantics |
| F41 | Absorbée / Absorbed | #36 / #88 / #81 | Commutation non destructive des séries et vérification / Non-destructive, verified series switching |
| F42 | Absorbée / Absorbed | #37 V-05/V-06/V-12 / #36 / #81 | Continuité logement/fluide entre compteurs physiques distincts / Consumption continuity across retired and active meters |
| F43 | Absorbée / Absorbed | #81 / #37 V-01/V-04 | Inventaire générations et entités anciennes / Inventory old generations and entities |
| F44 | Absorbée / Absorbed | #81 | Plan complet de migration en lecture seule / Complete read-only migration preview |
| F45 | Absorbée / Absorbed | #81 | Inventaire des consommateurs externes, références statistiques/tableaux de bord / Dependency and statistics/dashboard reference inventory |
| F46 | Absorbée / Absorbed | #81 | Diff intelligible source→cible et conséquences / Clear migration change preview |
| F47 | Absorbée / Absorbed | #81 | Consentement distinct avant migration / Separate explicit migration approval |
| F48 | Absorbée / Absorbed | #81 / #37 V-07/V-11 | Sauvegarde récupérable préalable / Recoverable backup before invasive change |
| F49 | Absorbée / Absorbed | #81 | Relecture et vérification après migration / Post-migration integrity checks |
| F50 | Absorbée / Absorbed | #81 / #37 V-07 | Restauration réellement éprouvée lorsqu'exigée ; sinon migration bloquée / Demonstrated restoration when required; otherwise block migration |
| F51 | Absorbée / Absorbed | #37 V-01/V-11 / #81 | Nettoyage uniquement après audit exhaustif du périmètre et accord spécifique / Cleanup only after sufficient audit and separate consent |
| F52 | Absorbée / Absorbed | #36 | Persistance des décisions de revue et lissage, provenance, reprise / Durable review and smoothing decisions |
| F53 | Absorbée / Absorbed | #83 / #42 / #84 / #70 | Recette transversale IHM native, parcours complets et sans effet implicite / End-to-end native UI acceptance |
| F54 | Stable | #83 / #84 / #37 / F04 | Consultation des compteurs actifs/déposés du logement configuré ; F03 multi-logements différée / Inspect configured dwelling's active and retired meters |
| F55 | Absorbée / Absorbed | #42 TAR-01–TAR-12 | Formulaire graphique annuel sans JSON ; BLOQUANT pour la première stable / JSON-free annual rate editor; STABLE RELEASE GATE |
| F56 | Absorbée / Absorbed | #42 TAR-06/TAR-07 | Coûts estimés ≠ charges facturées/connues / Estimates distinct from actual documented charges |
| F57 | Absorbée / Absorbed | #42 TAR-03/TAR-08 | EUR, EUR/m³, EUR/kWh, tarif de l'année exacte / ISO EUR and exact-year rates; no silent fallback |
| F58 | Absorbée / Absorbed | #39 S05 / #42 TAR-11 / #83 / #88 | Contrôle admin côté serveur, lecture vs écriture / Server-enforced role separation |
| F59 | Absorbée / Absorbed | #36 / #81 / #88 / #39 S08 | Prévisualisation et confirmation avant décisions persistées/Recorder / Preview and explicit confirmation before persistent change |
| F60 | Absorbée / Absorbed | #83 / #42 / #70 | Parcours FR/EN testés / Tested French-English workflows |
| F61 | Absorbée / Absorbed | #70 / #83 / #42 | Bureau/mobile, clavier/tactile, accessibilité / Desktop/mobile, keyboard/touch accessibility |
| F62 | Absorbée / Absorbed | #39 S02/S03 / #83 / #42 | Erreurs compréhensibles expurgées des secrets et données privées / Clear, redacted errors and diagnostics |

### Protections incompressibles et limites / Mandatory safeguards and limits

- **FR — Sécurité stable malgré incubateur :** F10 n'exempte pas les tests synthétiques de sécurité multi-comptes ; F13/F14 n'autorisent aucun faux delta, index inventé, conversion non validée ou écriture avec unité non vérifiée ; F38 reporte seulement l'interface de consultation avancée et non la conservation des variantes, sources, versions et provenances. F03 multi-logements est différée, mais F54 couvre le logement configuré et ses compteurs actifs/déposés.
- **EN — Stable guards notwithstanding incubation:** F10 does not defer synthetic multi-account security tests; F13/F14 do not allow fictitious deltas/readings, unsafe unit conversions or unverified-unit writes; F38 defers only advanced history browsing, not preservation of sources, versions, alternatives and provenance. F03 multi-dwelling navigation is deferred, while F54 covers the configured dwelling including retired meters.
- **FR — #36 / Recorder :** conserver les relevés sources intacts, classifications observé/corrigé/interpolé/inconnu, provenance/méthode/bornes/approbations, absence de faux zéros, années 2021–2023 et périodes anciennes, années civiles, Europe/Paris et transitions 23/25 h. Séries physiques et consolidées versionnées, relecture exacte des sommes et métadonnées après écriture, journal durable, refus sûr/quarantaine, idempotence, crash/concurrence/écrivain tardif. **Point technique F26 :** dans `parsing.py`, une valeur contradictoire au même horodatage ne doit pas être silencieusement remplacée ; harmoniser avec `history.py` et tester. **Point F27 :** distinguer `annual_by_end` des consommations effectivement attribuables à une année civile. Tests positifs et négatifs requis.
- **EN — #36 / Recorder:** preserve original measurements, observed/corrected/interpolated/unknown classifications and provenance/method/bounds/approvals; no fictitious zero; explicitly cover 2021–2023 and old sparse histories, civil year boundaries, Europe/Paris and 23/25-hour transitions. Immutable versioned physical/consolidated statistics, verified post-write Recorder sums/metadata, durable journal, fail-closed quarantine, idempotence, crash/concurrency/late-writer tests. **F26 code follow-up:** harmonize `parsing.py` with `history.py` so conflicting same-timestamp values cannot be silently overwritten. **F27 follow-up:** distinguish `annual_by_end` reporting from truly attributable civil-year totals. Positive and negative tests mandatory.
- **FR — #37 / #81 :** compteurs physiques successifs distincts ; identifiants indépendants des unités, anciennes références conservées jusqu'à migration séparément autorisée ; inventaire source→cible des consommateurs connus et inconnus, sauvegarde récupérable, restauration réellement éprouvée quand nécessaire, diff et approbation distincts, relecture, rollback, aucun nettoyage si références non qualifiées. Ne pas présumer l'exhaustivité absolue de l'historique fournisseur ; limiter le refus au périmètre réellement contradictoire.
- **EN — #37 / #81:** separate physical generations; unit-independent IDs, preserve legacy references until separately authorized migration; source-to-target inventory including unresolved dependencies, recoverable backups and demonstrated restoration where required, preview, separate approval, readback/rollback, no cleanup without verified dependencies. Do not demand impossible global supplier completeness; fail closed on selected-scope conflicts.
- **FR — #88 / Énergie :** une unique série pertinente par logement/fluide, exclusion des variantes concurrentes et du double comptage ; unités et classes vérifiées, chauffage kWh sans assimilation arbitraire au gaz ; préserver les sources tierces et préférences ; transaction administrateur avec aperçu, sauvegarde, confirmation, relecture et rollback. Écritures désactivées si preuve ou qualification insuffisante.
- **EN — #88 / Energy:** one eligible series per dwelling/fluid, no concurrent variants or double counting; verify units/classes and heating-kWh semantics without assuming gas consumption; preserve third-party sources/preferences; admin preview, backup, confirmation, readback and rollback; disable writes until qualified.
- **FR — #42 / IHM tarifs :** F55 est **bloquante** pour la première stable, bien qu'absorbée : saisie graphique année/fluide/compteur, aucun JSON requis dans le parcours normal, années anciennes, EUR/m³ et EUR/kWh, tarifs de l'année exacte, coût estimé clairement distinct des charges connues, statut provisoire/approuvé distinct de la réalité facturée ; tests FR/EN et recette UX réelle. Tarifs facultatifs pour les consommations seules.
- **EN — #42 / Rates UI:** F55 remains a **stable release gate** despite absorption: graphical year/fluid/meter editor with no JSON entry required in ordinary workflow, historical years, EUR/m³ and EUR/kWh, exact-year rates, estimates never presented as billed charges, provisional/approved rate status distinct from verified billing; bilingual/UX acceptance. Tariffs remain optional for consumption-only Energy.
- **FR — #83/#84/#70 et #39 Sxx :** F54 stable couvre la consultation du logement configuré ; parcours lisibles FR/EN sur ordinateur/mobile, accessible clavier/tactile, autorisations administrateur côté serveur, confirmation des décisions persistantes, messages et diagnostics sans secrets. La présence de code/CI ne prouve ni recette réelle ni activation.
- **EN — #83/#84/#70 and #39 Sxx:** stable F54 covers the configured dwelling; usable FR/EN desktop/mobile workflows and keyboard/touch accessibility; server-side admin authorization, explicit confirmation before persistent changes, redacted diagnostics and error messages. Code or CI presence is not real-world acceptance or feature enablement.

**FR — Qualification :** documenter séparément développé, testé sur SHA exact, recetté sur périmètre réel, fusionné, publié et installé. Les cases originales F01–F62 restent non cochées faute de preuves de recette exhaustives. Les critères de version stable, de publication et de clôture de #39 restent inchangés ; candidature officielle HACS en phase 2 #175.

**EN — Qualification:** separately record developed, tested on exact SHA, accepted in real scope, merged, released and installed. The original F01–F62 checkboxes remain unchecked absent comprehensive acceptance evidence. Stable release/publication/closure conditions in #39 remain intact; official HACS submission is deferred to phase-2 issue #175.

<!-- END F01-F62 SCOPE RECONCILIATION 2026-11-14 -->


**FR — Objectif :** préparer et qualifier le périmètre retenu de la première version stable de `ha-trybatec`, y compris structure du dépôt, métadonnées, tests HACS/hassfest, sécurité, documentation et recette. **Cette issue ne porte plus la candidature officielle au catalogue, ni les engagements de maintenance après référencement.** Ces obligations C01–C14, P01–P10 et décisions J07–J08 sont conservées intégralement dans [#175 — Phase 2 différée / Deferred phase 2](https://github.com/christophejaubert/ha-trybatec/issues/175), classée Incubateur, sans échéance ni engagement.

**EN — Objective:** prepare and qualify the agreed scope of the first stable release of `ha-trybatec`, including repository/package metadata, HACS/hassfest checks, security, documentation and acceptance. **Official catalog submission and post-listing maintenance are no longer completion conditions for this issue.** The original C01–C14, P01–P10 and J07–J08 requirements are preserved in [#175 — Deferred phase 2](https://github.com/christophejaubert/ha-trybatec/issues/175), in the Incubator with no deadline or delivery commitment.

> **FR — Autorisation limitée :** cette issue ne donne pas à elle seule l'autorisation de modifier Home Assistant, de fusionner, publier, migrer, restaurer, installer ou soumettre une PR à `hacs/default`. Les responsabilités fonctionnelles/CI restent dans leurs chantiers respectifs ; cette issue consolide les preuves de qualification.
>
> **EN — Limited authorization:** this issue does not itself authorize Home Assistant changes, merges, releases, migrations, restores, installations or submissions to `hacs/default`. Functional and CI responsibilities remain with their respective workstreams; this issue tracks qualification evidence.

## Légende / preuve exigée

- **[O]** = exigence officielle de structure, validation ou candidature ; **[Q]** = critère qualité propre au projet ; **[O/Q]** = contrôle mêlant prescription officielle et vérification de qualité.
- Pour cocher une case : joindre **PR/commit SHA, exécution CI, résultat d'essai, version HA et/ou documentation** pertinents. Ne pas inférer une validation de la seule présence d'un fichier, d'une case cochée, d'une PR fusionnée ou d'un état CI non vérifié.
- Les critères F sont la **recette cible** ; définir ensuite leur caractère bloquant **dans le périmètre retenu pour la version stable**. Une fonction non livrée ne doit pas être annoncée comme disponible.
- Les critères officiels cités sont ceux consultés le **9 novembre 2026** ; les revérifier avant soumission.

## Constat initial vérifié (lecture seule de `main` au 9 novembre 2026)

- Dépôt public, non archivé, branche par défaut `main`, licence MIT, description, topics, issues GitHub activées.
- Fichiers `README.md`, `hacs.json`, `custom_components/trybatec/manifest.json`, dossier `brand` (icon.png, icon@2x.png), traductions `fr.json` et `en.json`.
- `.github/workflows/ci.yml` contient **déjà les jobs `hacs`, `hassfest`, `gitleaks` et les tests**. **Ne pas créer de doublon** ; succès des exécutions sur un SHA candidat **non vérifié ici**.
- `manifest.json` indique `0.2.0b14` tandis que le début du README mentionne encore `0.2.0b7` comme version de `main` : **incohérence à corriger au moment opportun**.
- `hacs.json` annonce `Trybatec (Unofficial Beta)` : à revoir pour la stable.
- Le workflow `publish-experimental.yml` **interdit explicitement les releases stables** : créer un mécanisme de publication stable sécurisé, distinct, uniquement après autorisation.
- Le README signale une API Trybatec **non documentée contractuellement** et des limites expérimentales : qualification et mentions légales indispensables.
- Aucune des cases ci-dessous n'est pré-cochée sans preuve de validation complète.


## 1. Dépôt et métadonnées

- [historique : non validé / archived: unverified] **M01** — [O] Dépôt GitHub public, non archivé, un seul élément de type intégration.
- [historique : non validé / archived: unverified] **M02** — [O] Arborescence custom_components/trybatec/ installable.
- [historique : non validé / archived: unverified] **M03** — [O] Domaine trybatec valide et sans conflit avec une intégration installée/Core.
- [historique : non validé / archived: unverified] **M04** — [O] Tous les fichiers exécutables nécessaires présents dans le dossier de l'intégration.
- [historique : non validé / archived: unverified] **M05** — [O] README.md et hacs.json à la racine.
- [historique : non validé / archived: unverified] **M06** — [O] Description GitHub, topics et issues activées.
- [historique : non validé / archived: unverified] **M07** — [O] Manifest : domain, name, version, documentation, issue_tracker, codeowners valides.
- [historique : non validé / archived: unverified] **M08** — [O/Q] Valider categories (1–3 admises sans doublons), config_flow, iot_class, integration_type, dependencies, after_dependencies et requirements.
- [historique : non validé / archived: unverified] **M09** — [O/Q] Nom définitif cohérent dans hacs.json et manifest, retirer Beta du nom pour une release stable.
- [historique : non validé / archived: unverified] **M10** — [Q] Déclarer une version minimale Home Assistant effectivement testée dans hacs.json.
- [historique : non validé / archived: unverified] **M11** — [Q] Valider les traductions en.json et fr.json.
- [historique : non validé / archived: unverified] **M12** — [O] Icône brand/icon.png valide ou image reconnue dans le dépôt brands.
- [historique : non validé / archived: unverified] **M13** — [O] Téléchargement décompressé inférieur ou égal à 100 MiB et 50 000 fichiers.
- [historique : non validé / archived: unverified] **M14** — [Q] Vérifier la persistance et le comportement des fichiers/données lors des mises à jour.
- [historique : non validé / archived: unverified] **M15** — [Q] Licence, mentions de propriété intellectuelle et identité visuelle non trompeuse.
- [historique : non validé / archived: unverified] **M16** — [Q] Décider hide_default_branch, country (si restriction géographique), persistent_directory (si nécessaire), zip_release/filename (si archive voulue).
- [historique : non validé / archived: unverified] **M17** — [Q] Ajouter un lien My Home Assistant vers le dépôt personnalisé et vérifier le comportement 2026.11 et versions antérieures.
- [historique : non validé / archived: unverified] **M18** — [Q] Aligner README et manifeste : README vu avec référence main 0.2.0b7 tandis que manifest main indique 0.2.0b14.

## 2. Validation, CI/CD et qualification technique

- [historique : non validé / archived: unverified] **T01** — [O] Exécution HACS Action réussie sur commit candidat, category integration.
- [historique : non validé / archived: unverified] **T02** — [O] Exécution hassfest réussie sur le même commit.
- [historique : non validé / archived: unverified] **T03** — [O] Aucun check HACS ignoré ; liens des exécutions conservés.
- [historique : non validé / archived: unverified] **T04** — [Q] Tests unitaires pytest complets.
- [historique : non validé / archived: unverified] **T05** — [Q] Ruff (lint), formatage et vérifications de types pertinents.
- [historique : non validé / archived: unverified] **T06** — [Q] Tests de chargement dans Home Assistant réel/isolé.
- [historique : non validé / archived: unverified] **T07** — [Q] Installation, désinstallation, réinstallation.
- [historique : non validé / archived: unverified] **T08** — [Q] Redémarrage HA, rechargement d'intégration.
- [historique : non validé / archived: unverified] **T09** — [Q] Migration depuis versions historiques réellement utilisées.
- [historique : non validé / archived: unverified] **T10** — [Q] Authentification incorrecte, timeout, 401/403/429/5xx, reconnexion et retours API incomplets.
- [historique : non validé / archived: unverified] **T11** — [Q] Environnements HA OS, Container, Supervised selon matrice support déclarée.
- [historique : non validé / archived: unverified] **T12** — [Q] ARM64 et AMD64 selon matrice support déclarée.
- [historique : non validé / archived: unverified] **T13** — [Q] Compatibilité avec dernière version stable Home Assistant.
- [historique : non validé / archived: unverified] **T14** — [Q] Compatibilité préventive avec prochaine beta Home Assistant lorsque disponible.
- [historique : non validé / archived: unverified] **T15** — [Q] Tests de sécurité, secrets et dépendances.
- [historique : non validé / archived: unverified] **T16** — [Q] Mesurer temps de réponse, mémoire, charge CPU et fréquence d'appels API.
- [historique : non validé / archived: unverified] **T17** — [Q] Bloquer toute publication si contrôle qualifié obligatoire non réussi ou absent.
- [historique : non validé / archived: unverified] **T18** — [Q] Archiver preuves et liens de test, SHA, version de HA et environnement.
- [historique : non validé / archived: unverified] **T19** — [Q] Conserver les jobs existants ci.yml (hacs, hassfest, gitleaks, tests) ; ne pas multiplier les workflows sans besoin.

## 3A. Authentification, lots et API Trybatec

- [historique : non validé / archived: unverified] **F01** — Authentification avec compte utilisateur ordinaire.
- [historique : non validé / archived: unverified] **F02** — Comptes multi-copropriétés.
- [historique : non validé / archived: unverified] **F03** — Plusieurs logements.
- [historique : non validé / archived: unverified] **F04** — Association fiable compte/logement/lot/compteur.
- [historique : non validé / archived: unverified] **F05** — Validation UUID/dealUid/identifiants, sans confusion.
- [historique : non validé / archived: unverified] **F06** — Erreurs d'autorisation et accès révoqués.
- [historique : non validé / archived: unverified] **F07** — Réauthentification sans perte de configuration.
- [historique : non validé / archived: unverified] **F08** — Tolérance aux modifications des schémas API, refus explicite des données ambiguës.
- [historique : non validé / archived: unverified] **F09** — Limitation des appels, des retries et des erreurs HTTP.
- [historique : non validé / archived: unverified] **F10** — Tests de lecture et fonctionnement sur comptes indépendants, sans données publiques réelles.

## 3B. Compteurs et entités

- [historique : non validé / archived: unverified] **F11** — Identité stable de chaque compteur physique.
- [historique : non validé / archived: unverified] **F12** — Compteurs déposés conservés.
- [historique : non validé / archived: unverified] **F13** — Remplacement et succession de compteurs physiques.
- [historique : non validé / archived: unverified] **F14** — Validation des unités de l'index réel.
- [historique : non validé / archived: unverified] **F15** — Choix explicite utilisateur si unité inconnue.
- [historique : non validé / archived: unverified] **F16** — Conversions d'unités vérifiées.
- [historique : non validé / archived: unverified] **F17** — Aucun delta fictif après baisse ou remise à zéro inexpliquée.
- [historique : non validé / archived: unverified] **F18** — Stable unique_id et migration des IDs lorsqu'indispensable.
- [historique : non validé / archived: unverified] **F19** — Compteurs indisponibles/supprimés.
- [historique : non validé / archived: unverified] **F20** — Dédoublonnage et changements d'identifiants.

## 3C. Historique, lissage et Recorder

- [historique : non validé / archived: unverified] **F21** — Relevés réels préservés.
- [historique : non validé / archived: unverified] **F22** — Distinguer observé, corrigé, interpolé, inconnu.
- [historique : non validé / archived: unverified] **F23** — Examiner explicitement les relevés de 2021, 2022 et 2023 et périodes anciennes.
- [historique : non validé / archived: unverified] **F24** — Séries consultables lissées et non lissées.
- [historique : non validé / archived: unverified] **F25** — Ne jamais faire passer interpolation pour une mesure.
- [historique : non validé / archived: unverified] **F26** — Lacunes, chevauchements, doublons et incohérences.
- [historique : non validé / archived: unverified] **F27** — Changement d'année et périodes civiles.
- [historique : non validé / archived: unverified] **F28** — Fuseaux horaires et changements d'heure.
- [historique : non validé / archived: unverified] **F29** — Vérification des sommes/statistiques Recorder après import.
- [historique : non validé / archived: unverified] **F30** — Idempotence de l'import.
- [historique : non validé / archived: unverified] **F31** — Reprise contrôlée après interruption, journal des imports en attente.
- [historique : non validé / archived: unverified] **F32** — Protection et sauvegarde des statistiques et historiques existants.

## 3D. Consolidation et tableau Énergie

- [historique : non validé / archived: unverified] **F33** — Série logique consolidée par logement et fluide.
- [historique : non validé / archived: unverified] **F34** — Identités et données des compteurs physiques distinctes.
- [historique : non validé / archived: unverified] **F35** — Versions V1/V2 appliquées à la série consolidée.
- [historique : non validé / archived: unverified] **F36** — Séries historiques alternatives par compteur physique.
- [historique : non validé / archived: unverified] **F37** — Variantes lissées et non lissées par compteur.
- [historique : non validé / archived: unverified] **F38** — Séries alternatives consultables hors tableau Énergie.
- [historique : non validé / archived: unverified] **F39** — Sélection contrôlée empêchant le double comptage dans Énergie.
- [historique : non validé / archived: unverified] **F40** — Unités, state_class, device_class et statistic_id corrects.
- [historique : non validé / archived: unverified] **F41** — Changer la sélection ne détruit/altère pas l'historique statistique.
- [historique : non validé / archived: unverified] **F42** — Remplacement de compteur et continuité de la série logique.

## 3E. Migration sécurisée

- [historique : non validé / archived: unverified] **F43** — Détecter générations et entités historiques.
- [historique : non validé / archived: unverified] **F44** — Construire aperçu de migration complet.
- [historique : non validé / archived: unverified] **F45** — Identifier les références statistiques et des tableaux de bord avant changement.
- [historique : non validé / archived: unverified] **F46** — Présenter les modifications prévues.
- [historique : non validé / archived: unverified] **F47** — Confirmation explicite avant exécution.
- [historique : non validé / archived: unverified] **F48** — Sauvegarde préalable ou mécanisme de récupération documenté.
- [historique : non validé / archived: unverified] **F49** — Contrôle après migration.
- [historique : non validé / archived: unverified] **F50** — Procédure testée de restauration si incident.
- [historique : non validé / archived: unverified] **F51** — Nettoyage d'anciennes entités seulement après vérifications et validation.
- [historique : non validé / archived: unverified] **F52** — Persistance des décisions de revue historique.

## 3F. IHM, coûts et contrôle d'accès

- [historique : non validé / archived: unverified] **F53** — Interface de configuration finale Home Assistant.
- [historique : non validé / archived: unverified] **F54** — Consultation compteurs/logements.
- [historique : non validé / archived: unverified] **F55** — Saisie annuelle des coûts/tarifs, par fluide et compteur si pertinent, **via formulaire graphique sans saisie JSON** ; recette bloquante avant la première version stable. Suivi : [IHM — tarifs annuels (42)](https://github.com/christophejaubert/ha-trybatec/issues/42).
- [historique : non validé / archived: unverified] **F56** — Séparation montants estimés et montants réellement connus.
- [historique : non validé / archived: unverified] **F57** — Montants en EUR et tarifs de l'année civile exacte.
- [historique : non validé / archived: unverified] **F58** — Distinction accès ordinaire et privilèges administrateur pour opérations sensibles.
- [historique : non validé / archived: unverified] **F59** — Confirmation requise avant modification Recorder ou décisions persistantes.
- [historique : non validé / archived: unverified] **F60** — Parcours français et anglais validés.
- [historique : non validé / archived: unverified] **F61** — Affichage ordinateur et mobile.
- [historique : non validé / archived: unverified] **F62** — Erreurs lisibles sans secrets ni données privées.

## 4. Sécurité, confidentialité et cadre juridique

- [historique : non validé / archived: unverified] **S01** — Aucun secret, jeton, cookie ou identifiant d'accès dans le dépôt.
- [historique : non validé / archived: unverified] **S02** — Pas de secrets en clair dans les journaux.
- [historique : non validé / archived: unverified] **S03** — Diagnostics sans données personnelles identifiantes.
- [historique : non validé / archived: unverified] **S04** — Tests et captures publics uniquement synthétiques/anonymisés.
- [historique : non validé / archived: unverified] **S05** — Contrôle autorisations sur toutes les opérations sensibles.
- [historique : non validé / archived: unverified] **S06** — Limiter les appels API à la nécessité fonctionnelle.
- [historique : non validé / archived: unverified] **S07** — Respecter rate limits et éviter la surcharge du service tiers.
- [historique : non validé / archived: unverified] **S08** — Confirmation et protections des écritures historiques.
- [historique : non validé / archived: unverified] **S09** — Scanner dépendances/actions CI et réduire permissions.
- [historique : non validé / archived: unverified] **S10** — Maintenir SECURITY.md et signalement de vulnérabilités.
- [historique : non validé / archived: unverified] **S11** — Documenter les données échangées avec Trybatec.
- [historique : non validé / archived: unverified] **S12** — Vérifier les conditions d'utilisation et la légitimité des accès à l'API non documentée.
- [historique : non validé / archived: unverified] **S13** — Vérifier usage du nom/éventuels signes de marque.
- [historique : non validé / archived: unverified] **S14** — Afficher clairement le caractère non officiel et l'absence d'affiliation.
- [historique : non validé / archived: unverified] **S15** — Procédure de correctif de sécurité urgent contrôlée.
- [historique : non validé / archived: unverified] **S16** — Procédure d'alerte si version susceptible d'endommager les données.

## 5. Documentation et support

- [historique : non validé / archived: unverified] **D01** — README décrivant uniquement les fonctionnalités réellement livrées.
- [historique : non validé / archived: unverified] **D02** — Prérequis compte, accès Trybatec, version minimale HA.
- [historique : non validé / archived: unverified] **D03** — Installation depuis Marketplace.
- [historique : non validé / archived: unverified] **D04** — Installation par dépôt personnalisé avant référencement.
- [historique : non validé / archived: unverified] **D05** — Guide première configuration.
- [historique : non validé / archived: unverified] **D06** — Guide logements et découverte des compteurs.
- [historique : non validé / archived: unverified] **D07** — Guide unités, provenance et conversions.
- [historique : non validé / archived: unverified] **D08** — Guide lissage, non-lissage et degré de certitude.
- [historique : non validé / archived: unverified] **D09** — Guide tableau Énergie et sélection sans double comptage.
- [historique : non validé / archived: unverified] **D10** — Guide revue/import historique et avertissements.
- [historique : non validé / archived: unverified] **D11** — Référence des actions/services Home Assistant.
- [historique : non validé / archived: unverified] **D12** — Guide des coûts et tarifs annuels.
- [historique : non validé / archived: unverified] **D13** — Guide migration/retour arrière.
- [historique : non validé / archived: unverified] **D14** — Guide désinstallation et effets sur statistiques.
- [historique : non validé / archived: unverified] **D15** — FAQ/dépannage.
- [historique : non validé / archived: unverified] **D16** — Limitations connues, notamment API non documentée.
- [historique : non validé / archived: unverified] **D17** — Politique de support et de maintenance.
- [historique : non validé / archived: unverified] **D18** — Changelog et notes par release.
- [historique : non validé / archived: unverified] **D19** — Issue templates pour bugs et évolutions.
- [historique : non validé / archived: unverified] **D20** — Captures anonymisées.
- [historique : non validé / archived: unverified] **D21** — Relecture complète FR/EN.
- [historique : non validé / archived: unverified] **D22** — Confidentialité et risques liés au service tiers.
- [historique : non validé / archived: unverified] **D23** — README : badge My Home Assistant et sections cachées dans Marketplace si utiles.

## 6. Préparation de la version stable

- [historique : non validé / archived: unverified] **R01** — Définir explicitement le périmètre minimal stable.
- [historique : non validé / archived: unverified] **R02** — Résoudre tous défauts bloquants du périmètre.
- [historique : non validé / archived: unverified] **R03** — Publier candidate de release (rc) pour recette, si utile.
- [historique : non validé / archived: unverified] **R04** — Exécuter recette complète sur SHA immuable.
- [historique : non validé / archived: unverified] **R05** — Valider toutes les migrations et leurs prévisualisations.
- [historique : non validé / archived: unverified] **R06** — Collecter succès des contrôles CI obligatoires sur SHA exact.
- [historique : non validé / archived: unverified] **R07** — Notes de version exactes, risques/limites connus.
- [historique : non validé / archived: unverified] **R08** — Version manifest, tag, release et README cohérentes.
- [historique : non validé / archived: unverified] **R09** — Prévoir workflow release stable distinct du workflow expérimental (qui refuse versions stables).
- [historique : non validé / archived: unverified] **R10** — Obtenir validation explicite du propriétaire avant release.
- [historique : non validé / archived: unverified] **R11** — Créer une vraie GitHub Release stable, non juste un tag.
- [historique : non validé / archived: unverified] **R12** — Tester installation depuis dépôt personnalisé et version distribuée.
- [historique : non validé / archived: unverified] **R13** — Tester mises à jour depuis version précédente supportée.
- [historique : non validé / archived: unverified] **R14** — Vérifier procédure documentée de retour arrière (attention aux statistiques migrées).

## 7. Candidature au catalogue / Official catalog submission — différée / deferred

**FR :** exigences C01–C14 transférées dans [#175](https://github.com/christophejaubert/ha-trybatec/issues/175) et exclues du périmètre de réalisation et de clôture de cette première phase. Aucune soumission ni suivi du catalogue n'est planifié à ce stade.

**EN:** requirements C01–C14 have moved to [#175](https://github.com/christophejaubert/ha-trybatec/issues/175). They are excluded from the active first-phase scope and its completion criteria. No catalog submission or follow-up is planned now.

## 8. Maintenance post-référencement / Post-listing maintenance — différée / deferred

**FR :** exigences P01–P10, y compris P06 (maintenance FR/EN) et P10 (fin de vie avec préservation des données), transférées dans [#175](https://github.com/christophejaubert/ha-trybatec/issues/175), sans calendrier ni engagement. Les obligations de sécurité ou de qualité nécessaires à une version stable demeurent dans les critères propres à cette première phase ; le report de P06/P10 n'en dispense pas.

**EN:** P01–P10, including P06 (FR/EN maintenance) and P10 (data-preserving end-of-life policy), have moved to [#175](https://github.com/christophejaubert/ha-trybatec/issues/175) without a schedule or commitment. First-release safety/quality requirements remain applicable in this issue; deferring P06/P10 does not waive them.

## 9. Jalons et arbitrages

- [historique : non validé / archived: unverified] **J01** — Choisir le périmètre fonctionnel exact de la première stable (bloquants vs futures évolutions).
- [historique : non validé / archived: unverified] **J02** — Associer aux critères pertinents les PR/issues existantes de dev (notamment b15) et de CI/CD, **sans déplacer leurs responsabilités**.
- [historique : non validé / archived: unverified] **J03** — Dresser une matrice de compatibilité Home Assistant / Python / architecture / mode d'installation.
- [historique : non validé / archived: unverified] **J04** — Obtenir au moins un essai réel sur installation indépendante du développeur et des données synthétiques en CI.
- [historique : non validé / archived: unverified] **J05** — Valider explicitement les conditions d'utilisation de l'API tierce ou documenter une incertitude acceptable.
- [historique : non validé / archived: unverified] **J06** — Valider explicitement le SHA de la release stable après passage des gates.


**FR :** J07/J08 sont reportés à l'issue #175 ; la publication stable n'autorise pas le dépôt d'une PR de catalogue. / **EN:** J07/J08 are deferred to issue #175; publishing a stable release does not authorize a catalog PR.

## 10. Critères de clôture de cette première phase / Phase 1 completion criteria

**FR — Fermer comme réalisée seulement si :**

1. Le **périmètre minimal de la première stable** est explicitement décidé, et les fonctionnalités différées ne sont pas annoncées comme livrées.
2. Les critères de dépôt et de distribution propres à ce périmètre, les contrôles HACS/hassfest et la CI obligatoires ont des preuves sur le **SHA exact**.
3. La qualification du périmètre stable (installation, configuration, mise à jour, sécurité, migrations/Recorder/Énergie lorsqu'ils en font partie) est documentée avec ses limites et ses preuves ; aucune prétention de recette non réalisée.
4. La version stable, son manifeste, son tag, ses notes et sa **GitHub Release** sont cohérents, publiés **sur autorisation explicite distincte**, et son installation depuis un dépôt personnalisé est vérifiée.
5. La documentation disponible de la première stable, ses limitations et les risques des données sont exacts et disponibles en FR/EN selon les exigences applicables à la release.

**EN — Close as completed only if:**

1. The first stable release scope is explicitly approved, with deferred functionality clearly identified as unavailable.
2. Repository/distribution requirements, HACS/hassfest validation and mandatory CI are evidenced on the **exact release SHA**.
3. Qualification of the stable scope (install, configuration, upgrades, security, and migration/Recorder/Energy when included) is documented with honest evidence and limits; no unperformed acceptance is claimed.
4. The stable version, manifest, tag, notes and **GitHub Release** are aligned and published **only after separate explicit authorization**, and installation from a custom repository is verified.
5. Stable-release documentation, limitations and data risks are accurate and covered in FR/EN where required for the release.

**FR / EN :** l'acceptation par `hacs/default`, la présence au catalogue public et les engagements P01–P10 **ne sont pas des critères de clôture de #39**. Ils appartiennent à l'[issue #175 — incubateur](https://github.com/christophejaubert/ha-trybatec/issues/175). / Acceptance into `hacs/default`, public listing and P01–P10 **are not completion criteria for #39**; they belong to [#175 — Incubator](https://github.com/christophejaubert/ha-trybatec/issues/175).

## 11. Références officielles (consultées 2026-11-09)

- [Procédure de candidature au catalogue](https://contributors.home-assistant.io/marketplace/guides/catalog/)
- [Structure attendue du dépôt](https://contributors.home-assistant.io/marketplace/reference/repository-structure/)
- [Validations HACS, hassfest et contrôles à l'installation](https://contributors.home-assistant.io/marketplace/reference/validation/)
- [Référence de hacs.json](https://contributors.home-assistant.io/marketplace/reference/hacs-json/)
- [Releases et mises à jour](https://contributors.home-assistant.io/marketplace/guides/releases/)
- [Annonce officielle Home Assistant 2026.11](https://www.home-assistant.io/blog/2026/11/04/release-202611/)
- [Catalogue HACS](https://github.com/hacs/default)
- [Dépôt ha-trybatec](https://github.com/christophejaubert/ha-trybatec)

**Hors périmètre :** intégration native à Home Assistant Core / bibliothèque PyPI / certification Bronze, qui constituent un projet distinct et facultatif.

