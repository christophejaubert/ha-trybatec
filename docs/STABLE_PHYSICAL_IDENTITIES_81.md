# 🤖 Identités physiques stables / Stable physical-meter IDs (#81)

## Français

### Exécuteur ponctuel développé (non déployé)

- `migration_executor_81.py` implémente un exécuteur journalisé, à appel **exclusivement explicite** : il régénère le plan, compare l'empreinte avec celle approuvée, consulte une sauvegarde **réellement répertoriée par Home Assistant** contenant sa configuration et Recorder, vérifie les propriétaires et bloque les identifiants déjà occupés.
- L'exécution ajoute l'alias canonique **à l'appareil existant** via `new_identifiers` et modifie **uniquement** le `unique_id` de l'entité existante. Elle conserve `device_id`, `entity_id`, statistiques et préférences Énergie ; elle ne supprime aucune entité.
- `migration_activation_81.py` pré-enregistre les unités sources vérifiées, active le mode stable pour **l'ensemble des compteurs** d'un même compte, puis contrôle le rechargement de l'intégration. Une migration partielle de compte est refusée.
- Un journal persistant permet de refuser les exécutions concurrentes et de reprendre un **retour arrière explicite** après interruption : désactivation du mode stable, restauration des identifiants, retrait des seuls alias ajoutés, rechargement et vérification.
- Une étape de clôture séparée exige les preuves de contrôle du runtime, des références, des unités, de Recorder et d'Énergie. Une CI verte seule ne suffit pas. Les historiques ne sont jamais réécrits et les anciennes générations ne sont pas supprimées.

**Limites de déploiement :** l'exécuteur n'est pas exposé comme action Home Assistant ni appelé à l'installation ; les adaptateurs d'inventaire/recette et de vérification de sauvegarde doivent être raccordés à des données fiables, puis testés sur un environnement HA représentatif avant toute écriture sur l'instance réelle. Les nouvelles fonctions et tests constituent du code développé, non une recette métier validée. L'outil ne saurait garantir une restauration complète en cas de défaillance de l'hôte ou de la base : cette situation nécessite la sauvegarde HA.


### Adaptateurs natifs Home Assistant (branche #81)

- `migration_ha_adapters_81.py` se raccorde au registre des entités/appareils, au journal `Store` propre au compte et au **gestionnaire Backup natif** de Home Assistant 2026.11. Une sauvegarde doit être enregistrée sous son identifiant exact, inclure **configuration et base Recorder**, disposer d'au moins une copie de taille positive sans erreur et dater de moins de **24 h**. La présence de métadonnées ne prouve pas à elle seule qu'une restauration fonctionnerait.
- `migration_ha_evidence_81.py` inventorie **en lecture seule** les entités de la plateforme, les associations aux appareils, les métadonnées des statistiques Recorder et les trois catégories de configuration Énergie. Il ne convertit jamais une absence de statistique en autorisation de destruction.
- **Blocage volontaire :** aucun de ces adaptateurs ne peut déclarer le recensement des consommateurs externes exhaustif. Les tableaux de bord, automatisations et autres intégrations doivent être contrôlés indépendamment, y compris les références directes aux identifiants techniques. Le plan natif conserve donc `ready: false` tant que cette preuve manque. Aucune commande d'écriture n'est exposée dans l'IHM ni appelée au démarrage.
- Les tests dédiés couvrent les sauvegardes trop anciennes, incomplètes ou absentes, les erreurs d'agents et le refus d'une recette automatique à partir du seul inventaire interne.

## Décision d'architecture : une migration unique (12/11/2026)

**Cible : un unique mécanisme normal d'identité, sans compatibilité b6 permanente.** Le maintien des anciens identifiants par les comptes créés avant cette évolution constitue uniquement un **sas de sécurité transitoire**. La reconnaissance des identités historiques doit être limitée à un outil de migration ponctuelle, indépendant du chemin normal des capteurs.

