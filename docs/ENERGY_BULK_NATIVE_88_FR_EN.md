# 🤖 #88 — Contrats natifs L6/L7 / Native L6/L7 contracts

## FR — Avancement, sans activation

**Cible vérifiée : Home Assistant Core `2026.11.1`.** Les sources officielles de Core sont : [Recorder/statistics.py](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/recorder/statistics.py), [Energy/data.py](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/energy/data.py), [Energy/validate.py](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/energy/validate.py), [Backup/manager.py](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/backup/manager.py), [Backup/models.py](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/backup/models.py) et [storage.py](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/helpers/storage.py).

### Livraison technique de cette PR ciblée

1. **L3 :** remplace le service inexistant `recorder.get_statistics` par la lecture native `statistics_during_period`, sur quatre fenêtres bornées ; aucune modification Recorder ni invocation du fournisseur.
2. **Schéma :** vérifie sur une copie des préférences Énergie les sources `water` et `gas`, l'unité volumique m³ pour l'eau et l'admissibilité **technique** du kWh dans `gas`. Cela ne démontre ni l'origine physique du chauffage ni l'exactitude de ses statistiques et **n'autorise pas** la catégorie chauffage en soi.
3. **L7 :** le nouveau `HAGuardedEnergyPort` implémente le port transactionnel existant, sans enregistrement WebSocket ni effet au démarrage : contrôle de version, verrou partagé, sauvegarde Core native **achevée**, traçabilité d'un identifiant de sauvegarde nouveau, relecture des métadonnées avec couverture HA+base, validation native de l'archive, journal privé atomique et relu, modification des seuls `energy_sources` par `EnergyManager.async_update`, flush explicite de la sauvegarde différée (60 secondes), relecture des préférences persistées, et refus des sources concurrentes. Les changements ne sont possibles que si la proposition correspond exactement au journal préparé et à la sauvegarde vérifiée. Les transactions de retour arrière conservent les paramètres tiers et refusent les situations ambiguës.
4. **Tests :** simulations isolées (sans HA de production, sans sauvegardes réelles) couvrant les deux types de compteur d'eau, le chauffage, sources tierces, sauvegarde absente/partielle/illisible, journal manquant, empreintes discordantes, changement concurrent, écriture, relecture et rollback.

### Blocages **non levés**

- L6 ne peut encore certifier une consolidation **exhaustive** des générations physiques et des compteurs déposés (#37), des buckets historiques Recorder avec preuve et quiescence (#36), ni l'inventaire de tous les alias et statistiques concurrentes. L6 n'émet donc encore **aucun `admissible`** pour une source nouvelle.
- L7 ne crée **aucune interface d'activation** : aucun branchement du panneau ne contourne L6 ; l'adaptateur n'est pas inscrit en tant que service ni endpoint. **La fonctionnalité d'ajout groupé réel n'est pas encore opérationnelle.**
- Une archive identifiable et déchiffrable n'est **pas** une restauration réelle qualifiée. Celle-ci n'a pas été effectuée ; les risques résiduels doivent rester documentés et la recette réelle exige une décision distincte.
- Un verrou interne Trybatec ne bloque pas à lui seul toute modification indépendante depuis une autre intégration ou l'interface HA ; les empreintes protègent des modifications détectables, mais aucune garantie d'atomicité inter-intégrations n'est revendiquée.
- Aucune installation, sauvegarde, modification ou restauration de Home Assistant réel n'a été effectuée dans ce travail GitHub. **Aucune fusion ni release n'est autorisée.**

Références de coordination : [#88](https://github.com/christophejaubert/ha-trybatec/issues/88), [#36](https://github.com/christophejaubert/ha-trybatec/issues/36), [#37](https://github.com/christophejaubert/ha-trybatec/issues/37), [#45](https://github.com/christophejaubert/ha-trybatec/issues/45), [candidate #147](https://github.com/christophejaubert/ha-trybatec/pull/147) et protocole `docs/PRODUCTION_ACCEPTANCE_0.3.4b1_FR_EN.md`.

## EN — Current state, no activation

**Verified target: Home Assistant Core `2026.11.1`.** The linked official Core source files above establish the native read, Energy update, deferred persistence, and backup contracts. This PR replaces the nonexistent Recorder statistics service with `statistics_during_period` using four bounded read-only windows; tests category-schema and unit compatibility in isolation, never assuming gas-category kWh proves physical heat semantics; and provides a dormant, guarded native L7 port.

The new port has server-side version gating and a shared internal lock, a completed and uniquely identified native HA+database backup whose catalog and archive decryptability can be checked, an atomic private journal with disk readback, additive full-list `energy_sources` mutations through `EnergyManager.async_update`, explicit flush/readback of delayed Energy storage, strict journal+fingerprint validation and limited rollback. All associated tests use synthetic fixtures. **A validated backup is not a tested restoration**, and internal locking cannot exclude unrelated native HA writers without cross-component coordination.

**Blocking:** the independent full history/Recorder/retired physical meter and alternative-statistic guarantees from #36/#37 are not yet established, so L6 cannot emit any admissible new source; the new port is deliberately not registered or exposed by the UI. Live bulk enrollment is **not operational**, and the delivery candidate cannot be considered qualified or published. No production HA action, migration, restore, merge, release, or installation has occurred or is authorized.
