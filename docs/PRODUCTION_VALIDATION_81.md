# 🤖 Recette progressive / Progressive production validation (#81)

## Français — Décision d'architecture et conditions de recette

**Statut : protocole préparé, NON exécuté sur la production.** La présence d'une sauvegarde avec métadonnées complètes ne prouve ni sa lisibilité, ni une restauration réussie. Aucune opération sur Home Assistant, y compris rechargement et installation, n'est autorisée par cette documentation.

### Effets de la branche #82 lors du chargement

- Pour une entrée historique sans l'option stable_meter_identities=true, le coordinateur ne construit pas de StableUnitGuard et le capteur conserve la génération historique de son unique_id. Un simple chargement ne lance pas migration_executor_81.
- Le setup enregistre les services historiques (leur exécution/import reste une action explicite), le panneau administrateur et la plateforme sensor ; après démarrage, le coordinateur interroge le fournisseur et peut publier des valeurs normales. Home Assistant peut écrire les états et statistiques habituels via Recorder. L'installation n'est donc pas une opération zéro effet.
- L'exposition de capteurs et d'appareils lors du premier polling peut écrire le registre Home Assistant et créer des entités normalement ; ce n'est pas une migration explicite, mais doit être observé.
- Pour une nouvelle entrée dotée de stable_meter_identities=true, les identités stables sont actives dès le départ et le registre local des unités sources est écrit avant des publications cumulatives approuvées. Le stockage local peut donc changer lors d'une récupération de mesures.
- Les imports historiques Recorder, la sélection Énergie et l'exécuteur de migration restent des chemins distincts nécessitant une action explicite ; les erreurs fournisseur peuvent laisser les valeurs indisponibles et déclencher une notification locale.
- Une ancienne entrée ne passe en mode stable qu'à travers l'activation explicite et journalisée, encore non raccordée à une procédure de production approuvée. Ne pas lever dependency_inventory_complete=False.

### Matrice des risques (gravité / maîtrise constatée)

| Scénario | Gravité | Maîtrise | Déclenchement et effets possibles | Détection / arrêt | Récupération ciblée ou complète |
|---|---|---|---|---|---|
| 1. Chargement Trybatec en échec | Importante | Partielle | Mise à jour/reload, API cassée, capteurs indisponibles | Erreurs d'entrée et absence de valeurs ; arrêter si l'intégration ne se recharge pas | Revenir à la version antérieure, puis reload autorisé ; restauration complète seulement si les registres/configurations ont été altérés |
| 2. Communication fournisseur perdue | Importante | Partielle | Panne cloud, authentification ou réseau ; mesures périmées | Poll en échec, capteurs indisponibles, notification ; ne pas migrer sans snapshot actuel | Rétablir accès, laisser les données historiques intactes ; pas de restauration de la base en première intention |
| 3. Collision entité ou appareil | Critique | Partielle | Identité nouvelle occupée, appareil réutilisé ou doublon | Comparer registries complets et résultats de collisions ; arrêter avant toute écriture | Revenir au code précédent si non migré ; sinon rollback journalisé seulement si propriétaire intact ; restore si registre détruit |
| 4. Identifiant physique incorrect | Critique | Partielle | Mauvais appariement ou modification explicite unique_id | Diff avant/après, fingerprint, propriété ; stopper dès la moindre divergence | Rollback ciblé vérifié ; restauration complète si référence d'appareil ou registre irrécupérable |
| 5. Consommateurs invalides | Importante | Non démontrée | Références externes anciennes unique_id, automatisations et tableaux dynamiques | Contrôle de chaque consommateur ; arrêter si surface masquée ou dépendance cassée | Correction de référence ciblée avant migration ; restore de config si dépendances massivement altérées |
| 6. Migration partielle | Critique | Partielle | Interruption entre alias, unique_id, activation et reload | Journal persistant, états prepared/rollback_incomplete ; aucune relance aveugle | Inverse ciblé uniquement après preuve de propriété ; restore si journal et registre incohérents |
| 7. Redémarrage HA échoué | Critique | Partielle | Update/reload suivi de restart, dépendance cassée | Contrôler services essentiels, démarrage et santé globale ; arrêter les changements | Réinstaller version précédente et redémarrer seulement si nécessaire ; restauration si HA ne démarre plus |
| 8. Recorder corrompu ou réinterprété | Critique | Partielle | Modification d'échelle/metadata ou série écrite par autre action | Comparer metadata/unités et séries ; arrêter aux premiers écarts | Ne pas éditer la DB en direct ; restaurer la base après évaluation de la perte de données depuis la sauvegarde |
| 9. Énergie étrangère modifiée | Critique | Partielle | Import ou écriture de préférences hors #81 | Comparer les trois catégories, y compris statistiques et inclusion ; arrêt sur divergence | Restaurer uniquement les préférences exactes si avant-state complet ; restauration entière si non récupérable |
| 10. Rollback échoué | Critique | Non éprouvée | Collision inverse, journal corrompu, mutation concurrente | Statut rollback_incomplete ; suspendre toute nouvelle exécution | Diagnostic de propriétaire/registre, puis restauration complète si inverse non sûre |
| 11. Restauration échouée | Critique | Non maîtrisée | Archive illisible, clé erronée, base externe, destination perdue | Vérification en environnement isolé non exécutée | Contacter procédure de récupération propre à HA ; ne pas écraser la production pour tester |
| 12. Données post-sauvegarde perdues | Critique | Non maîtrisée par restore | Une restauration remplace les composants sélectionnés par leur état de sauvegarde | Mesurer l'écart temporel et les modifications survenues | Réduire le périmètre de restore ou éviter l'opération ; ne jamais promettre le retour exact à l'instant de panne |