- Nouvelles installations : identifiant canonique stable et verrou de l'unité source.
- Installations existantes : inventaire puis migration unique, avec maintien des `entity_id` pour conserver les références et leurs `statistic_id` Recorder.
- Générations anciennes coexistantes : seule la génération active exactement vérifiée peut être candidate ; les autres restent archivées/inactives jusqu'à audit, sans suppression automatique.
- En cas d'unité inconnue, de statistiques incompatibles, de référence non vérifiée, de collision ou de migration interrompue : **bloquer**, ne pas improviser de valeur ni supprimer de donnée.
- Après migration et recette, éliminer la branche d'exécution historique et ses anciennes conditions ; conserver uniquement l'utilitaire de récupération ponctuelle si nécessaire, jamais une logique de compatibilité ordinaire.

**Avancement effectif :** `migration_once_81.py` fournit l'inventaire déterministe en lecture seule, les conditions de blocage et une empreinte d'état ; les tests associés utilisent uniquement des données synthétiques. La transaction de registre et son rollback sont **codés avec des tests synthétiques**, mais leur raccordement aux inventaires complets et la recette réelle restent **à réaliser**. Le résultat « prêt pour confirmation » n'autorise aucune écriture et n'atteste pas à lui seul la complétude des dépendances.


**Statut : exécuteur ponctuel et adaptateurs développés sur la PR #82, non fusionnée.** La CI doit être vérifiée sur le dernier SHA ; les tests automatisés ne valent pas recette sur un Home Assistant réel. L'exécution sur les installations existantes demeure **non raccordée et bloquée** jusqu'à inventaire indépendant des consommateurs, preuve de sauvegarde restaurable et recette sur instance représentative. Aucune écriture sur Recorder, Énergie ou le registre des entités n'est déclenchée au démarrage.

### Architecture et compatibilité

- `meter_identity.py` calcule un `unique_id` opaque stable à partir du compte, du lot/logement, du fluide et du numéro de série physique, sans inclure ni unité de mesure ni version logicielle.
- **Nouveaux comptes uniquement** : le flux d'installation crée `stable_meter_identities: true`. Le capteur utilise cet identifiant stable. Un registre de contrôle local conserve la première unité de source vérifiée avant toute publication d'index cumulatif ; l'état « unité inconnue » est également mémorisé.
- Si l'unité source change après validation (par exemple de L vers m³), le capteur **conserve le même identifiant**, mais son index et ses statistiques deviennent indisponibles jusqu'à revue. Il ne reconvertit ni n'écrase silencieusement les statistiques historiques.
- **Comptes existants** : en l'absence de l'option, ils conservent **strictement le comportement b6 préexistant**, y compris les éventuelles générations liées aux corrections d'unité. Le module pur sait proposer la résolution des anciennes générations, mais cette résolution n'est **pas appliquée aux capteurs actifs** tant que la migration explicite n'est pas disponible.
- Les appareils physiques déposés et les séries Recorder versionnées restent distincts ; aucune consolidation ni suppression n'est tentée dans ce correctif.
- Le panneau administrateur expose uniquement une **prévisualisation en lecture seule** du passage aux identifiants canoniques. Les références Recorder/automatisations/tableaux de bord ne sont **pas** considérées comme exhaustivement vérifiées. L'absence de référence dans Énergie ne prouve pas qu'une entité est inutilisée.

### À terminer avant fusion/publication

1. **Migration des comptes existants :** audit complet de l'identité et des références ; sauvegarde récupérable ; aperçu signé par empreinte ; confirmation de chaque migration ; détection des collisions et des générations coexistantes ; reprise après interruption et rollback.
2. **Recorder et Énergie :** vérifier les anciennes unités, le modèle statistique et les séries utilisées ; n'autoriser une bascule que lorsque la conservation des données et l'absence de double comptage sont démontrées. Ne jamais fusionner des index physiques différents.
3. **Essais en intégration :** installations neuves et existantes, unités inconnues/vérifiées/corrigées, multi-logements et collisions, comptes multiples, compteurs déposés, perte de registre, restauration, redémarrage et migration partielle.
4. **Validation :** CI obligatoire sur SHA exact, tests d'intégration Home Assistant, sauvegarde et recette métier réelle distincte ; aucune release si les contrôles sont incomplets.
5. **Coordination :** #36 (séries Recorder et bascules Énergie), #37 (compteurs déposés et nettoyage), #45 (parcours du panneau), #83 (IHM guidée), #35 (réauthentification). Ne pas recopier ou modifier leurs contrats fonctionnels dans cette PR.

