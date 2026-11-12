# 🤖 L6 — Raccordement des preuves Énergie / Energy evidence read-only handoff

## FR — But et frontière de confiance

**Référence auditée :** `main` `a1bd6d8558c8fe1cc13cadeb1ff4aaa20528dc53`, PR #91/#92/#121 fusionnées, PR #120/#82 encore ouvertes. Issue #88 ouverte. Le présent lot est préparé localement ; **pas de publication GitHub ni d'intégration HA**.

L6 réutilise le collecteur L3, le registre historique B15, le planificateur #92 et les utilitaires de préférences Énergie existants. Les deux nouveaux modules sont :

- `custom_components/trybatec/energy_bulk_readonly.py` : classification pure, EF/ECS/CET, à partir du rapport L3 et des préférences Énergie réellement observées.
- `custom_components/trybatec/energy_bulk_readonly_ha.py` : raccordement dormant au collecteur administrateur L3 et comparaison mémoire/disque, sans WebSocket ni démarrage automatique.

Les quatre états par fluide sont **`admissible`**, **`already_configured`**, **`blocked`** et **`insufficient_evidence`**. *Seuls* les trois derniers peuvent actuellement être produits : un état `admissible` exige de futures preuves natives et indépendantes de #36/#37, indisponibles dans le contrat L3 intégré. `already_configured` décrit une référence existante et un emplacement compatible vérifiables ; ce n'est **pas** une validation de toute la couverture historique.

Toutes les sorties incluent `writes=False`, `activation_authorized=False`, `blocked=True`. Les sources tierces, champs futurs et paramètres existants sont laissés intacts. Un inventaire incomplet n'est jamais considéré comme vide. Le résultat est réservé à un **adaptateur serveur administrateur** : le navigateur ne peut pas créer des preuves en fournissant des booléens ou des `statistic_id`.

### Inventaires et preuves

