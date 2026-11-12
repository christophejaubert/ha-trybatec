# 🤖 L7 — Ajout groupé sécurisé / Guarded bulk Energy enrollment

## FR — Statut **brouillon non intégrable**

**Dépendances bloquantes :** #36 (persistance/continuité des consolidations), #37 (filiation exhaustive des compteurs déposés), #120 (identités des nouveaux comptes, sans migration #82). Le moteur L7 est un **automate de transaction non raccordé à Home Assistant** ; il ne dispose d'aucun adaptateur natif autorisé de sauvegarde, de journalisation ou d'écriture. Il est **impossible de déclencher un ajout réel** depuis le panneau ou le démarrage. Son caractère testable avec un port synthétique ne vaut pas intégrabilité de la release `0.3.4b1`.

### Contrat

`custom_components/trybatec/energy_bulk_transaction.py` définit :

- `ServerEnergyState` : données de lecture reconstituées exclusivement par un futur backend administrateur.
- `EnergyPreview` : diagnostic purement informatif, empreintes et identifiant de proposition ; `writes=False`, `activation_authorized=False`.
- `EnergyTransactionPort` : interface abstraite vers les opérations HA natives à **implémenter uniquement après stabilisation**.
- `preview_bulk_energy_transaction()` : aperçu sans écriture.
- `apply_bulk_energy_transaction()` : action explicitement confirmée, refusant les preuves périmées, usurpées, partielles ou contradictoires.

Les étapes du moteur sont : (1) contrôle administrateur serveur, (2) verrou exclusif sur la transaction, (3) reconstruction des preuves L6 et du plan #92, (4) contrôle des empreintes mémoire/disque, (5) sauvegarde et vérification de récupérabilité, (6) nouvelle vérification de concurrence, (7) journal durable avant modification, (8) écriture de la seule section `energy_sources`, (9) flush/relecture mémoire/disque, (10) journal de validation, (11) rollback **uniquement si les états correspondent exactement** à la modification prévue, puis relecture. Une modification tierce ou un rollback partiel conduit à `EnergyRecoveryRequired` : **ne jamais écraser un état tiers**.

**L7 ne prend actuellement en charge que l'ajout, pas le remplacement.** Les anciennes sources ou versions sélectionnées sont bloquantes. Toute substitution doit réutiliser et qualifier séparément les parcours B15/B17 existants ; ne pas maquiller le remplacement en premier ajout. Les tarifs annuels ne conditionnent pas l'ajout de la consommation seule ; aucun prix ou coût historique n'est inventé.

### Résultats de tests et limites

- 22 cas synthétiques L7 : administrateur, confirmation, 3 fluides, prévisualisation, sauvegarde refusée, journal impossible, échec avant/après écriture, vérification persistée, rollback, concurrence, restauration incomplète, sources tierces, unité, validation CET et remplacement refusé.
- Aucun appel à la base Recorder, fournisseur, Home Assistant réel ou sauvegarde de production.
- Les simulateurs peuvent produire artificiellement `admissible` pour vérifier l'automate ; **le L6 réel ne peut pas produire cet état actuellement**.
- Les API HA natives de sauvegarde, persistance, journal, validation de schéma, accès administrateur et le panneau UI doivent être raccordés/testés avant toute intégration.
- **Vue UI FR/EN autonome testée sur DOM simulé**, bouton définitivement désactivé ; la recette réelle sur navigateur, thèmes, clavier/lecteurs d'écran et panneau HA reste à réaliser.
- Aucun test de restauration réelle. La CI GitHub est suivie sur le SHA exact de la PR #130 (distincte de ces tests locaux). Aucune recette métier.

### Critères de déblocage L7

1. Fonction de preuve serveur indépendante par fluide validée par #36/#37 ; provenance et couverture complètes garanties.
2. Adaptateur HA concret : authentification via `hass.auth`, verrou partagé, version/schéma natif exact, sauvegarde réellement récupérable, journal persistant, transaction Energy validée, échec/rollback et reprise post-crash.
3. Compatibilité avec les appareils et compteurs de #120 sans changement de l'identité historique ; aucune migration de #82.
4. Interface native admin : aperçu, statuts explicites, motifs, liens de repli #83, contrôle unique de confirmation, accessibilité #70 ; ne pas afficher un bouton activable avant réussite des prérequis.
5. Tests réels du schéma Home Assistant ciblé, défaillances et persistance, browser acceptance, CI sur SHA final, puis **recette métier sur installation représentative après autorisation**.

## EN — Status **non-mergeable draft**

L7 is a dormant, dependency-injected transaction engine. It is not registered as a Home Assistant endpoint or startup hook; it has **no production backup, journal or Energy write adapter**. Missing #36/#37 historical/physical proofs and #120 nonmigrating identity contracts prevent real enrollment.