Les niveaux ci-dessus sont des évaluations de risque, pas des incidents constatés. La réussite de la CI ne prouve pas l'absence d'un défaut en production.

### Recette graduelle R0 à R5

| Niveau | Nature | Pré-requis | Conditions d'arrêt | Autorisation |
|---|---|---|---|---|
| R0 — Observation | Version, registres, 7/plusieurs générations, Recorder, Énergie, consommateurs, sauvegardes (lecture seule) | Aucun changement de l'installation | Snapshot incomplet ou contradictoire | Lecture seule autorisée |
| R1 — Synthétique | Pytest HA, incidents simulés, collisions, unités, reload legacy, refus, sauvegardes/restore fictifs | Données fictives, framework HA et CI | CI échoue / test de sécurité manquant | Développement GitHub autorisé |
| R2 — Prévisualisation réelle | Afficher plan et les blocages sans écriture ; pas de migration | Candidate disposant d'une action sûre ou autre voie read-only vérifiée | Preview absent, incomplet, inconnu ou désaccord | Aucune écriture ; ne pas déployer pour cela sans accord |
| R3 — Chargement candidate | Installation manuelle du SHA exact, compte historique non migré, vérification avant/après | Nouvelle autorisation ; sauvegarde/retour arrière/impact documentés ; automatisation d'update/redémarrage traitée | Identité, appareil, mesure, Recorder ou automation inattendus | Validation séparée impérative |
| R4 — Migration effective | Transaction ponctuelle + confirmation d'empreinte et sauvegarde | Inventaire externe exhaustif et vérifiable, restauration éprouvée, tests R0–R3, droits et autorisation R4 | Contradiction ou preuve manquante : REFUS | Validation séparée impérative |
| R5 — Récupération | Rollback ciblé si prouvé sûr, sinon restauration exceptionnelle | Avant-state, journal, sauvegarde et estimation des données post-sauvegarde | Inverse ambigu, copie illisible : escalade, jamais forcer | Validation séparée impérative |

Ne jamais provoquer de panne intentionnelle sur la production pour démontrer R5. L'absence de plateforme isolée maintient la restauration effective au statut NON ÉPROUVÉ. Une simulation en CI ne la remplace pas.

### Préparation d'une candidate R3 — à faire approuver avant toute action

1. Consigner SHA GitHub exact, commit de main, versions Core/intégration, périmètre du diff, manifeste et mode d'installation manuelle. Aucun tag ni release sans autorisation.
2. Capturer localement et de manière privée les quatre classes d'identifiants, compteurs, unités, metadata Recorder, catégories Énergie, automatisations et tableaux.
3. Vérifier l'archive de sauvegarde, une copie hors VM déclarée achevée, la disponibilité de la clé auprès de l'utilisateur ; **ne pas** copier, déchiffrer ou restaurer l'archive sans autorisation.
4. Vérifier et traiter par une décision distincte l'automatisation pouvant installer automatiquement une update et redémarrer HA ; ne pas modifier sa configuration sans accord.
5. Préparer le paquet candidat et le rollback vers la version installée avant R3, vérifier checksum, source et absence de modifications de configuration non liées.
6. Après autorisation expresse, installer puis comparer avant/après sans déclencher de migration : mêmes identités physiques, entity_id, unique_id, device_id, statistiques, préférences et consommateurs. Vérifier une disponibilité fournisseur suffisante.
7. Arrêter à toute création/requalification imprévue, collision, erreur d'unité, anomalie Recorder ou automatisation de mise à jour intempestive. Aucune restauration automatique.

