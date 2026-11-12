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


---

## FR — Matrice complémentaire de qualification et de réinstallation

Cette matrice distingue la preuve **synthétique** d'une recette réelle.
Tous les noms de comptes, lots, numéros de compteurs et lectures des tests
sont fictifs. Les tests ne restaurent et ne modifient aucune installation.

| Scénario | Référence avant | Attendu après | Test / niveau de preuve |
|---|---|---|---|
| Compte historique avant/après mise à jour | Identités `b6` et associations HA existantes | Mêmes `entity_id`, `unique_id`, `device_id` après rechargement | `test_legacy_account_reload_preserves_physical_registry_without_migration` — HA synthétique |
| Panne du fournisseur | Derniers registres historiques connus | Pas d'activation canonique ni nouveau registre physique | `test_legacy_account_reload_on_vendor_outage_never_claims_stable_identity` — HA synthétique |
| Compteur remplacé | Prédécesseur déposé + successeur en service | Deux identités et appareils distincts, inchangés au rechargement | `test_legacy_successive_physical_meters_preserve_identities_on_reload` — HA synthétique |
| Nouveau compte éligible | Aucune entrée existante pour la portée considérée | ID stable, sans unité ni version dans la clé physique | `test_new_config_flow_enables_stable_ids_only_for_new_entry`, `test_stable_meter_unit_verification_and_correction_do_not_duplicate_entity` |
| Unité inconnue puis confirmée | Capteur stable sans somme autorisée | Même ID ; `total_increasing` uniquement après vérification | Test d'unité stable et garde persistant — HA synthétique |
| Changement d'échelle | Unité source durable existante | Valeur cumulative suspendue, pas de nouvelle entité | Test de correction et rechargement — HA synthétique |
| Compte réinstallé avec ancien `b6` ou archive `b15` | Ancienne entité dans le registre, nouvelle entrée avec drapeau stable | Refus `legacy_identity_requires_review`, aucune entité canonique concurrente | `test_reinstalled_account_with_legacy_b6_entity_blocks_stable_duplication` (2 variantes) — HA synthétique |
| Série réutilisée sur deux lots | Ancien ID b6 sans lot attribuable | Refus des deux identités nouvelles, sans deviner le propriétaire | `test_reused_serial_with_unscoped_b6_id_blocks_both_new_stable_meters` — HA synthétique |
| Réinstallation sans registre d'unité durable | Entité stable existante, référence d'unité perdue | Refus `missing_unit_baseline_requires_review`, même ID en registre | `test_missing_stable_unit_ledger_blocks_reinstall_without_duplicate` — HA synthétique |
| Collisions et propriété étrangère | Identifiants multiples ou propriétaire non prouvé | Diagnostic bloqué, aucune migration | `test_meter_identity_81.py` et `test_staged_greenfield_guards_81.py` |
| Rétrogradation vers ancien code | Capteur `meter_…_index` déjà enregistré | Risque prouvé : ancien code attend un identifiant `b6` différent | `test_old_version_downgrade_would_change_new_meter_identity` — preuve d'incompatibilité des clés, **pas** un test d'installation |
| Démarrage, reload, absence de migration | Aucune décision d'activation historique | Pas d'exécuteur #82 dans le paquet ni d'activation implicite | G01–G09, tests statiques et HA synthétiques |
| Recorder/Énergie historiques | Métadonnées et préférences existantes | Aucun import historique ni changement de préférences initié par #120 | Inspection du diff, tests de garde, Recorder E2E CI ; **pas** de recette réelle |

**Limite importante :** le nouveau contrôle du registre repère les identifiants
anciens `b6` et archives `b15` connus, et refuse les b6 non localisés
lorsqu'un numéro de série est réutilisé. Si une entrée ou son
registre ont été entièrement supprimés tandis que des statistiques Recorder
subsistent, **l'absence d'entité n'établit pas l'absence de données
historiques**. Une réinstallation dans ce contexte exige un audit préalable
des statistiques et références : la présente candidate ne prétend pas
résoudre toute réinstallation historique.

### Risque de rétrogradation — récupération contrôlée, non automatique

Le mode historique fabrique un `unique_id` `b6` à partir du compte, du
numéro physique et de l'unité source. Le mode stable fabrique un
`meter_<empreinte>_index` indépendant de l'unité. Ces valeurs sont
**différentes pour un même compteur** ; rétrograder aveuglément après
création d'un compte stable pourrait produire des doublons d'entité et
d'appareil, et une rupture/duplication de `statistic_id`.

**Avant installation :**

