# 🤖 #88 — Recette de sauvegarde et reprise / Backup and recovery acceptance

> **Recette réelle 0.3.4b1 / Real acceptance:** aucune plateforme HA de test n'est disponible. La recette en lecture seule et toute opération de production explicitement autorisée suivent [le protocole de production](PRODUCTION_ACCEPTANCE_0.3.4b1_FR_EN.md). Les scénarios de pannes, corruption, restauration destructrice ou concurrence artificielle décrits ci-dessous restent **réservés aux fixtures synthétiques**, sans toucher à l'installation réelle. / No HA staging system is available. Separately approved production acceptance follows the linked protocol; destructive fault, corruption and restore drills below remain synthetic-only. Aucun feu vert de release n'est déduit de ces tests. / This does not authorize release.


## FR — Procédure de qualification future, non exécutée sur Home Assistant

**État : dossier de test, pas de recette de production.** Les vérifications sur répertoire `tmp_path` prouvent exclusivement le comportement simulé des fichiers de préférences, sauvegarde et journal. Elles **ne démontrent ni BackupManager natif, ni transaction atomique, ni restauration HA réelle**.

### Conditions préalables obligatoires

1. Contrats finalisés et vérifiés de #36 (consolidation, version B15, persistance de toutes les fenêtres Recorder), #37 (inventaire exhaustif actif/déposé, absence de doubles comptes) et #120 (identités nouvelles sans migration). Exclure #82 et ne pas modifier les identifiants historiques.
2. Home Assistant cible, version, schéma `water`/`gas`, mappage chauffage CET kWh, droits administrateur, emplacement de la sauvegarde et procédure de restauration documentés et testables.
3. Environnement **isolé et fictif**, sans connexion au portail réel, sans instance réelle ni données privées. Relever les empreintes avant/après, les sources tierces, les variantes de statistiques et les autorisations.
4. Backend natif futur audité indépendamment : sauvegarde *récupérable* qui inclut la configuration Energy pertinente, journal durable, verrou exclusif, gestion de concurrence et de redémarrage. Vérifier les API Home Assistant de la version effectivement prise en charge avant toute activation.

### Matrice de test isolée

| Situation | Résultat exigé |
|---|---|
| Source absente et trois séries indépendamment prouvées | Prévisualisation des ajouts EF/ECS/CET ; confirmation distincte ; écritures minimales |
| Source Trybatec déjà configurée | Aucun doublon ; résultat idempotent |
| Version active et version concurrente sélectionnées | Refus avec explication ; aucune écriture |
| Compteur déposé absent de la consolidation | Refus ; signalement de couverture incomplète |
| Unités/classes Recorder incorrectes, données non persistées | Refus ; retour vers la configuration |
| Contrôle utilisateur non administrateur | Refus avant sauvegarde ou mutation |
| Aperçu devenu périmé | Refus par empreintes ; aucune écriture |
| Sauvegarde inexistante ou non restaurable | Refus avant mutation |
| Journal pré-écriture non durable | Refus avant mutation |
| Échec d'écriture ou de vérification | Retour arrière conditionnel, relu et certifié ; sinon incident manuel |
| Modification tierce concurrente | Aucun écrasement des préférences tierces |
| Redémarrage avec journal `prepared` | Analyse des empreintes ; aucun réessai aveugle |
| État partiel mémoire/disque ou rollback échoué | Incident manuel persistant ; aucun succès déclaré |
| Navigation FR/EN, thèmes, clavier et lecteur d'écran | Statuts explicites, bouton désactivé jusqu'aux garanties et repli #83 |

### Critères avant recette réelle

Obtenir d'abord une **autorisation distincte** décrivant l'environnement précis et les opérations permises. Produire un protocole de sauvegarde/restauration native vérifiée **hors production**, puis une stratégie de secours. N'exécuter aucun test d'écriture ou de restauration sur l'installation réelle sans nouvelle décision explicite. La CI seule ne prouve jamais la recette réelle ni l'intégrabilité L7.

## EN — Future acceptance procedure, not executed on live HA

**Status: test plan, not production acceptance.** Temporary-folder tests prove only synthetic preference, backup and journal file mechanics; they **do not** establish native BackupManager, atomic HA Energy persistence or actual HA restoration.

Required gates: finalized #36 Recorder full-bucket consolidation and version contracts, #37 exhaustive active/retired meter coverage, #120 new-account stable identity without #82 migration; independently verified installed HA version and `water`/heating category mapping; a separately audited native backend; an isolated synthetic HA environment with no vendor account or production data; a recoverable HA backup and documented restore exercise. No live action before specific authorization.

Test all of the following on isolated fixtures: unconfigured EF/ECS/CET, already configured idempotence, competing versions, retired-meter gaps, wrong units/Recorder classes, absent persisted buckets, third-party energy sources, non-admin refusal, stale preview, backup creation/verification failure, failed journal durability, apply failure, readback mismatch, failed or partial rollback, concurrent third-party changes, crash before/after persistence, and FR/EN accessibility. Verify exact before/after fingerprints and re-read storage rather than trusting a UI flag.

Before any real HA testing, the user must separately approve its precise target, data, actions and consequences. No restore/import/Energy modification is permitted under the present task. The L7 draft remains blocked until native/isolated acceptance and historical contracts are demonstrated.