### Décision sur la prochaine préversion

Une livraison **sans migration des entrées existantes** peut être étudiée si l'ancien mode est préservé et si les tests de rechargement/absence de migration réussissent. Les identités stables pour de nouvelles installations et les diagnostics peuvent être livrés séparément à condition de considérer cette livraison comme **intermédiaire et non comme une clôture de #81**. Un changement du périmètre de la PR #82 ou de ses critères exige une décision explicite de la MOE/utilisateur. Aucune release, installation ou fusion n'est autorisée par ce document.

## English — Progressive production-only acceptance

**Status: prepared, NOT performed on the live Home Assistant instance.** A complete listed backup is not a proven restoration. This document authorizes no installation, restart, migration or restore.

### Actual code behavior on load

- Legacy accounts without stable_meter_identities=true keep their legacy meter unique IDs; normal startup does not invoke the one-time migration executor. A read-only audit cannot change those identities.
- Setup registers opt-in history services, the admin panel and sensor platform. Once Home Assistant starts, normal polling may update sensor states and Recorder's ordinary history/statistics. This is not a zero-side-effect operation.
- Normal sensor registration may register entities/devices; a source outage may leave them unavailable and show a local warning. New stable accounts may durably save a source-unit baseline before permitting cumulative statistics.
- History imports, Energy preference changes, and one-time identity migration remain separate explicitly invoked operations. Never bypass dependency_inventory_complete=False.

### Risk matrix (severity, evidence and recovery)

| # | Scenario | Severity | Control | Detection and safe recovery |
|---|---|---|---|---|
| 1 | Integration load failure | High | Partial | Inspect setup errors/availability; roll back code without altering Recorder, restore configuration only if necessary |
| 2 | Portal unavailable | High | Partial | Failed polls/unavailable values; recover connectivity, do not migrate stale evidence |
| 3 | Entity/device collision | Critical | Partial | Full native registry and ownership checks; refuse migration and perform reviewed inverse or restore if registry damaged |
| 4 | Incorrect identity reassignment | Critical | Partial | Fingerprint and before/after comparisons; journaled inverse only if current owner matches |
| 5 | Broken external consumers | High | Unproven | Complete dependency inventory required; update individual consumers or restore configuration when narrow recovery impossible |
| 6 | Interrupted transaction | Critical | Partial | Persisted journal and no automatic retry; explicit idempotent rollback where safe |
| 7 | HA restart failure | Critical | Partial | Check host/integration health; revert candidate or restore only when required |
| 8 | Recorder loss or scale change | Critical | Partial | Compare metadata/series, never edit DB directly; recovery must consider post-backup data loss |
| 9 | Unrelated Energy preferences change | Critical | Partial | Compare all three categories, restore specific prefs from known before-state only |
| 10 | Failed rollback | Critical | Not tested live | Keep rollback_incomplete, refuse re-execution, escalate to proven recovery |
| 11 | Failed restore | Critical | Not tested | No isolated target available; do not test on the sole production host |
| 12 | Changes since backup lost | Critical | Not eliminated | A full restore overwrites selected components with older state; calculate the data loss window |

### R0–R5 gates

- **R0:** read-only production inventory and backup metadata, with private before-state and clearly stated blind spots.
- **R1:** synthetic HA integration tests for old/stable accounts, unit changes, collisions, source outages, simulated resume/rollback and fake restoration; CI must pass on the exact SHA.
- **R2:** real read-only preview only when a safe provider exists. The current installed release may not expose it; installation to enable R2 needs separate approval.
- **R3:** candidate load only after explicit authorization identifying SHA, data, installation method, backup, existing auto-updater risks, stop conditions and targeted downgrade. Do not implicitly migrate old accounts.
- **R4:** live identity mutation only with independently verified external consumers, tested recovery, fresh fingerprint, explicit confirmation and all safety gates. Otherwise reject.
- **R5:** prefer a verified exact inverse; a full restore is exceptional, requires new approval and can erase every selected change made since the backup. Never deliberately break production to test recovery.

### Decision gate

An intermediate release with stable identities for NEW accounts and read-only diagnostics, while leaving EXISTING-account migration locked, is a plausible **option, not an accepted scope change**. It requires explicit approval of any PR/acceptance-criteria split, complete regression checks and a separate release authorization. No deployment or publication is authorized here.
