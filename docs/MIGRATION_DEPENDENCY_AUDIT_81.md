# 🤖 Dépendances #81 / Dependency audit #81

## Français — Procédure indépendante, sans données d'installation

Cette procédure complète l'inventaire natif de la PR #82. Elle est **en lecture
seule** et ne permet **jamais** de supprimer un ancien compteur ni d'autoriser
une migration à partir d'une simple case cochée. Ne pas publier de listes
réelles d'entités, identifiants de compte, sauvegardes, secrets, adresses,
configurations ni fichiers de l'installation dans le dépôt.

### Correspondances à figer avant toute décision

Pour **chaque** compteur physique (actif et déposé), conserver dans un
dossier de recette privé, sur une copie isolée :

- La portée compte / configuration et la clé physique lot + fluide + série.
- L'ancien et le nouvel `unique_id` exacts, la preuve de propriété et
  la disponibilité de l'identité cible.
- L'`entity_id` et le `device_id` à préserver.
- Les `statistic_id` Recorder, unités, classes, somme et périodes enregistrées.
- Les références aux anciennes générations coexistantes (`_2`, etc.)
  **sans les fusionner ni les nettoyer**.
- L'empreinte du plan, les versions Core/intégration et l'instant UTC.

L'exécuteur ne modifie en principe que le `unique_id`, ajoute l'alias
canonique au **même** appareil et conserve les autres identifiants.
Une référence externe à l'ancien `unique_id` peut néanmoins casser :
**la conservation de `entity_id` ne prouve pas la conservation de
l'ensemble des consommateurs**.

### Matrice de contrôles obligatoires

| Surface | Méthode indépendante | Contrôler | Limite / preuve exigée |
|---|---|---|---|
| Entity Registry | Inventaire complet du registre, plateforme et propriétaire | `entity_id`, `unique_id`, `device_id`, alias et collisions | Capturer anciens et nouveaux propriétaires ; ne pas se limiter aux entités visibles |
| Device Registry | Inventaire propriétaire par configuration, identifiants et appareils enfants | `device_id`, identifiants canoniques et historiques | Comparaison après rechargement, sans fusion physique |
| Recorder | Métadonnées natives + statistiques pertinentes | `statistic_id`, unités, `has_sum`, séries existantes | Absence dans une plage temporelle ≠ absence historique ; aucune réécriture |
| Énergie | Trois catégories complètes : sources, consommations appareil et eau | `statistic_id`, références de capteurs | Aucun résultat observé ≠ absence externe ; comparaison et absence de doubles |
| Automatisations | Parcourir les définitions stockées et référencées | `entity_id`, `device_id`, texte et templates | Inclure les blueprints/dépendances dynamiques |
| Scripts et scènes | Parcourir toutes les définitions, y compris paramètres et attributs | Les quatre classes d'identifiants | Inclure scripts qui résolvent les entités dynamiquement |
| Tableaux de bord | Parcourir Lovelace storage et YAML ; badges, entêtes, cartes et templates | Les quatre classes et références textuelles | Vues stratégie et cartes externes : contrôle distinct ou inconnu |
| Groupes | Anciens groupes et entrées de configuration, y compris `options.entities` | `entity_id` et groupes intermédiaires | Une API qui masque les options ne démontre pas l'absence de références |
| Autres intégrations | Inspecter les données/options et flows documentés, sans secrets | `entity_id`, `unique_id`, `device_id` | Champs masqués, options non exposées ou références internes : indéterminé |
| Applications tierces | Inventorier les applications autorisées (Node-RED, AppDaemon, scripts, clients API, etc.) | Les quatre identifiants | Sans accès aux configurations et usages, indéterminé |
| API et clients externes | Consulter les usages observables et config. des consommateurs autorisés | Références directes ou calculées | Absence de trafic durant l'observation ≠ absence d'usage futur |

Pour chaque surface et chaque identifiant, consigner dans le **dossier privé**
la méthode, la date, la source, l'étendue réellement parcourue, les
correspondances, l'action décidée (préserver, adapter, bloquer), les limites
et la preuve de contre-vérification.

### Outil de diagnostic borné

`migration_consumer_audit_81.scan_consumer_snapshots` cherche des
références exactes ou incorporées dans des instantanés structurés fournis
en lecture seule, avec des chemins opaques et sans exposer la valeur des
identifiants en sortie. Un préfixe d'identifiant ne suffit pas pour
déclarer une correspondance. Les résultats sont indicatifs ; l'outil
**ne certifie jamais une couverture exhaustive** et renvoie toujours
`dependency_inventory_complete: false` et `safe_to_apply: false`.

Les instantanés manquants, tronqués, partiellement masqués, générés ou
externes restent **inconnus**, même si aucune correspondance n'est
observée. Une chaîne arbitraire comme `"complete": true` n'a aucune
autorité. Le verrou natif `dependency_inventory_complete=False` est
maintenu.

### Conditions de levée ultérieure

Un futur fournisseur d'attestations, **non disponible dans cette PR**,
devra être issu d'un contrôle indépendant vérifiable et lié à
l'empreinte exacte du plan et de la configuration, puis recalculé
avant exécution. Tant qu'une surface pertinente reste inconnue ou que
des consommateurs ne peuvent pas être préservés : **refus de migration**.

## English — Independent dependency audit, no installation data

This is a **read-only**, non-authorizing procedure. Never commit live
identifiers, vendor accounts, locations, credentials, backup IDs,
recordings, Home Assistant configurations or screenshots.

For every active/retired physical meter, record privately the account
scope and lot/fluid/serial, old/new `unique_id`, preserved `entity_id`
and `device_id`, all Recorder `statistic_id` values, owner/collision
evidence, selected Energy sources, coexisting historical generations and
the exact fingerprint/version/time.

Independently inspect: entity and device registries, complete Recorder
metadata and relevant series, all three Energy categories, automations,
scripts, scenes, Lovelace storage and YAML views (including badges,
headers, custom cards and templates), group config entries/options,
other integration data/options, third-party applications and observable
external API clients. For each category retain privately its source,
method, inspected coverage, matching identifiers, required preservation
or change, unresolved limitations and a post-migration verification.

**No observed match is not proof of no consumer.** Unavailable,
redacted, dynamically computed and uninspected sources remain unknown.
A native `entity_id` preserved by the migration does not guarantee
that third parties using the old `unique_id` will still work.

The bounded pure scanner in
`migration_consumer_audit_81.scan_consumer_snapshots` produces only
opaque diagnostic locations. It cannot certify coverage or authorize
execution; it always returns `dependency_inventory_complete: false`
and `safe_to_apply: false`, including when untrusted input claims to
be complete. The native collector retains its mandatory hard block.

Only a future, independent and verifiable evidence supplier, bound to
the fresh exact migration fingerprint, could qualify for an execution
review. This PR provides **no such authorization**.
