# 🤖 #36 — Scénarios Recorder et restauration / Recorder recovery acceptance

**Cible / Target:** `0.3.4b1` — PR #128; tests sur base fictive isolée uniquement / isolated synthetic Recorder only.

## FR — Préconditions non négociables

1. Environnement Home Assistant **isolé de la production**, compte, lot, numéros de compteurs, index, statistiques et préférences Énergie **tous fictifs**. Aucune connexion à l'installation utilisateur, aucun jeton ni donnée de consommation réelle.
2. Capturer version HA exacte, schéma Recorder, SHA du code et des fixtures, copie complète de la base et des préférences Énergie de test ; vérifier **sur la copie** la capacité de restauration avant toute simulation de panne.
3. Simuler une file différée, son achèvement et l'absence de writer actif ; ne pas assimiler un `enqueue` à une écriture persistée.
4. Enregistrer le hash des snapshots V1/V2/V3 et celui du journal; toute mutation non approuvée, chevauchement entre générations ou divergence doit bloquer la suite.
5. Ne jamais activer le basculement Énergie si les preuves #37 de filiation, #88 de complétude et d'exclusivité, et la confirmation administrateur sont absentes.

## Matrice FR — séquence, preuve et refus attendu

| ID | Séquence synthétique | Résultat / preuve exigée |
|---|---|---|
| REC-01 | Créer V1, stocker le journal `prepared`, puis `imported` avant le premier enqueue | Après interruption, aucune version `verified` ou `active` fictive ; journal récupérable |
| REC-02 | Enqueue V1 complet, lecture partielle ou différée | `pending_recorder_readback`, lignes manquantes détaillées, aucune activation |
| REC-03 | Lire V1 complète, même horodatage UTC et sommes pour chaque bucket attendu | `persisted_verified_no_requeue`, transition `verified` uniquement après persistance |
| REC-04 | Ajouter un bucket supplémentaire, dupliquer un timestamp, altérer une somme | Vérification refusée, aucune reprise automatique |
| REC-05 | Couper après la première série d'un batch EF/ECS/CET fictif ; laisser une série persistée, une série absente, une série partielle | Lecture indépendante par ID ; la persistée jamais rejouée, la partielle bloque tout rejeu |
| REC-06 | Redémarrer l'instance de test, restaurer le journal de versions, relire Recorder | Pas de perte d'état validé ; aucune écriture au démarrage |
| REC-07 | Demander `retry_pending` en présence d'un writer possiblement actif / réponse incomplète | Refus sécurisé, aucun nouvel enqueue |
| REC-08 | Demander `retry_pending` sur toutes lignes effectivement persistées | Résultat idempotent : aucun nouvel enqueue, journal vérifié |
| REC-09 | Préparer V2 avec empreinte source différente sans approbation, puis avec approbation | Premier refus, seconde préparation ; V1 inchangée |
| REC-10 | Vérifier V2 mais refuser confirmation Énergie / modifier les préférences entre prévisualisation et application | V2 vérifiée mais non active ; ancien ID conserve la sélection |
| REC-11 | Préparer, vérifier puis activer V3 sur fixtures, avec preuve de préférence enregistrée puis relue | V1/V2 archivées, V3 seule active, pas de double comptage |
| REC-12 | Échec simulé de sauvegarde du journal après mise à jour Énergie | Restaurer les préférences fictives, relire et prouver l'état `rolled_back` |
| REC-13 | Tenter retour V1 sans consentement spécifique ou depuis un schéma/statistique incompatibles | Refus ; avec approbation, snapshot V1 conservé et sélection exclusive vérifiée |
| REC-14 | Trois générations physiques successives d'un même fluide, discontinuité, changement de fuseau et 23/25 h | Additionner uniquement les consommations admissibles ; jamais les index cumulés ; zones inconnues explicites |
| REC-15 | API Recorder indisponible, lecture tronquée, somme non finie ou unité incompatible | Bloquer preuve et activation ; conserver un diagnostic expurgé et la possibilité de récupérer hors production |
| REC-16 | Simuler changement concurrent de la configuration Énergie ou d'une version pendant validation | Empreinte obsolète ; aucun écrasement des sources tierces |

**État réel :** les tests Python existants couvrent une partie des garanties REC-03/04/07/08/09/10/11/12/13, mais cela ne vaut pas exécution exhaustive de cette matrice sur HA isolé, ni restauration prouvée. REC-05/06/14/15/16 exigent encore une recette systémique documentée.

**Verrou opérationnel :** le rejeu sélectif d'une série absente est **désactivé** tant qu'un mécanisme indépendant ne prouve pas la quiescence du writer et l'absence de série persistée. Aucun faux drapeau `complete` ou `queue_quiescent` issu du navigateur ne saurait y suppléer.

## EN — Mandatory isolation and acceptance evidence

Run all scenarios on a synthetic Home Assistant instance with fictional meter IDs, observations, statistical IDs, Energy preferences and a demonstrably restorable test backup. Record the HA version, fixture SHA, exact code SHA, pre/post Recorder rows, version journal and preference snapshots. Never connect to the user's actual integration or copy its secrets or consumption values.

REC-01..08 verify that pending intent survives failures, incomplete/extraneous rows fail closed, complete Recorder rows are read back before verification, and an idempotent replay does **not** enqueue a persisted statistic. A partial or writer-active batch must not be replayed.

REC-09..13 cover immutable V1→V2→V3, explicit revision and Energy approvals, preferences readback, stale-fingerprint rejection, compensating rollback and separately approved restoration to an archived version. REC-14..16 cover successive physical devices and DST, unavailable/invalid Recorder metadata, and concurrent version or Energy changes.

**Outstanding acceptance:** real-world independent writer-quiescence proof, repeated crash/restart on an isolated Recorder database, full multi-generation lineage (#37), native Energy eligibility (#88), and a documented restoration rehearsal. These remain blocked for the user's real Home Assistant. Neither a passing PR CI nor this document authorizes a restore, merge, release or production write.
