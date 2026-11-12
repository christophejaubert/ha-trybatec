# 🤖 Restauration #81 / Restore acceptance #81

## Français — Protocole avant toute exécution réelle

**État du procès-verbal : NON EXÉCUTÉ / NON VALIDÉ.** Le contrôle de
métadonnées d'une sauvegarde HA, même complète et récente, **ne prouve
pas qu'elle peut être restaurée**. Ce document décrit les validations
restantes, sans créer de machine ni toucher la production.

### Autorisation préalable nécessaire

Avant toute création d'instance, copie hors du périmètre de lecture
ou restauration, présenter et faire approuver **séparément** :

1. L'environnement isolé choisi (hôte, emplacement, réseau, version HA,
   capacité de stockage et CPU/RAM, méthode de destruction).
2. Les données à copier (archive HA incluant configuration/Recorder,
   chiffrement, taille et agents de sauvegarde), sans divulguer de
   secrets dans GitHub.
3. Le destinataire des données et les personnes y ayant accès.
4. Les opérations exactes : transfert local, vérification, démarrage,
   restauration, comparaison, redémarrage et purge à terme.
5. Les risques de connexion accidentelle au fournisseur, au cloud,
   aux services domotiques et à l'installation de production.
6. Le plan de retour arrière et le traitement du mot de passe/kit
   d'urgence de sauvegarde (ne jamais le déposer dans le dépôt).

L'approbation du développement GitHub n'autorise aucune de ces actions
sur l'installation ou sur un hôte externe.

### Préparation — lecture seule

- Identifier dans BackupManager l'archive exacte, la date, le type,
  l'inclusion des paramètres HA et de la base Recorder, les destinations,
  les tailles et les erreurs signalées. Refuser une couverture incomplète.
- Déterminer si Recorder utilise une base externe ; dans ce cas, le
  contenu et la récupération de **cette** base doivent être traités
  séparément. Ne pas présumer qu'une archive HA suffit.
- Confirmer la disponibilité du fichier chiffré et du moyen de
  déchiffrement. Une liste de métadonnées ne prouve ni l'ouverture de
  l'archive ni la validité de la clé.
- Relever de manière privée les identifiants des entités, appareils et
  statistiques ; inclure les générations déposées et anciennes.
- Définir une copie **sans connectivité sortante**, notamment aucune
  communication fournisseur, MQTT, notifications, appareils, cloud ou
  services de tiers non explicitement nécessaires.

### Recette sur un environnement autorisé et isolé

1. Créer/provisionner la cible approuvée sans route vers la production.
2. Transférer la sauvegarde par le moyen approuvé ; vérifier
   intégrité cryptographique et lisibilité **avant** restauration.
3. Restaurer uniquement sur cette cible ; vérifier la présence de la
   configuration et de Recorder, les éventuels avertissements et la
   version exacte de Home Assistant.
4. Relever les registres d'entités et appareils, y compris identifiants
   et associations, comparer la **même** liste avant/après.
5. Relever les métadonnées Recorder (unités, classe, has_sum,
   statistic_id) et les bornes/valeurs d'échantillons représentatifs.
6. Comparer les trois catégories des préférences Énergie : aucune
   disparition, duplication ou substitution non prévue.
7. Vérifier que compteurs déposés et actifs restent distincts.
8. Redémarrer puis recharger l'intégration **sur la cible isolée**,
   vérifier la stabilité des identifiants et la cohérence persistante.
9. Exercer ensuite la migration dans l'environnement de recette,
   uniquement si ses propres garanties et sa confirmation explicite
   sont réunies ; contrôler le journal, l'interruption, la reprise,
   l'inverse et les observations avant/après.
10. Consigner les preuves sans secret ni valeur privée dans GitHub :
    seulement le statut, les critères et les liens vers les artefacts
    conservés dans un stockage privé autorisé.

### Procès-verbal de restauration à remplir

| Vérification | Résultat initial | Critère de succès |
|---|---|---|
| Cible isolée autorisée et réseau coupé | NON EXÉCUTÉ | Aucun accès production/fournisseur |
| Archive lisible et déchiffrable | NON EXÉCUTÉ | Vérification cryptographique réussie |
| Restauration complète de la configuration | NON EXÉCUTÉ | Registries/config présents |
| Base Recorder restaurée | NON EXÉCUTÉ | DB ouverte et séries contrôlées |
| Entity Registry comparé | NON EXÉCUTÉ | Identités et références conservées |
| Device Registry comparé | NON EXÉCUTÉ | Appareils et associations conservés |
| Statistiques/échelles comparées | NON EXÉCUTÉ | Pas de perte ni réinterprétation |
| Trois catégories Énergie comparées | NON EXÉCUTÉ | Pas de perte/double comptage |
| Compteurs déposés conservés | NON EXÉCUTÉ | Une identité par génération physique |
| Redémarrage/rechargement validés | NON EXÉCUTÉ | Persistance stable |
| Retour arrière éprouvé | NON EXÉCUTÉ | État initial récupéré |
| Validation métier distincte | NON EXÉCUTÉ | PV approuvé explicitement |

**Règle de décision :** un seul contrôle obligatoire non exécuté,
inconnu ou échoué empêche toute déclaration de restauration éprouvée et
toute activation de migration en production.

## English — Restore and acceptance protocol

**Record status: NOT RUN / NOT ACCEPTED.** Native backup metadata,
availability and positive archive size do not establish recovery.

Before any action, obtain separate explicit approval of the isolated
host, network, storage, recipients, encrypted backup data, copy method,
restoration steps, external-connection risks, cleanup and rollback.
GitHub development approval does not permit instance creation,
backup transfer, production changes or restore.

Read-only preparation verifies: exact backup ID, timestamp, Home
Assistant configuration and Recorder database inclusion, destination
status and archive availability; separately account for external
Recorder databases and encryption keys. Keep credentials and the
emergency recovery kit out of GitHub.

On the **approved offline isolated target**, verify archive integrity
and decryption, restore the configuration and database, compare entity
and device registries, Recorder metadata and sample statistics, all
three Energy preference categories, active/retired meter identities,
and restart/reload persistence. Only then run a separately approved
migration rehearsal, interruption/resume and rollback. Retain
private before/after evidence and a signed business acceptance record.

Every checklist item above starts at **NOT RUN**. A missing or failed
mandatory check blocks the proof of recovery and any production
migration. No release, real migration or production write is
authorized by this document.
