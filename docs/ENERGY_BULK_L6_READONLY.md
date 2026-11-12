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
