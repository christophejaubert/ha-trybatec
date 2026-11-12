# 🤖 Identités neuves / New IDs — Candidate #81

## Français — Portée de la livraison intermédiaire

**Statut : candidate en brouillon, aucun déploiement, migration, fusion ou publication autorisés.**

Cette branche, indépendante et fondée sur `main`, extrait uniquement les fonctions **non migrantes** déjà développées dans la PR #82. Elle ne transporte pas les 102 commits de la branche historique et **ne clôture pas** l'issue #81.

### Inclus

- Identité physique canonique déterministe pour les **nouvelles entrées de configuration** uniquement : compte, lot, fluide, série ; ni version d'intégration ni unité dans l'identifiant.
- Première unité vérifiée protégée par un garde durable (`StableUnitGuard`) ; changement d'échelle non vérifié : mesure et statistiques cumulatives bloquées.
- Les entrées **historiques** ne reçoivent pas automatiquement `stable_meter_identities`. Les `entity_id`, `unique_id`, `device_id` et associations existantes restent en mode historique ; seul un parcours explicite de migration, **absent de cette candidate**, pourrait changer ce mode.
- Prévisualisation d'identités physiques **en lecture seule** dans le panneau administrateur. `dependency_inventory_complete=False` et `safe_to_apply=False` quels que soient les résultats ; aucune supposition d'exhaustivité des consommateurs.
- Tests synthétiques pour les registres, le rechargement du compte historique, panne fournisseur, correction d'unité, nouveau flux de création et refus de migration.

### Exclus et non autorisés

Le paquet ne contient **aucun** des modules :
`migration_once_81.py`, `migration_executor_81.py`,
`migration_activation_81.py`, `migration_ha_adapters_81.py`,
`migration_ha_evidence_81.py`, `migration_consumer_audit_81.py`.

Ne sont pas inclus : restauration, exécution de migration, nettoyage des générations déposées, import historique Recorder, reconfiguration Énergie, consolidation #36, cycle de vie #37 ou ajout groupé #88.

Cette extraction ne modifie pas le `manifest.json`, les numéros de version, les services d'import, le JavaScript du panneau ni la chaîne de livraison. Les services historiques présents sur `main` restent accessibles via leurs actions explicites, sans déclenchement à l'installation.

**Important :** un chargement normal peut enregistrer les entités d'un *nouveau* compte, publier ses états et écrire les états/statistiques ordinaires dans Home Assistant. L'interdiction porte sur les réécritures **historiques explicites**, les changements Énergie et les migrations automatiques ; ce paquet ne signifie pas « aucune écriture HA ».

### Contrats de compatibilité et d'arrêt

| ID | Garantie / contrôle |
|---|---|
| G01 | Ancien compte : identifiants et appareil inchangés après rechargement |
| G02 | Panne fournisseur : aucun nouvel identifiant, aucune activation stable |
| G03 | Flux de création *nouveau* uniquement : mode stable et contrôle des doublons |
| G04 | Nouveau capteur : unité inconnue puis validée = une seule entité |
| G05 | Correction d'échelle : blocage, aucune seconde série sous le même statistic_id |
| G06 | Collision et propriétaire étranger : diagnostic bloqué, aucune écriture |
| G07 | Panneau : `safe_to_apply=False`, inventaire externe non exhaustif |
| G08 | Aucun exécuteur migratoire dans le paquet ni appel au chargement |
| G09 | Tests intégration HA et CI sur **SHA exact de la candidate** |
| G10 | Repli asymétrique explicitement documenté et contrôlé |

### Risque de repli asymétrique

Une entrée créée **après cette candidate** en mode stable n'est pas garantie compatible avec le code ancien `0.3.3b1`. Un retour aveugle à cette version pourrait recréer des identifiants historiques et des entités supplémentaires.

**Ne pas créer de nouveau compte en production pendant la qualification sans plan distinct de récupération.** Le retour au code précédent peut être étudié pour une entrée ancienne restée non migrée ; il n'est pas une stratégie universelle pour les nouvelles entrées.

Les autres risques résiduels sont les références dans les applications tierces non exhaustivement inspectables, les changements de versions Home Assistant, les états normaux Recorder et l'absence de restauration réelle éprouvée. L'issue #81 reste ouverte et la PR #82 reste en brouillon.

### Coordination et intégration #45

- Base de la PR candidate : `main` courant. PR #82 reste séparée.
- Aucun changement dans les modules des issues #36, #37, #42 ou #88 ; surveiller les nouveaux `main`/PR jusqu'à la décision de fusion.
- Conserver le manifeste et la version existante. La MOE de #45 décide du numéro et de la portée de la prochaine préversion, puis réalise sa recette avant publication.
- Contrôler les 15 jobs obligatoires et l'absence de collision fichier avec les chantiers actifs.
- Avant toute publication, tenir compte de l'automatisation de mise à jour et redémarrage Home Assistant ; aucune modification de cette automatisation n'est autorisée ici.
- Si la candidate était fusionnée, **rebaser/réconcilier la PR #82** pour ne pas réintroduire de changements identiques. La fusion n'est pas autorisée au stade de cette candidate.

## English — Staged non-migrating scope

**Status: draft candidate only. No live deployment, migration, merge or release is authorized.**

This fresh `main`-based branch extracts non-migrating features from PR #82 without replaying its 102 commits or closing issue #81.

**Included:** deterministic physical-meter IDs for **newly created** accounts; durable verified source-unit guard that blocks unapproved scale changes; unchanged legacy identities for existing accounts; a read-only admin-panel preview that always returns `dependency_inventory_complete=False` and `safe_to_apply=False`; synthetic HA regression tests for new setup, legacy reload/outage, unit transitions and non-executable previews.

**Excluded:** historical migration executor, journal/rollback and backup adapters, independent external-consumer collector, Recorder backfills, Energy configuration changes, cleanup, historical consolidation and bulk enrollment. The original main import services remain explicitly opt-in. No version bump or release is included.

**Normal runtime effects remain possible:** new-entity registration and normal sensor/Recorder state recordings. The contract excludes *historical backfills*, Energy preference changes and identity migration on setup, update or restart.

**Downgrade risk:** a new stable-account entity may not be safely opened by old `0.3.3b1` code, which could create duplicate legacy IDs. Do not create new live accounts during qualification without a separately reviewed recovery plan. An existing unmigrated account has a different, narrower code-revert path. Real backup restore and external-consumer completeness are not proven.

**Acceptance gates:** G01–G10 above, all mandatory CI on exact final SHA, independent #45 release coordination and separate approval before any merge, publication, installation or Home Assistant change. Keep issue #81 open and PR #82 in draft.