The engine specifies administrator re-verification, an exclusive guard, fresh native L6 evidence and #92 planning, optimistic state fingerprints, recoverable backup verification, durable prewrite journal, a minimal `energy_sources` change, persisted readback, and safe rollback only while the exact intended state remains current. Conflicting third-party changes require manual recovery and MUST NOT be overwritten. All preview replies retain `writes=False`, `activation_authorized=False`; no browser boolean, `statistic_id` or read-only preflight state is an authorization.

**Addition vs replacement:** L7 deliberately supports new additions only. Selected competing sources are refused and should be routed to separately qualified existing B15/B17 replacement/handoff procedures. Prices/costs are not inferred from tariffs. Synthetic tests use fake backends; they do not test native HA backup/restore, Recorder or genuine Energy persistence. Native HA panel integration, real-browser accessibility and HA recovery/business acceptance remain required; the standalone FR/EN disabled preview is already covered synthetically. The PR must stay draft until those gates are satisfied.

**References:** [#88](https://github.com/christophejaubert/ha-trybatec/issues/88), [#36](https://github.com/christophejaubert/ha-trybatec/issues/36), [#37](https://github.com/christophejaubert/ha-trybatec/issues/37), [#120](https://github.com/christophejaubert/ha-trybatec/pull/120), [HA Energy 2026.11.1](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/energy/data.py).

---

## FR — Extension L7 : journal, reprise et observateur HA (PR #130, itération 2)

Le moteur L7 exige désormais `read_last_journal()` **avant sauvegarde** et vérifie par relecture que l'enregistrement pré-écriture (`prepared`) a réellement été persisté **avant toute modification**. Une transaction précédente non terminée bloque une nouvelle opération ; la réussite exige également une relecture du journal final. Le port de test et les cas de refus ont été adaptés.

- `energy_bulk_recovery_l7.py` : diagnostic de reprise sans écriture Énergie, à partir du journal durable et des empreintes mémoire/disque. Seuls `avant/avant` et `après/après` peuvent, sur action administrateur explicite et après revérification de la sauvegarde, entraîner une mise à jour **du seul journal**. Les états mixtes, inconnus ou modifiés par une source tierce nécessitent une récupération manuelle : aucune restauration implicite.
- `energy_bulk_native_observer_l7.py` : port Home Assistant **strictement en lecture seule**. Il vérifie l'utilisateur dans `hass.auth`, la portée compte/lot, les préférences mémoire/disque et la réponse L6 reconstruite depuis le serveur. Toutes ses méthodes d'écriture, de sauvegarde, de journal et de persistance échouent explicitement. Aucune commande, service ni WebSocket n'est enregistré.
- `panel/energy-bulk-draft-l7.js` : élément UI autonome FR/EN, statuts EF/ECS/CET, motifs d'échec, repli #83 et bouton **toujours désactivé**. Aucun import ou changement du panneau partagé #42/#70 ; pas de point d'entrée vers une action.
- Tests : journal non durable, transaction antérieure en suspens, conflits, autorisations, reprise après redémarrage simulé, copie de sauvegarde et restauration **sur répertoire temporaire fictif**, journal corrompu ou inaccessible, interface statique FR/EN et contrôle d'injection DOM. Les preuves sont entièrement synthétiques.

**Ce qui n'est pas livré :** port natif capable de sauvegarder/restaurer/configurer Énergie, contrat de sauvegarde restaurable de l'instance HA, action backend d'activation, recette Recorder réelle, tests d'écriture de production, activation ou fusion. Ces éléments attendent #36/#37/#120 stabilisés et les autorisations séparées.

Voir `docs/ENERGY_BULK_L7_RECOVERY_RUNBOOK.md` pour la procédure de qualification future.

## EN — L7 extension: durable journal, recovery and native HA observer

L7 now reads the last durable journal before backup and verifies read-after-write of its `prepared` record **before any Energy change**. An unresolved previous journal blocks new attempts. A final success also requires a readable durable journal record.

The pure `energy_bulk_recovery_l7.py` reconciles only unambiguous both-before or both-after states, via a separately confirmed administrator action and a still-verified backup; it changes **journal records only**. Mixed/unknown/concurrent states require manual investigation and are never silently overwritten. `energy_bulk_native_observer_l7.py` verifies HA administrator identity, account/lot scope, and memory/persisted preferences, but explicitly refuses *all* write, backup and journal operations. A standalone FR/EN DOM-only preview component shows all utility decisions and a **permanently disabled** activation button, without editing the shared #42/#70 panel or registering an endpoint.

All recovery and restore tests use synthetic data and a temporary local directory. They are not native HA backup/restore proof. No live Recorder/Energy writes, source replacement, legacy-ID migration, merge, release or Home Assistant installation are included. See `docs/ENERGY_BULK_L7_RECOVERY_RUNBOOK.md` for the future acceptance protocol.
