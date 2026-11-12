# Préparation groupée Énergie / Bulk Energy preflight

## FR — Portée expérimentale

Ce composant est **un calcul pur de proposition en lecture seule** (`energy_bulk_plan.py`). Il ne communique ni avec Home Assistant ni avec Trybatec, ne lit pas Recorder, ne modifie pas les préférences Énergie et **ne rend pas le bouton « Ajouter à Énergie » opérationnel**. Ses entrées de preuve doivent, dans un futur chantier distinct, être construites par un service administrateur qui vérifie le registre de versions, les métadonnées Recorder, les sources déjà sélectionnées, les unités, les compteurs déposés et la couverture de tous les logements/fluides concernés. Des indicateurs de preuve fournis par le navigateur **ne sont pas suffisants**.

Ce plan accepte une **unique série consolidée et vérifiée par compte, lot et fluide** ; les variantes concurrentes doivent être inventoriées exhaustivement par un backend de confiance. Toute variante déjà active bloque l'ajout et renvoie au parcours de remplacement validé, sans suppression de séries historiques. Les références tierces et les réglages Énergie non concernés sont préservés ; une seconde préparation ne crée aucun doublon. Les compteurs déposés peuvent contribuer à la série consolidée, mais seulement si cette couverture est vérifiée indépendamment.

### Mappage de catégories testé contre Home Assistant Core 2026.11.1

| Fluide | Catégorie technique HA | Statistique attendue | Limites |
| --- | --- | --- | --- |
| EF | `water` | m³ | Aucun libellé `name` injecté : `WATER_SOURCE_SCHEMA` ne l'accepte pas |
| ECS | `water` | m³ | Même catégorie native que EF, série distincte |
| Chauffage (CET) | `gas` | kWh | Sous réserve de validation réelle des statistiques thermiques par HA |

Le plan n'insère **aucune statistique de coût**, aucun tarif annuel ou prix dynamique. Dans Home Assistant 2026.11.1, `_reject_price_for_external_stat` interdit d'associer directement `entity_energy_price` ou `number_energy_price` à une statistique externe en l'absence de `stat_cost` : les coûts historiques doivent faire l'objet d'une analyse séparée. L'absence de tarifs annuels ne bloque pas à elle seule le suivi des **consommations**.

### Étapes manquantes avant activation

1. Identifier toutes les séries et références en concurrence pour chaque logement/fluide, y compris générations d'entités ; garantir une couverture d'inventaire exhaustive.
2. Vérifier Recorder : existence des statistiques, classe, unités, valeurs enregistrées, versions et absence de chevauchement non résolu ; résoudre les historiques déposés selon #36/#37 et les migrations selon #81.
3. Construire un aperçu serveur authentifié avec empreinte de **l'état réel** des préférences, puis faire valider le schéma par Home Assistant sans écriture.
4. Après consentement administrateur distinct et sauvegarde récupérable, écrire en transaction contrôlée, relire, vérifier et restaurer en cas d'échec. Tester les modifications concurrentes et l'idempotence.
5. Réaliser les tests de compatibilité, de sécurité, UI FR/EN et la **recette métier sur une installation représentative**. Les contrôles CI ne constituent pas cette recette.

Références : [issue #88](https://github.com/christophejaubert/ha-trybatec/issues/88), [issue #83](https://github.com/christophejaubert/ha-trybatec/issues/83) et [Home Assistant Core 2026.11.1 — energy/data.py](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/energy/data.py).

---

## EN — Experimental scope

`energy_bulk_plan.py` is a **pure read-only proposal planner**. It never talks to Home Assistant, Trybatec or Recorder, never changes Energy preferences, and **does not enable the bulk enrollment button**. All evidence flags and competing-series inventories must later be established by a trusted administrator-only backend from persisted Recorder metadata, version ledgers, existing Energy preferences and verified physical meter scopes. **Browser claims are not evidence.**

Exactly one verified consolidated consumption series per account/dwelling/fluid is allowed. Known competing selected versions block insertion, existing correct targets are idempotent, and unrelated sources/preferences are preserved. Retired-meter history requires independently confirmed consolidated coverage.

For Home Assistant Core 2026.11.1, water utilities use separate `water` statistics in m³ (the `WATER_SOURCE_SCHEMA` does **not** accept an extra custom `name` field); heating may use the compatible `gas` category with verified kWh thermal energy, subject to real compatibility verification. No yearly rates or cost statistics are inserted. Home Assistant rejects direct dynamic/fixed prices for external statistics without a suitable cost statistic.

**Before any real action:** trusted complete inventory, verified Recorder metadata and identities, conflict/overlap exclusions, exact-schema preview, concurrent-change fingerprinting, recoverable backup, explicit administrator confirmation, post-write readback, rollback and real production-like acceptance. Automated CI and real Home Assistant acceptance are separate.

Sources: [#88](https://github.com/christophejaubert/ha-trybatec/issues/88), [#83](https://github.com/christophejaubert/ha-trybatec/issues/83), [HA Core 2026.11.1 Energy schema](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/energy/data.py).
