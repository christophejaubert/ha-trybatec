# 🤖 Identités physiques stables / Stable physical-meter IDs (#81)

## Français

## Décision d'architecture : une migration unique (12/11/2026)

**Cible : un unique mécanisme normal d'identité, sans compatibilité b6 permanente.** Le maintien des anciens identifiants par les comptes créés avant cette évolution constitue uniquement un **sas de sécurité transitoire**. La reconnaissance des identités historiques doit être limitée à un outil de migration ponctuelle, indépendant du chemin normal des capteurs.

- Nouvelles installations : identifiant canonique stable et verrou de l'unité source.
- Installations existantes : inventaire puis migration unique, avec maintien des `entity_id` pour conserver les références et leurs `statistic_id` Recorder.
- Générations anciennes coexistantes : seule la génération active exactement vérifiée peut être candidate ; les autres restent archivées/inactives jusqu'à audit, sans suppression automatique.
- En cas d'unité inconnue, de statistiques incompatibles, de référence non vérifiée, de collision ou de migration interrompue : **bloquer**, ne pas improviser de valeur ni supprimer de donnée.
- Après migration et recette, éliminer la branche d'exécution historique et ses anciennes conditions ; conserver uniquement l'utilitaire de récupération ponctuelle si nécessaire, jamais une logique de compatibilité ordinaire.

**Avancement effectif :** `migration_once_81.py` fournit l'inventaire déterministe en lecture seule, les conditions de blocage et une empreinte d'état ; les tests associés utilisent uniquement des données synthétiques. L'application des modifications de registre, la sauvegarde/validation et le rollback restent **à implémenter et tester**. Le résultat « prêt pour confirmation » n'autorise aucune écriture et n'atteste pas à lui seul la complétude des dépendances.


**Statut : implémentation partielle sur PR #82, non fusionnée.** La CI doit être vérifiée sur le dernier SHA ; les tests automatisés ne valent pas recette sur un Home Assistant réel. Les migrations d'installations existantes ne sont pas encore implémentées, et aucune écriture sur Recorder, Énergie ou le registre des entités n'est déclenchée au démarrage.

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

## Architecture decision: one-time migration (2026-11-12)

**Target: a single normal stable-identity mechanism, not permanent b6 compatibility.** Keeping legacy IDs on already-installed accounts is merely a **temporary safety gate**. Recognition of obsolete IDs belongs in the separate, one-time migration tool, never the regular sensor lifecycle.

- New installations: canonical stable unique IDs and persistent source-unit guard.
- Existing installations: inventory first, then a one-off migration preserving the **same entity IDs**, associated references and Recorder statistic IDs.
- Coexisting old generations: only an exactly verified active generation is a candidate; retain the others without automatic cleanup until dependencies are audited.
- Unknown units, incompatible Recorder statistics, incomplete references, identity collisions or interrupted migrations: **fail closed**; do not invent measurements or delete data.
- Once migration and acceptance finish, remove the old runtime branch. Any later recovery utility must remain explicitly invoked, not a permanent compatibility pathway.

**Actual delivery:** `migration_once_81.py` contains a deterministic read-only inventory, blockers and a fingerprint, covered by synthetic tests. Registry application, backup/confirmation, verified rollback and real acceptance are **not yet implemented**. A "ready for separate confirmation" preview neither authorizes writes nor proves an exhaustive dependency audit.


**Status: partial implementation in draft PR #82; not merged.** CI success must be re-checked against the exact latest commit. Automated tests are not equivalent to acceptance testing on a real Home Assistant instance. Existing-installation migrations are **not** implemented; startup performs no entity-registry, Recorder or Energy writes.

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

## Références / References

- [#81 — architecture/architecture](https://github.com/christophejaubert/ha-trybatec/issues/81)
- [#37 — entités/physical devices](https://github.com/christophejaubert/ha-trybatec/issues/37)
- [#36 — Recorder/Énergie](https://github.com/christophejaubert/ha-trybatec/issues/36)
- [#83 — IHM/UI](https://github.com/christophejaubert/ha-trybatec/issues/83)