| Élément | Déjà accessible | Preuve indispensable manquante |
| --- | --- | --- |
| Compteurs courants | Cache du coordinateur, lot/fluide/numéro, unité | Exhaustivité toutes années, compteurs déposés (#37) |
| Historique | Registre B15 et aperçu V5 | Sélection stable de la variante consolidée, dates/chevauchements (#36/#37) |
| Recorder | Métadonnées, échantillons persistés | Concordance de **tous** les intervalles de la série consolidée (#36) |
| Préférences | Copie mémoire + disque, références de statistiques | Exhaustivité des variantes et dépendances externes (#81/#120) |
| Schéma HA | Source `water` pour EF/ECS, `gas` techniquement pour CET sous 2026.11.1 | Validation métier de CET et exécution native de schéma réelle |

La présence de valeurs Recorder ne suffit pas à établir une couverture de compteurs déposés. Les catégories `water` / `gas` sont des catégories Home Assistant techniques, non des libellés métiers arbitraires. La catégorie `gas` pour le chauffage en kWh nécessite une validation spécifique.

### Critères de raccordement futur

1. Établir un inventaire complet des compteurs historiques, filiation et dates de validité depuis #37, sans migration ni nettoyage des identifiants #82.
2. Obtenir de #36 la preuve de couverture/versions et les fenêtres Recorder vérifiées pour **chaque** compteur et période, avec source_fingerprint stable et absence de double comptage.
3. Reconstituer côté serveur les statistiques concurrentes B15/V4/V5, capteurs physiques et références tierces : aucune absence apparente d'un inventaire partiel ne vaut preuve.
4. Raccorder ces preuves à `plan_bulk_energy_insertion()` sans rendre les indicateurs du planificateur autoritaires. Prévoir les scénarios concurrentiels et invalidation des empreintes.
5. Rejouer les tests dans le dépôt complet, Python 3.13/3.14, HA runtime et navigateur réel FR/EN/clair/sombre/clavier avant qualification.

**Tests réalisés :** 17 scénarios nouveaux L6 en isolation, inclus dans les 83 tests locaux du lot combiné. Les utilitaires #92 sont simulés ; aucune validation CI ou HA réel n'est revendiquée.

## EN — Purpose and trust boundary

**Audited baseline:** `main` SHA `a1bd6d8558c8fe1cc13cadeb1ff4aaa20528dc53`. PRs #91, #92 and #121 are merged; PRs #120 and #82 remain open. Issue #88 remains open. This is a **local, unpublished** preparation.

L6 adds a pure per-utility classifier (`energy_bulk_readonly.py`) and a dormant authenticated Home Assistant adapter (`energy_bulk_readonly_ha.py`). It reuses L3 native observations and existing #92 Energy helpers. Every fluid EF/ECS/CET receives one of `admissible`, `already_configured`, `blocked`, `insufficient_evidence`. **Admissible is deliberately unreachable** until independently proven historical coverage, retired-meter lineage, overlapping variants and complete competing-reference inventories are made available by #36/#37. An already configured reference means exact observed selection only, not completeness or permission to alter Energy.

Outputs always preserve `writes=False`, `activation_authorized=False`, `blocked=True`. Existing Energy settings and third-party sources are not modified; no migration, Recorder write, supplier call or automatic startup hook is added. Only server-collected L3 evidence may be used. UI input flags are never trusted.

**Future integration gates:** trustworthy account/lot/physical lineage (#37), persistent per-window Recorder and consolidated series proof (#36), stable identity interface without #82 migration (#120), exhaustive alternatives, matching installed HA schema and CET semantic approval. Execute real #92 planner and HA/native/browser CI before integration. Synthetic isolated tests are not production acceptance.

**References:** [Issue #88](https://github.com/christophejaubert/ha-trybatec/issues/88), [#36](https://github.com/christophejaubert/ha-trybatec/issues/36), [#37](https://github.com/christophejaubert/ha-trybatec/issues/37), [PR #121](https://github.com/christophejaubert/ha-trybatec/pull/121), [HA Core 2026.11.1 Energy schema](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/energy/data.py).

---

## FR — Extension de qualification L6 (PR #129, itération 2)

Le raccordement évolue **sans changement de registre, de Recorder ou d'Énergie** :

- `energy_bulk_contract_l6.py` est un comparateur pur du registre de versions B15 issu de #36, des compteurs courants, et de l'archive des compteurs déposés issue de #37. Chaque identité physique comporte lot, fluide et numéro de série ; les collisions, statuts incertains, références manquantes, versions concurrentes, unités incompatibles et consolidations multiples sont refusés. Une génération déposée observée mais absente du registre B15 est **bloquante**.
- `energy_bulk_contract_ha_l6.py` vérifie de nouveau le contexte administrateur via le collecteur L3 puis lit uniquement des enveloppes JSON `.storage` bornées, en respectant l'interdiction de `Store.async_load()` pour la lecture ; aucune écriture ni appel fournisseur. Les noms des stockages sont calculés localement depuis l'ID de la configuration.
- `energy_bulk_readonly_ha.py` annexe désormais ce diagnostic à la réponse L6, sans jamais transformer une attestation d'inventaire partiel en admissibilité.
- Le contrat `meter_identity.py` de #120, encore non intégré à `main`, est vérifié **sur sa branche** comme référence technique ; aucune migration, aucun changement d'`entity_id` ou de `unique_id` historique n'est introduit.

**Limite déterminante :** ni le cache du coordinateur ni l'archive des compteurs déposés ni le registre B15, considérés isolément, ne prouvent l'exhaustivité de toutes les années. La persistance Recorder **bucket par bucket**, la concordance de la couverture cumulée/physique, la sélection des variantes et le recensement externe restent nécessaires. `complete=False` et `admissible=False` sont constants dans le nouveau contrôle. Le statut `already_configured` n'est qu'une observation de sélection effective dans les préférences ; il n'autorise aucune réécriture.

Validation : tests synthétiques ajoutés pour compteur déposé, identité ambiguë, archive falsifiée, série manquante, unité incompatible, registre versionné incorrect, versions concurrencées et absence de modification des entrées. Exécuter les tests sur le SHA de PR #129 en CI et distinguer cette preuve de toute recette HA réelle.

## EN — L6 qualification extension (PR #129, iteration 2)

The new pure `energy_bulk_contract_l6.py` cross-checks the B15 version ledger (#36), current physical-meter observations and archived retired meters (#37). It detects ambiguous identities, retired meters missing from the B15 ledger, conflicting consolidated series/versions, invalid archival keys and incompatible units. `energy_bulk_contract_ha_l6.py` reconstructs evidence from **read-only**, size-bounded HA storage-envelope reads, after independently enforcing L3 administrator authentication. The L6 HA preview attaches this diagnostic; it never grants admission.

**Gate remains closed:** a coordinator cache, retained retired-meter archive and B15 version ledger do not prove exhaustive multi-year coverage, source provenance, all Recorder buckets, complete alternatives or the independent #120 new-account stable-identity contract. Accordingly `complete=False`, `admissible=False`, no new Energy insertion and no implicit migration. The standalone source-selection observation `already_configured` is not permission to mutate Energy. CI must run on PR #129's exact head; live acceptance is separate.

### FR — Validation complémentaire de l'adaptateur natif

Quatre tests sur un faux contexte HA simulent l'authentification, les lectures `.storage`, l'absence de fichiers et le rejet d'un rapport L3 de provenance incorrecte. Ils n'appellent aucune API réelle. En l'absence de registre B15, les inventaires de compteurs courants **et** déposés sont explicitement inconnus, jamais réputés vides. La couverture locale de ce seul adaptateur atteint 100 % avec ces tests synthétiques, ce qui ne constitue pas une recette HA.

### EN — Additional native adapter validation

Four synthetic HA-context tests cover authentication, bounded storage reads, missing files and invalid L3 provenance. An unavailable B15 ledger explicitly marks both current and retired inventories unknown; absence never proves an empty scope. Local synthetic test coverage of this small adapter is 100%; no actual HA acceptance is implied.

### FR — Pont des contrats provisoires #36/#37 (PR #127/#125)

`energy_bulk_provenance_bridge_l6.py` accepte des **enveloppes internes synthétiques ou collectées côté serveur**, sans importer les modules des PR non fusionnées. Il rapproche :

- `lineage_37_energy_handoff_v1`, depuis `prepare_energy_lineage_handoff_37` de #125 (empreinte de l'enveloppe, compteurs déposés/inconnus, sommes de contributions physiques, indicateurs non autoritaires) ;
- les groupes `preview_only` de `build_coverage_evidence` dans #127 (journées mesurées/estimées/mixtes et statut `unknown` / `qualified_bounds_with_gaps` / `qualified_bounds_no_gaps`) ;
- le comparateur B15 / archive #37 existant dans #129, pour croiser les quantités, inventaires par fluide et détecter les contradictions.

Une enveloppe falsifiée, une portée étrangère, des doublons ou un désaccord sur les consommations sont refusés ; l'absence d'une enveloppe donne **preuve insuffisante**, jamais une consommation nulle. `qualified_bounds_no_gaps` **n'atteste que la plage de bornes disponible**, jamais les années inconnues. Les autorisations restent **`admissible=False` et `activation_authorized=False`**, y compris lorsque les deux enveloppes concordent. **Ce contrat n'est pas enregistré au démarrage et les PR #125/#127 ne sont pas fusionnées.** Le collecteur natif effectif et la preuve exhaustive restent à concevoir avec les propriétaires de #36/#37 avant toute activation.

### EN — Draft #36/#37 contract bridge (PRs #127/#125)

`energy_bulk_provenance_bridge_l6.py` performs a **pure, internal, non-authoritative** comparison of #125 `lineage_37_energy_handoff_v1`, #127 `build_coverage_evidence` bounded daily summaries, and L6's B15/retired-meter crosscheck. It detects tampered envelope fingerprints, duplicate/foreign scopes, retired-meter count mismatches, inconsistent consumption totals and missing evidence. `qualified_bounds_no_gaps` concerns *observed bounds only*, never proof of every historical day, every Recorder bucket or exhaustive external statistics. Missing upstream PR contracts produce an explicit `insufficient_evidence` verdict, not a guessed zero. **Always `admissible=False`, `activation_authorized=False`; no HA startup hook, backend API or write is registered.** PRs #125/#127 are not merged; a trusted server-side proof collector and full isolated HA acceptance remain dependencies.