**Attention :** une publication peut être suivie d'une mise à jour automatique de Home Assistant selon la configuration de l'utilisateur. Aucun changement de mode d'identité ne doit être publié sans revue d'impact.

## English

### One-time executor implemented (not deployed)

- `migration_executor_81.py` provides an **explicit-only**, journaled transaction: refresh and compare the approved preflight fingerprint, independently look up a **real HA configuration + Recorder backup**, verify ownership and refuse occupied targets.
- It adds the canonical identifier to the **same physical device** using `new_identifiers` and updates only the original entity's `unique_id`, preserving `device_id`, `entity_id`, Recorder and Energy preferences. No legacy rows are deleted.
- `migration_activation_81.py` durably seeds source-unit baselines, changes the account to canonical mode only when **all its physical meters** are included, then checks the integration reload; partial-account activation is rejected.
- A durable journal blocks concurrent attempts and supports **explicit interrupted-operation recovery**: disable canonical mode, restore old IDs, remove only aliases introduced by this migration, reload and verify.
- Separate completion requires actual runtime, reference, unit, Recorder and Energy verification. CI success alone does not prove business acceptance. Historical series are never rewritten or silently removed.

**Deployment restrictions:** the executor is not exposed as a HA action and is never invoked at setup. Trustworthy inventory, backup verification and post-migration acceptance adapters must be wired and tested on a representative HA runtime before any real-instance write. This is implemented code and synthetic testing, **not** completed real-world business acceptance. Catastrophic host/database failure still requires a complete HA backup restoration.


### Native Home Assistant adapters (issue #81)

- `migration_ha_adapters_81.py` binds the actual HA entity/device registries, entry-scoped persistent `Store` journal and **native BackupManager** (2026.11). An exact backup ID must have a configuration and Recorder database copy, a positive-sized destination without recorded failure, and a timestamp within **24 hours**. Metadata cannot prove actual archive restorability.
- `migration_ha_evidence_81.py` inspects all Trybatec platform registry records, physical device owners, Recorder statistic metadata and the three Energy configuration categories **read-only**. Missing statistics are not interpreted as authorization to delete old history.
- **Deliberate safety gate:** the native collector never claims all external consumers have been inspected. Dashboards, automations and custom integrations—including possible references to technical unique IDs—need independent coverage. It therefore returns `ready: false` until that verification exists. No write API is exposed in the panel or run during setup.
- Dedicated tests reject stale, incomplete and unavailable backups and disallow promoting native-only evidence to full business acceptance.

## Architecture decision: one-time migration (2026-11-12)

**Target: a single normal stable-identity mechanism, not permanent b6 compatibility.** Keeping legacy IDs on already-installed accounts is merely a **temporary safety gate**. Recognition of obsolete IDs belongs in the separate, one-time migration tool, never the regular sensor lifecycle.

- New installations: canonical stable unique IDs and persistent source-unit guard.
- Existing installations: inventory first, then a one-off migration preserving the **same entity IDs**, associated references and Recorder statistic IDs.
- Coexisting old generations: only an exactly verified active generation is a candidate; retain the others without automatic cleanup until dependencies are audited.
- Unknown units, incompatible Recorder statistics, incomplete references, identity collisions or interrupted migrations: **fail closed**; do not invent measurements or delete data.
- Once migration and acceptance finish, remove the old runtime branch. Any later recovery utility must remain explicitly invoked, not a permanent compatibility pathway.

**Actual delivery:** `migration_once_81.py` contains a deterministic read-only inventory, blockers and a fingerprint, covered by synthetic tests. Registry application, verified-backup gating and rollback are **coded with synthetic tests**, but trusted live inventory wiring and real acceptance are **not yet completed**. A "ready for separate confirmation" preview neither authorizes writes nor proves an exhaustive dependency audit.


**Status: one-time executor and native adapters implemented in draft PR #82, not merged.** CI success must be re-checked against the exact latest commit; automated tests do not constitute real-instance acceptance. Live existing-account execution remains **unwired and blocked** until independent external-consumer inventory, demonstrably recoverable backup and representative HA acceptance. Startup performs no entity-registry, Recorder or Energy writes.

