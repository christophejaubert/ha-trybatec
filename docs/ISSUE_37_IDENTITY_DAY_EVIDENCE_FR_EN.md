# 🤖 #37 — Audit de filiation et des identités / Lineage and identity audit

**Périmètre / Scope:** contribution isolée sur les contrats et tests #37 ; aucune migration #81, aucune écriture #36/#88, aucune opération Home Assistant. / Scoped #37 contracts and tests; no #81 migration, #36/#88 write, or Home Assistant operation.

**Sources / References:** [#37](https://github.com/christophejaubert/ha-trybatec/issues/37), [#36](https://github.com/christophejaubert/ha-trybatec/issues/36), [#81](https://github.com/christophejaubert/ha-trybatec/issues/81), [#88](https://github.com/christophejaubert/ha-trybatec/issues/88), [#45](https://github.com/christophejaubert/ha-trybatec/issues/45). L'historique #125/#150 et la convergence #153 sont déjà réutilisés dans les trois modules #37 sur `main`. / Existing #125/#150 and #153 work is reused rather than replayed.

## FR — Contrats de preuve

### Identités et générations

- La génération physique est la clé *(compte, lot, fluide, numéro de série)*. L'identifiant d'entité Home Assistant, son éventuel suffixe `_2`, son `unique_id` et le `statistic_id` ne constituent **pas** des générations physiques.
- `first_observed_at` et `last_observed_at` désignent seulement les observations disponibles. `service_start` et `service_end` restent nulles sans preuve directe ; un intervalle entre générations n'est pas une date de remplacement ni une consommation nulle.
- Chaque compteur déposé garde son propre identifiant physique et ses consommations historiques candidates, avec `historical_reading_only`. Rien ne transforme sa contribution en mesure active.
- Index bruts : la passerelle #37 recalcule les diminutions entre relevés successifs, même si un compteur d'anomalies fourni par la source est à zéro. Elle refuse les index invalides. Les différences d'index entre compteurs différents sont toujours interdites.
- Consommations journalières : une journée en dehors des bornes d'observation connues ou d'une plage de service explicitement prouvée est bloquée. Les collisions intergénérations non approuvées et les recouvrements non adjacents restent refusés.

### Attribution des décisions #36 à la journée

Contrat optionnel **`day_decision_fingerprints: {date: decision_fingerprint}`**, au niveau d'une variante historisée `preview_only`. Une journée contenant une contribution estimée peut ainsi transporter son identifiant de décision individuel, son compteur physique, sa variante `raw/smoothed`, sa provenance `measured/mixed/estimated_linear_confirmed` et les quantités exacte, mesurée et estimée.

Le contrat vérifie qu'une décision de journée figure dans les décisions sélectionnées, que la journée possède une estimation strictement positive et que les sommes sont exactes. Une décision unique ou un ensemble d'approbations sans attribution journalière précise reçoit `approval_set_unattributed` et un blocage explicite : **un ensemble de décisions n'autorise pas automatiquement chacune des journées**. `day_candidate_unverified` signifie uniquement « référence apportée par l'amont » : **le backend #36 doit encore contrôler indépendamment** l'identifiant, la version de révision, la fenêtre, la consommation approuvée et la portée physique exacte. Le pont #37 ne peut pas produire cette preuve à sa place.

### Audit HA #81 sans migration

`audit_ha_identity_references_37(account_key, entry_id, meters, registry_entities, observed_references)` s'appuie sur le moteur existant `meter_identity.preview_stable_identity_transition`, sans recréer une politique d'identité. Il accepte uniquement un inventaire borné et les références *observées* de consommateurs (tableaux de bord, automatisations, Énergie, Recorder, externes). Il signale les références `entity_id` orphelines du registre fourni, les cohabitations stable/legacy et les suffixes techniques, mais :

- un `entity_id` absent du registre ne prouve pas la disparition de son historique Recorder ;
- un `statistic_id` n'est pas tenu d'être un `entity_id` présent au registre ;
- un suffixe `_2` n'autorise ni une nouvelle génération physique, ni la suppression de l'ancien identifiant ;
- le scan des consommateurs observés n'est **jamais exhaustif** ; ses champs `consumer_inventory_exhaustive`, `recorder_statistic_references_exhaustive`, `safe_to_delete_legacy_entity` et `safe_to_migrate` restent faux.

### Qualification des états

- **`verifie`** : uniquement les contraintes arithmétiques et de structure vérifiées localement sur les données fournies. Ce mot ne qualifie pas un inventaire réel complet ni une persistance Recorder.
- **`partiel`** : des journées calculables existent, mais les preuves extérieures (décisions #36, historique du fournisseur, versions Recorder, consommateurs Énergie) restent incomplètes.
- **`contradictoire`** : conflit ou violation détectée (période, chevauchement, doublon, références héritées simultanées, consommateur orphelin), avec refus sûr.
- **`inconnu`** : aucune base suffisante pour conclure. Une absence d'observation n'est jamais une preuve d'absence.

Même lorsque la somme est `verifie` localement, les indicateurs `physical_inventory_complete`, `recorder_persistence_verified`, `competing_versions_exhausted`, `energy_activation_authorized` et `writes` restent **faux** dans l'enveloppe #37→#88.

### Dépendances et qualification V-01–V-12

| Critère #37 | Développé ici ou acquis réutilisé | Reste bloquant / preuve indépendante |
| --- | --- | --- |
| V-01 Nettoyage hérité | Audit des références seulement | Nettoyage prohibé ; audit exhaustif #81 avant toute action séparée |
| V-02 Déposés | Conservés en lecture seule dans le modèle | Recette de visibilité réelle HA, inventaire complet |
| V-03 Statuts | En service / déposé / inconnu conservés | Recette affichage/appareils |
| V-04 Traçabilité | Compte/lot/fluide/série, bornes, unités, index décroissants, anomalies | Vérifier API et source réelle |
| V-05 Continuité | Plusieurs générations, contributions par journée, trous/chevauchements refusés | Transitions et sources réellement justifiées |
| V-06 Énergie | Contributions déposées candidates, somme contrôlée | #36 Recorder et #88 sélection native exclusive |
| V-07 Tests/migration | Scénarios synthétiques ; aucune mutation | Preuve CI au SHA exact et recette HA ; migration séparée |
| V-08 Origine des lectures | Aucune déduction à partir de la cadence | Indicateur API indépendant si disponible |
| V-09 Lissage | Aucune présomption sur le graphique du fournisseur | Méthode approuvée et révisions #36 |
| V-10 Inventaire | Union conservatrice des sources observées | Exhaustivité de toutes les générations non démontrée |
| V-11 Migration non destructive | Compatibilité #81 auditable sans écriture | Migration #82 non autorisée ; consommateurs/récupération inconnus |
| V-12 Séries Énergie | Empreintes et refus des alternatives ambiguës | #88 preuves exhaustives de non-double comptage, écriture/rollback réels |

**Tests fictifs ajoutés :** décision par jour ou groupée, décision étrangère/inutilisée, contrôle d'index décroissant sans indicateur, consommation hors bornes, somme estimée/mesurée forgée, suffixe `_2`, stable/legacy simultanés, consommateur orphelin, référence statistique indépendante, collision de registre et absence d'écriture.

**Limites des preuves :** une CI verte n'atteste ni une collecte exhaustive du portail ni un audit exhaustif des consommateurs externes. La revue Recorder et l'activation Énergie relèvent de #36/#88 et nécessitent les décisions d'exploitation distinctes. Ne pas clôturer #37, #81 ou #88 au vu de ces seuls tests.

## EN — Interface and acceptance summary

Physical generations are identified solely by *(account, lot, fluid, serial)*. Home Assistant `entity_id` suffixes, `unique_id` and `statistic_id` are **technical references, not physical replacements**. Observation bounds and separately evidenced service dates remain distinct; unknown transitions and missing intervals are never interpreted as zero consumption. Retired meters retain historical-only candidate consumption but are not active sensors. Descending raw indexes are independently checked, even when supplier anomaly counters report none. Known-period violations and unapproved overlapping physical series fail closed.

The optional `day_decision_fingerprints` input binds a positive estimated daily delta to a specifically supplied #36 approval reference. Pooled decisions remain `approval_set_unattributed`; specific references remain `day_candidate_unverified` until the #36 backend independently validates revision, time span, amount and physical scope. The handoff conserves per-meter daily identities, amounts and provenance and exposes explicit blockers. It never certifies full historical inventory, Recorder persistence, or Energy exclusivity.

The new non-mutating #81 audit reuses the existing stable-identity preview. It detects stable/legacy coexistence, sampled orphan references and technical numeric entity suffixes, but its snapshots are **not an exhaustive consumer scan**, do not establish safe deletion and cannot authorize any migration. `statistic_id` and `entity_id` are not interchangeable. Qualification statuses `verifie`, `partiel`, `contradictoire`, `inconnu` distinguish locally checked arithmetic from independent real-world acceptance.

For V-01/V-11, legacy cleanup and migration remain forbidden. V-02/V-03/V-04/V-05/V-08/V-09 obtain additional non-destructive contract checks but await live qualification. V-06/V-10/V-12 still depend on independent complete source/Recorder/Energy evidence from #36/#88. V-07 requires exact-SHA CI and separately permitted production acceptance. Neither a draft PR nor successful synthetic tests are a production acceptance, merge, release, installation or migration authorization.
