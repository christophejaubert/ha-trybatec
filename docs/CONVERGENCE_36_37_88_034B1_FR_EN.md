# 🤖 Convergence fonctionnelle #36/#37/#88 — 0.3.4b1
# Functional convergence #36/#37/#88 — 0.3.4b1

## FR — Statut et provenance

**État : développé en branche de preuve, non fusionné, non recetté.** Le périmètre complet de #36, #37 et #88 demeure impératif pour **la même bêta 0.3.4b1** ; cette composition n'autorise ni réduction ni report. Le dépôt public ne contient ici aucune donnée réelle de mesure ou d'identification de logement.

Base : PR #147, commit \`20375ca9f05e828f26c43d9c14529981948b4f07\`. Fichiers repris par blob exact : PR #149 (8, #36 Recorder), PR #150 (6, #37 compteurs), PR #151 (6, #88 Énergie). Aucun merge des PR sources.

**Contrat intégré** :

1. \`history_plan_b15.make_b15_plan\` et \`history_variants_b15.variants_preview\` produisent les variantes et les journées depuis les choix validés côté serveur.
2. \`history_recorder_handoff_36.async_b15_recorder_handoff_36\` lit les versions, sommes, buckets UTC et métadonnées natives Recorder (sans import).
3. \`lineage_history_bridge_37.prepare_physical_continuity_37\` et \`lineage_energy_handoff_37.prepare_energy_lineage_handoff_37\` établissent les membres physiques, contributions et empreintes de filiation (sans migration).
4. \`energy_bulk_contract_ha_l6.async_crosscheck_native_l6\` lit l'inventaire L6 côté serveur après authentification administrateur, sans importer les déclarations du navigateur.
5. \`energy_bulk_native_convergence_034b1.async_collect_native_convergence_034b1\` compose ces contrats, puis \`reconcile_native_handoffs_034b1\` vérifie par fluide les comptes journaliers, quantités mesurées/estimées/mixtes, totaux, unités, version Recorder choisie, variantes Énergie observées et causes de refus. Le contrat est également raccordable à la prévisualisation lot B via son argument interne optionnel \`recorder_handoff_36\`.
6. Le port \`energy_bulk_native_port_l7.HAGuardedEnergyPort\` de #151 reste non enregistré ; il n'est pas exposé par websocket et ne peut donc pas modifier Énergie sur production.

L'orchestrateur est **une fonction interne**, sans service ni route Home Assistant, et reçoit les relevés/approbations exclusivement de code serveur de confiance. Il ne constitue pas une nouvelle base de données ou source de vérité. Une empreinte, une série apparemment continue, une lecture de quelques périodes ou une décision d'affichage ne suffisent jamais à accorder l'écriture.

## FR — Verrous à lever AVANT livraison fonctionnelle complète

| Chantier | Écart technique | Preuve nécessaire |
|---|---|---|
| #36 | \`async_block_till_done()\` n'exclut pas une tâche Recorder tardive | Protocole réel de quiescence/exclusivité, relecture intégrale et reprise sûre, sans oracle synthétique en production |
| #36 | Versions et couverture ne démontrent pas nécessairement l'absence de séries étrangères | Inventaire des statistiques et des journées complètes, approbations datées liées aux consommations |
| #37 | Inventaire actuel/déposé non prouvé exhaustif | Toutes générations physiques, périodes de service, lacunes, conflits et références alternatives |
| #88 L6 | Classification reste \`insufficient_evidence\`/refus pour les nouvelles sources | Évidence issue des contrats authentifiés et exhaustive, pas seulement de booléens/empreintes |
| #88 L7 | Port de sauvegarde/journal/rollback sans route administrateur ni preuve de reprise réelle | Compatibilité API 2026.11.1, sauvegarde récupérable, transaction exclusive, disque/mémoire et reprise sûre |
| #88 UI | Aucun parcours d'activation réel \`Énergie et versions\` | Aperçu, diff, confirmation admin, résultat persisté, journal, navigation FR/EN/mobile |
| Chaîne | CI Gitleaks historique en échec sur PR spécialisées | Diagnostic ciblé par CI/CD, sans exemption ni scanner affaibli |
| Recette | Aucune plateforme de test HA séparée | Recette progressivement autorisée sur production ; incidents destructifs exclusivement synthétiques |

**Important :** le nouveau rapprochement des dates, totaux et références donne un diagnostic utile, **pas** l'admissibilité L6 ni l'activation L7. Tous les champs \`admissible\`, \`activation_authorized\`, \`recorder_writes\` et \`energy_writes\` restent \`false\`. En l'absence d'une preuve fiable contre l'écrivain Recorder tardif, la reprise sélective reste bloquée.

## FR — Qualification et recette

Tests synthétiques : \`tests/test_energy_bulk_native_convergence_034b1.py\`, en complément des tests existants repris des trois PR. Les résultats CI ne sont qualifiés qu'au **SHA exact** de cette branche, indépendamment des résultats des PR sources.

Protocole réel : \`docs/PRODUCTION_ACCEPTANCE_0.3.4b1_FR_EN.md\`. Toute sauvegarde, installation, écriture Recorder/Énergie, restauration, fusion ou publication exige l'autorisation spécifique correspondante. Les preuves de production restent privées. Ne jamais simuler une restauration destructive sur l'installation de production.

## FR — Vérification de l'API HA Core 2026.11.1 (source versionnée)

Contrats consultés **sur le tag exact 2026.11.1**, et non uniquement sur la branche de développement :

- [BackupManager.async_create_backup](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/backup/manager.py) attend la fin de \`_backup_finish_task\` ; cela établit l'attente de génération mais **pas** une preuve de restauration réelle.
- [BackupManager.async_can_decrypt_on_download](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/backup/manager.py) vérifie le déchiffrement du flux, **pas** le succès d'une restauration des préférences et de Recorder.
- [EnergyManager.async_update](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/energy/data.py) diffère la sauvegarde de **60 secondes**. Le port L7 propose donc \`Store.async_save\` suivi d'une relecture du fichier réel.
- [Store.async_save et _async_handle_write_data](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/helpers/storage.py) attendent l'écriture et nettoient le délai de sauvegarde en cours. Cela ne garantit pas l'exclusivité face à tous les autres composants.
- Les [API d'import Recorder](https://github.com/home-assistant/core/blob/2026.11.1/homeassistant/components/recorder/statistics.py) mettent des tâches en file ; une barrière de commit n'établit pas seule l'absence d'un écrivain retardé.

Ces constats **ne lèvent aucun verrou** L6/L7 ni l'obligation de tests réels autorisés. Les portées des exceptions, versions et conflits d'écriture devront être revérifiées lors d'un changement de version Core.

## EN — Scope, contract and release gates

**Status: developed on a proof branch, not merged, not production-accepted.** Complete #36/#37/#88 functionality remains mandatory in **0.3.4b1**, without a silent deferral.

Starting from draft #147 at \`20375ca9f05e828f26c43d9c14529981948b4f07\`, this branch copies exact source blobs from #149 (eight Recorder files), #150 (six physical-lineage files), and #151 (six native Energy files), without merging those PRs.

The new \`energy_bulk_native_convergence_034b1\` component composes the canonical historical plan, the native #36 Recorder readback, #37 physical generations and daily lineage, and authenticated native #88 L6 audit. It compares daily measured/estimated/mixed quantities, totals, units, consolidated statistic identifiers and observed competing selections. The existing lot-B preview accepts an optional trusted Recorder handoff. No alternate ledger, automatic write hook or new websocket is created.

**This is diagnostic convergence, not operational enrollment.** Historical completeness and late-Recorder-writer exclusion remain unproven; L6 is not permitted to elevate asserted completeness, and L7 has no registered production route. Full activation UI, independently qualified backup/recovery, durable fencing, comprehensive alternatives inventory, Core 2026.11.1 API guarantees and separately authorized production acceptance are outstanding. Fail-closed guards must remain in force.

Synthetic tests are in \`tests/test_energy_bulk_native_convergence_034b1.py\`; exact-head checks and the public-privacy/Gitleaks gates must be reconciled before any merge decision. The existing FR/EN production-acceptance runbook remains authoritative for the real platform. No merge, release, deployment, backup, restore or production Recorder/Energy mutation is authorized by this work.