### Architecture and compatibility

- `meter_identity.py` derives an opaque, deterministic `unique_id` from account scope, dwelling/lot, fluid and physical serial; never from source units or release numbers.
- **New accounts only:** the config flow enables `stable_meter_identities: true`. An internal, durable local scale guard stores the first verified source unit before permitting cumulative statistics, including a stored initial "unverified" marker.
- After a correction (for example L to m³), the sensor **keeps its identity**, but its value and long-term statistic eligibility are withheld until separately reviewed. Existing cumulative statistics are never silently reinterpreted.
- **Existing accounts:** without the flag, the **original b6 runtime behavior is unchanged**, including possible unit-specific generations. The pure helper can inspect known b6 generations, but its resolution is **not applied to active sensors** until an explicit migration flow is implemented.
- Retired physical devices and versioned Recorder statistics stay separate. This change performs no historical merging or cleanup.
- The administrator snapshot shows a **read-only** preview of future canonical IDs. Recorder, automation and dashboard references are explicitly **not** comprehensively audited; a missing Energy reference is not proof of an unused entity.

### Remaining release gates

1. **Existing-account migration:** full ownership/dependency audit, recoverable backup, fingerprinted preview, separate confirmation, collision/coexistence checks, interrupted-resume and rollback.
2. **Recorder and Energy:** verify old scale and statistical metadata; prove zero data loss or duplicate counting before switching sources; never sum raw indexes of different physical meters.
3. **Integration tests:** greenfield/legacy, unknown/verified/changed units, multi-account/lot, serial collisions, retired meters, lost baseline, restart, restore, partial migrations.
4. **Validation:** mandatory CI on exact SHA, HA integration coverage and separate real-instance acceptance; do not release with missing checks.
5. **Coordination:** #36 (Recorder/Energy), #37 (retired meters/cleanup), #45 (panel flow), #83 (guided UI), #35 (reauthentication).

**Release caution:** a published version may trigger a user's Home Assistant automatic updater. Never enable migration as a release side effect.

## Audit externe et recette isolée / External audit and isolated acceptance

**FR :** La matrice indépendante des consommateurs est définie dans
[MIGRATION_DEPENDENCY_AUDIT_81.md](MIGRATION_DEPENDENCY_AUDIT_81.md).
Le scanner `migration_consumer_audit_81.py` ne produit que des références
opaques de diagnostic, ne conclut jamais à une exhaustivité et ne peut
jamais débloquer la migration. Les résultats privés de l'installation
ne doivent pas être publiés sur GitHub.

La procédure de sauvegarde, restauration, comparaison des états,
redémarrage et procès-verbal de recette isolée figure dans
[MIGRATION_RESTORE_ACCEPTANCE_81.md](MIGRATION_RESTORE_ACCEPTANCE_81.md).
**Aucune restauration ni migration réelle n'a été effectuée** ; le PV
reste non exécuté. Toute action sur une instance ou un fichier privé
requiert une autorisation spécifique.

**EN:** The independent consumer matrix is specified in
[MIGRATION_DEPENDENCY_AUDIT_81.md](MIGRATION_DEPENDENCY_AUDIT_81.md).
The diagnostic scanner emits only opaque references and can never
claim exhaustive coverage or unlock migration. Never publish real
installation evidence to GitHub.

The isolated backup/restore, before-and-after comparison, restart and
business acceptance protocol is specified in
[MIGRATION_RESTORE_ACCEPTANCE_81.md](MIGRATION_RESTORE_ACCEPTANCE_81.md).
**No real restore or migration was performed**; the record remains
not executed. Separate explicit authorization is required before any
instance or private-data operation.

## Références / References

- [#81 — architecture/architecture](https://github.com/christophejaubert/ha-trybatec/issues/81)
- [#37 — entités/physical devices](https://github.com/christophejaubert/ha-trybatec/issues/37)
- [#36 — Recorder/Énergie](https://github.com/christophejaubert/ha-trybatec/issues/36)
- [#83 — IHM/UI](https://github.com/christophejaubert/ha-trybatec/issues/83)