1. Capturer dans un dossier privé la version/SHA, l'entrée, les
   `entity_id`, `unique_id`, `device_id`, `statistic_id`, unités,
   consommateurs et sauvegardes ; ne jamais publier ces données.
2. Distinguer les **comptes historiques jamais migrés** des **nouveaux
   comptes déjà créés avec des identifiants stables**.
3. Pour un ancien compte : préparer un retour à la version précédente
   avec comparaison exacte des identités et arrêt si divergence.
4. Pour un nouveau compte stable : **ne pas rétrograder vers `0.3.3b1`
   automatiquement**. Privilégier une correction en avant sur une version
   compatible conservant les identités. Toute alternative de retrait/
   réinstallation d'entrée, traitement de séries ou restauration exige une
   analyse d'impact, un état initial vérifié et une autorisation distincte.
5. Une restauration complète pourrait remplacer les données sélectionnées
   par leur état à la date de l'archive et **perdre les modifications
   postérieures** ; sa restaurabilité n'a pas été éprouvée.
6. En cas d'erreur, conserver registres et statistiques intacts, relever
   les preuves privées et suspendre tout nouveau changement. Ne jamais
   nettoyer automatiquement les générations historiques.

**Critère de fusion recommandé :** les tests CI sur le SHA final doivent
réussir, les autres PR concurrentes doivent être réconciliées, et la MOE
doit accepter explicitement le risque résiduel de réinstallation avec
statistiques orphelines et de rétrogradation des *nouveaux* comptes.
La préparation de cette PR ne constitue pas une autorisation de
fusion, de release, d'installation ni de migration.

## EN — Additional acceptance and downgrade matrix

All tests use synthetic accounts, meters and readings. The following
checks establish automated behavior, **not live Home Assistant
business acceptance**.

| Case | Before | Expected after | Evidence |
|---|---|---|---|
| Legacy update/reload | Existing b6 entity and device references | Unchanged entity, unique and device IDs | `test_legacy_account_reload_preserves_physical_registry_without_migration` |
| Supplier outage | Legacy identities registered | No implicit activation or reassignment | `test_legacy_account_reload_on_vendor_outage_never_claims_stable_identity` |
| Retired predecessor and active successor | Two physical generations | Both retained across reload | `test_legacy_successive_physical_meters_preserve_identities_on_reload` |
| New account | Fresh eligible account | Canonical stable ID with verified-unit guard | New config-flow and stable-unit tests |
| Unknown and changed units | Missing or approved source scale | Block unsafe cumulative statistics; preserve entity | Stable-unit transition tests |
| Reinstall with old b6 or archived b15 entity | Prior registry reference survives | Block new stable entity as `legacy_identity_requires_review` | `test_reinstalled_account_with_legacy_b6_entity_blocks_stable_duplication` (both variants) |
| Reused serial with unscoped b6 | Ambiguous former ID across two lots | Reject both canonical identities without guessing ownership | `test_reused_serial_with_unscoped_b6_id_blocks_both_new_stable_meters` |
| Reinstall without durable unit ledger | Stable entity registered; unit evidence lost | Block cumulative scale as `missing_unit_baseline_requires_review` | `test_missing_stable_unit_ledger_blocks_reinstall_without_duplicate` |
| Collisions and foreign ownership | Ambiguous or foreign identifiers | Fail-closed preview | Identity and staging-guard unit tests |
| Downgrade to old version | New `meter_…_index` ID | Legacy b6 computation differs; downgrade unsafe | `test_old_version_downgrade_would_change_new_meter_identity` (ID-only proof) |
| Startup and history side effects | Unmigrated historical account | No automatic migration, historical backfill or Energy change | Static and HA synthetic tests; real acceptance pending |

**Known blind spot:** orphan Recorder metadata may persist even when an
entity-registry entry is gone. The b6/b15 collision check catches known
registry entries and ambiguous reused serials, but **cannot certify absence of orphaned statistics**.
Do not treat reinstallation as a new eligible account without an
independent history/dependency audit.

**Safe recovery posture:** inventory all IDs and statistics privately
before deployment. Revert code on an **unmigrated legacy account** only
after checking that the baseline remains unchanged. For **new stable
accounts**, do **not** automatically downgrade to `0.3.3b1`: prefer a
compatible forward fix. Removal/recreation, historic statistic changes
or full restore need separate explicit approval. A restore may discard
all selected changes made after the backup, and real recovery remains
untested. Never auto-clean historical meters.

Final merge and release require their own approval; a green automated
CI result is not a substitute for real migration or rollback testing.
