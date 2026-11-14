# 0.3.5b1 — Préversion intégrée / Integrated experimental prerelease

## FR — Changements, qualification et limites

**Bêta expérimentale non officielle.** Cette version rassemble les corrections du panneau Trybatec (navigation, accessibilité et déclinaisons clair/sombre, textes FR/EN, détails des compteurs, parcours de configuration), la découverte mutualisée de l'historique par compte, les options de tarifs annuels sans JSON obligatoire, les diagnostics, la gestion des identités physiques et les protections d'accès/notification développées depuis `0.3.4b1`.

**Historique et Énergie :** le code de #36 introduit des tentatives Recorder identifiées, versionnées, journalisées et mises en quarantaine en cas de dérive ; #37 reconstitue les consommations de chaque compteur physique sans soustraire les index de générations différentes ; #88 relit les preuves Recorder, la filiation et les références Énergie sur une sélection bornée. Les lacunes fournisseur ne sont jamais présumées égales à zéro.

**Tests :** la chaîne #36 → #37 → L6 → L7 a réussi sur Home Assistant Core `2026.11.0` **isolé**, avec véritable SQLite Recorder, gestionnaire de sauvegarde, écriture additive Énergie, journal durable, relecture disque, refus de modification externe pendant sauvegarde, reprise après interruption et restauration d'archive dans un répertoire temporaire distinct. Les relevés et comptes sont fictifs. La recette métier après installation relève exclusivement du propriétaire et n'est pas un préalable à cette bêta. Les tests ne garantissent pas l'impossibilité de modifications futures par d'autres composants privilégiés.

**Fonction désactivée à la livraison :** **l'ajout groupé EF/ECS/chauffage dans le tableau Énergie n'est pas opérationnel sur l'installation**. Le verrou `NATIVE_ENERGY_BULK_WRITES_ENABLED_88=False` demeure actif et la confirmation WebSocket L7 est refusée. Les tests démontrent le moteur en environnement isolé, **pas une fonction utilisable sur Home Assistant réel**. Aucune migration automatique des identités existantes, import historique Recorder, suppression, restauration ou modification du fournisseur n'est autorisée par l'installation.

**Précautions :** les unités (EF/ECS en m³, CET attendu en kWh), l'identité des compteurs et les références Energy restent protégées. Les contrôles d'interface sont synthétiques. **La recette métier sur l'installation relève du seul propriétaire et ne conditionne pas la livraison de la bêta.** La fusion, la release et l'installation sont distinctement autorisées ; elles n'autorisent pas d'écritures Recorder/Énergie, migration, restauration ni purge.

**Compatibilité :** `2026.11.0` est la version Core effectivement qualifiée pour cette candidate. Les nouvelles candidates devront partir de la dernière version stable officielle Home Assistant disponible au début de leur qualification. [Dossier de qualification](docs/CANDIDATE_0_3_5b1_RELEASE_GATE_FR_EN.md).

## EN — Changes, evidence and limitations

**Unofficial experimental beta.** This candidate brings together Trybatec panel fixes (navigation, accessibility, light/dark themes, FR/EN content, meter details and guided setup), shared account-wide history discovery, native annual tariff options without mandatory JSON, diagnostics, physical identity and access/notification safeguards developed since `0.3.4b1`.

**History and Energy:** #36 adds versioned, uniquely identified, durably journaled Recorder attempts and quarantines detected external drift. #37 calculates consumption within each physical meter generation, never subtracting readings from different meters. #88 audits exact selected Recorder versions, physical lineage and Energy references. Missing supplier readings are not assumed to be zero.

**Isolated qualification:** real Home Assistant Core `2026.11.0` Recorder SQLite, BackupManager and EnergyManager exercised a single positive native #36 → #37 → L6 → L7 test with a durable journal and persisted Energy readback. Negative tests cover an external writer during backup, interruption and recovery, guarded rollback, corrupted backups and archive restoration to a separate disposable directory. All source records and identities are synthetic. Owner-led business acceptance is a separate, **non-blocking** post-installation responsibility. The tests do not claim absolute exclusion of future privileged third-party writers.

**Deliberately unavailable:** **bulk EF/ECS/heating enrollment into the live Energy dashboard is NOT enabled in this beta**. The `NATIVE_ENERGY_BULK_WRITES_ENABLED_88=False` gate and WebSocket confirmation refusal remain active. Isolated transaction test success does **not** make bulk enrollment operational on a user's Home Assistant. Existing identity migration, historical Recorder imports, deletion, restore and supplier modifications are not implicitly authorized.

**Acceptance and compatibility:** the owner has explicitly authorized the distinct merge, release and HA installation operations. Real UI, meter identity and CET kWh/Energy business acceptance remain the owner's responsibility after installation and **are not a delivery gate**. Migration, sensitive writes and restoration still require separate authorization. `2026.11.0` is the approved tested Core baseline for this beta. Future candidate qualification starts from the latest officially released stable Home Assistant version. See [candidate gate](docs/CANDIDATE_0_3_5b1_RELEASE_GATE_FR_EN.md).

---

# 0.3.4b1 — Candidate intégrée / Integrated beta candidate

## FR — Évolutions et limitations

Candidate regroupant les travaux préparés : installation et réauthentification sécurisées, notifications d'accès, identités stables **pour nouveaux comptes seulement**, tarifs annuels et calculs YTD, options natives sans JSON obligatoire, corrections d'interface et de traduction, filiation historique des compteurs, contrats Recorder et prévisualisation Énergie en lecture seule. Les contrôles CI, confidentialité et accessibilité synthétique sont renforcés.

**Limites bloquantes :** le rejeu sélectif Recorder reste interdit sans preuve de quiescence du writer ; L6 ne prouve pas encore l'admissibilité exhaustive Énergie, et L7 refuse toute écriture réelle. Ces éléments ne constituent pas un ajout groupé opérationnel. La migration et le nettoyage des anciens identifiants restent exclus.

**Bêta expérimentale destinée à la recette, non validée en production :** publication expressément demandée avant la recette réelle sur Home Assistant. Les fonctions #36/#37/#88 n'ont pas toutes atteint leurs critères métier ; la reprise sélective Recorder et l'ajout groupé Énergie demeurent bloqués par des protections volontaires, et les compteurs déposés nécessitent une validation réelle. **Ne pas installer cette bêta en pensant pouvoir encore tester l'écriture groupée EF/ECS/chauffage : ce parcours n'est pas opérationnel.** Une autorisation distincte reste indispensable avant installation, sauvegarde, mutation Recorder/Énergie ou restauration. Procédure : `docs/PRODUCTION_ACCEPTANCE_0.3.4b1_FR_EN.md`.

## EN — Changes and limitations

Integrated candidate combining secured setup and reauthentication, access notifications, stable physical identities **for new accounts only**, annual tariff/YTD features, native options without mandatory JSON, UI/translation fixes, retired-meter historical lineage, Recorder evidence contracts and read-only Energy previews. Synthetic CI, privacy and accessibility checks are strengthened.

**Blocking limitations:** selective Recorder retry remains denied without independently proven writer quiescence; L6 has not established comprehensive Energy eligibility and the L7 adapter denies real writes. This is **not** proof of working bulk Energy enrollment. No migration or cleanup of historic identities is included.

**Experimental beta for subsequent production acceptance, not production-validated:** the user explicitly requested publication before live Home Assistant acceptance. Full business qualification of #36/#37/#88 is incomplete; selective Recorder retries and bulk Energy activation remain intentionally locked down, while retired-meter continuity needs live validation. **This beta cannot yet test actual bulk EF/ECS/heating writes:** the enrollment UI is not operational. Publication does not authorize installation, backup, Recorder/Energy writes or restoration, which remain separately controlled. See `docs/PRODUCTION_ACCEPTANCE_0.3.4b1_FR_EN.md`.

---

# 0.3.3b1 — Consolidation post-recette (bêta expérimentale)

**Préversion expérimentale.** Sa publication ne constitue ni une installation sur Home Assistant ni une validation fonctionnelle en production ; consulter [le périmètre et les limites](docs/RELEASE_SCOPE_0.3.3b1.md).

- Corrige l'escalade des notifications d'accès : après une indisponibilité réseau déjà signalée, un refus d'authentification avéré remplace le message de notification sur le même identifiant, sans notification doublonnée. Une panne transitoire ultérieure ne rétrograde pas l'alerte d'authentification tant qu'une actualisation réussie n'a pas effacé l'incident.
- Ajoute des tests synthétiques de déduplication, d'escalade, de non-rétrogradation et de résolution de notification.
- Accessibilité (#70) : les pictogrammes décoratifs du menu Home Assistant, des onglets et du chevron de navigation ne sont plus annoncés séparément par les lecteurs d’écran ; les boutons, textes et états restent explicites. Recette navigateur synthétique requise, sans revendication WCAG générale.
- Actualise la préparation HACS/Marketplace avec [un audit de travail](docs/MARKETPLACE_READINESS.md), sans candidater au catalogue officiel.
- Préserve les corrections et parcours existants de `0.3.2b1` ; les anciennes PR #46, #71 et #72 ont déjà été reprises en tout ou partie sous une forme plus récente et ne doivent pas être fusionnées sans réconciliation. La PR #40 est réinterprétée à partir du code actuel.

**Limites et exclusions :** aucune prétention de validation exhaustive WCAG/ergonomie réelle ou des écritures Recorder/Énergie ; les opérations de désinstallation, réinitialisation et purge A01–A31 ne sont pas exposées ; la pondération DJU (#34), EVO-007 et le référencement officiel Marketplace restent différés. Les budgets historiques 120 s/24 HTTP et 600 s/80 HTTP demeurent inactifs : seules les protections existantes de secours continuent de s'appliquer.

**Aucun effet automatique** sur les index du fournisseur, les statistiques Recorder, les références Énergie, les compteurs déposés ni les paramètres Home Assistant. Toute opération sur une installation réelle nécessite une confirmation distincte.

---

# 0.3.2b1 — Cohérence de l'interface et prérequis Énergie (candidate)

Candidate fondée sur le socle correctif 0.3.1b3 (PR #77) intégré dans `main`, sans fusion ni publication automatique.

- Dates et horodatages localisés, chiffres groupés sans arrondi, formatage d'index de compteur.
- Contrôles mobiles : accès au menu HA, onglets défilants signalés et sélection visible.
- Compteurs déposés : lecture historique explicite en lecture seule ; bornes datées et dernier index source brut présentés avec leur statut, sans déduire une date de remplacement.
- Charte Trybatec : titres et pictogrammes de fluide colorés, boutons et navigation générale verts, états distincts.
- Fréquence de synchronisation en jours/heures/minutes, sans changement du stockage des minutes.
- Accueil : vérifications, prérequis et accès contextuels, sans alerte abusive sur les options facultatives.
- Les trois fluides sont inclus dans les aperçus Recorder sous contrôle inchangé des unités et des validations.
- Sélection d'une nouvelle version Énergie désactivée lorsque les versions Recorder vérifiées ou la source Trybatec déjà active sont absentes. La première activation reste un parcours séparé.
- UI-003 : configuration complète des unités et UUID dans Compteurs, synthèse des anomalies historiques, journalisation dans un encart autonome et lien d'accès au panneau depuis l'engrenage Home Assistant. Les options natives restent disponibles en secours pendant la recette.
- Maintien des protections 0.3.1b3 : lecteur HTTP fragmenté, garde 1 800 s / 512 appels, 16 Mio par réponse d'index, 64 Mio historiques cumulés, diagnostics et annulation asynchrone ; budgets 120 s/24 et 600 s/80 toujours non actifs.
- EVO-007 (sauvegarde de version via Marketplace) est différée et n'est pas développée dans cette version.
- Tests et vérifications de la candidate : consulter `docs/specifications/trybatec-ui-0.3.2b1.md`, et les contrôles CI du SHA final.

**Aucun effet automatique** sur Recorder, Énergie, les entités, les relevés du fournisseur ou les données locales de Home Assistant. La fusion nécessite une autorisation distincte.

---

# 0.3.1b3 — Correctifs HTTP, historique et Recorder

Cette préversion corrective fait suite aux vérifications après installation de 0.3.1b2.
**Préversion bêta expérimentale : installation volontaire avec sauvegarde Home Assistant préalable recommandée.**

- Lecture HTTP : attendre l'intégralité du corps, même avec fragmentation réseau,
  avant de décoder un JSON. Préserver le plafond des réponses d'index (16 Mio)
  et l'absence de contenu fournisseur dans les journaux.
- Historique : ne plus subdiviser une période à la suite d'un simple JSON
  malformé ou d'une structure de réponse invalide ; conserver une subdivision
  contrôlée uniquement pour les erreurs qui peuvent effectivement être résolues
  en réduisant la période. Aucune portion manquante n'est tenue pour validée.
- Recorder : corriger l'appel à la métadonnée statistique qui combinait deux
  paramètres incompatibles ; maintenir les contrôles des unités et des sommes
  sans autoriser de nettoyage ni de bascule Énergie.
- Diagnostics : préparer l'inventaire en lecture seule des limites techniques
  effectives, la traçabilité expurgée et les budgets candidats validés sous
  réserve de tests représentatifs ; ne pas les afficher comme actifs prématurément.
- Progression historique : ne jamais présenter comme progression de la tâche
  demandée les mesures d'une autre opération concurrente du même compte.
- Plafonds de secours effectivement appliqués : 1 800 secondes et
  512 tentatives HTTP par opération suivie ; arrêt avec rejet explicite de
  tous les résultats partiels. Ils sont distincts des budgets candidats
  standard 120 s / 24 appels et exhaustif 600 s / 80 appels, non activés :
  un test synthétique valide nécessite plus de 80 appels.
- Reprise après interruption : une nouvelle demande relit intégralement
  l'intervalle initial. Aucun corps fournisseur ni checkpoint incomplet
  n'est repris, faute de preuve de cohérence instantanée de l'API source.
  Le redémarrage intégral est sûr vis-à-vis des fragments partiels, mais
  n'est pas une reprise incrémentale des périodes déjà lues.
- Tests : flux HTTP fragmenté, caractères UTF-8 répartis, taille bornée, JSON
  invalide, annulation, échecs d'historique, audit Recorder et CI complète.

Les autres évolutions fonctionnelles et visuelles de 0.3.2b1 restent sur la PR #75.
Les opérations d'import Recorder, de nettoyage, de tarifs et de configuration
Énergie conservent leurs procédures de sauvegarde et confirmation distinctes.

**Exclusions :** aucune modification automatique de Home Assistant installé,
du fournisseur Trybatec, des relevés sources, du tableau Énergie ou des
statistiques Recorder. La disponibilité effective dépend d'une publication GitHub distincte.

---
# 0.3.1b2 — Correctifs de recette du panneau Trybatec (candidate)

Correctif ciblé après la recette réelle de `0.3.1b1`. Aucune migration automatique,
aucun changement des préférences Énergie, aucun import Recorder et aucune
modification des index hébergés par le fournisseur.

- **Version du panneau :** lecture effective du manifeste déplacée vers un exécuteur
  Home Assistant ; évite les accès bloquants au disque dans la boucle asyncio,
  tout en conservant la valeur de version réellement installée.
- **Tarifs annuels :** à l'ouverture de la page Tarifs, interrogation historique
  *en lecture seule* des relevés fournisseur datés (de 2000 à aujourd'hui),
  limitée au périmètre vérifié de chaque compte. Les dates des compteurs déposés
  alimentent les exercices proposés (première/dernière année observée ± 1 an).
  Les tarifs déjà saisis restent proposés même hors intervalle. L'interface
  indique explicitement un échec ou une vérification en cours ; elle n'invente
  pas de dates de remplacement ni d'années vérifiées. Les résultats complets
  sont mis en cache en mémoire par compte pour la journée.
- **Audit des entités :** vérification conservatrice des compteurs déposés
  à partir des identifiants techniques exacts et de l'appartenance au compte,
  sans exiger d'index actif. Les erreurs ou métadonnées Recorder incomplètes
  sont signalées sans présenter l'entité comme supprimable ni proposer de
  bascule Énergie. La prévisualisation native de migration reste distincte.
- **Navigation :** correction des attributs HTML `data-*` des boutons vers
  Énergie et l’ancienne interface Options ; la délégation des clics est
  couverte par des tests qui exécutent les gestionnaires réels.
- **Actualisation de l’IHM :** URL du module de panneau versionnée à partir
  du manifeste effectivement installé ; contrôle de version lors du retour
  sur l’onglet et périodiquement lorsque celui-ci est visible. Rechargement
  automatique uniquement en l’absence de saisies en cours ; sinon,
  proposition d’actualisation explicite sans écraser le formulaire.
- **Saisie :** conservation du nœud HTML et du focus lors des événements
  intermédiaires de dates, heures, valeurs numériques et texte ; les
  prévisualisations Recorder devenues obsolètes sont invalidées avant toute
  confirmation. Tests Chromium synthétiques FR/EN, ordinateur/mobile, avec
  frappes successives et contrôle d’intégrité du champ.
- **Inventaire des entités :** classification prudente à partir des
  identifiants techniques et du statut effectivement vérifié (index actifs,
  index historiques, tarifs, coûts et consommations annuelles). Ni un suffixe
  `_2`, ni l’état `unknown` ne prouvent une suppression possible.
- **Tests :** régression sur les dates anciennes et les collisions de comptes,
  absence de données inventées, mise en cache, garde d'identité et refus des
  suppressions automatiques. Validation CI et test réel après installation
  nécessaires avant toute affirmation de recette achevée.

**Exclusions :** aucune suppression, réinitialisation, purge, retouche des
statistiques Recorder, bascule Énergie, modification des tarifs ou du portail
fournisseur. Les spécifications A01–A31 restent documentaires.

---
# 0.3.1b1 — Interface et identité Trybatec (préversion candidate, non publiée)

**Périmètre de cette tranche : corrections d'interface non destructrices.** Ce candidat n'autorise aucune migration ni modification d'une installation Home Assistant.

### Changements par rapport à 0.3.0b1
- Le choix de l'exercice annuel est limité aux années des relevés datés du compte (première année −1, dernière année +1), y compris les compteurs déposés. Les exercices tarifés existants hors plage restent sélectionnables individuellement ; une plage de secours explicitée est utilisée en l'absence de relevés datés.
- La version effective de l'intégration installée apparaît dans l'en-tête de toutes les pages du panneau, sans valeur présumée.
- Contraste des surfaces et de la sélection des compteurs amélioré en thèmes Home Assistant clair/sombre ; sélection sans déplacement du contenu, états accessibles et pictogrammes EF/ECS/CET distincts.
- Palette Trybatec documentée et harmonisée entre l'interface et les ressources graphiques ; exigences WCAG 2.2 AA conservées comme **critères à vérifier**, non comme conformité démontrée.
- Arbitrages détaillés A01–A31 et registre des décisions repris depuis la PR #72 à titre de spécifications futures, sans activation des fonctionnalités destructrices.

### Exclusions explicites
- **Aucun outil de désinstallation, réinitialisation ou purge** : l'assistant destructeur A01–A31 n'est pas implémenté ni exposé dans cette préversion, en attente des garanties d'appartenance, de conservation, de reprise et des scénarios T01–T40.
- Aucune écriture vers le portail fournisseur Trybatec.
- Aucun effacement d'entités, d'historique Recorder, de statistiques ou de préférences Énergie ; les anciennes interfaces et identifiants sont conservés.
- Aucune sauvegarde, importation historique, bascule Énergie ou redémarrage automatique.
- Aucune publication ni fusion ne résulte de la préparation de cette note.

### Validation requise avant fusion
- CI intégrale verte sur **le SHA final** : tests Python 3.13/3.14, HACS, hassfest, qualité, sécurité, Recorder et navigateur synthétique.
- Vérification du nouvel emblème approuvé dans les deux PNG officiels (256/512 px) et de son rendu à 24/32/64 px, sur fonds clair/sombre.
- Recette fonctionnelle/visuelle Home Assistant réel sur bureau/mobile et en FR/EN restant à exécuter ; la recette Chromium synthétique n'en tient pas lieu.
- La fusion dans `main` et la publication d'une release nécessitent chacune une autorisation explicite distincte.

Sources : [périmètre 0.3.1b1](docs/RELEASE_SCOPE_0.3.1b1.md) · [système de conception](docs/DESIGN_SYSTEM.md) · [spécifications A01–A31](docs/specifications/trybatec-cleanup-reset-purge-A01-A31.md).

---

# 0.3.0b1 — Unified Trybatec panel (experimental beta)

**Experimental prerelease.** This version brings together the additive Home Assistant sidebar panel **Trybatec** and the current work on history smoothing, physical meter inventory and annual tariffs (issues #36, #37, #42 and integration tracking #45). It is intended for evaluation, not a claim that all acceptance criteria have been completed.

### New and improved

- A dedicated **Trybatec** sidebar panel presents account information, meters, history and smoothing, tariffs, Energy and version management, diagnostics and administrative tools. The existing Home Assistant **Configure / Options** interface remains available; its seven menu destinations and FR/EN labels have regression coverage.
- Historical reviews preserve actual source readings and meter identities. An administrator can explicitly record an **estimated starting index** as a separate hypothesis with its own source fingerprint, reason and revision confirmation. Approved hypotheses affect the **smoothed** consumption alternative only; the raw physical-meter series remains unchanged. Previews distinguish measurements, assumptions, units and boundaries.
- Historical Recorder series are versioned rather than silently rewritten. The importer revalidates its exact plan, source provenance, meter identity and units; Energy activation is an explicitly confirmed, separately audited operation with double-counting safeguards and rollback handling. No import or activation is triggered by installation.
- Annual tariffs can be edited through the panel without manual JSON editing. The tariff page also requests read-only yearly consumption/cost estimates (EUR/m³ for water, EUR/kWh for heating), visibly distinguishing missing rates, unverified measurements and provisional versus approved values.
- A separate technical-entity audit distinguishes **physical meters, including retired meters**, from possible older duplicate Home Assistant entities. The audit includes known Energy references. An unavailable entity or an `_index_2` suffix alone never proves that an entity is safe to delete.
- French and English panel text has additional automated execution tests. An isolated synthetic Chromium test covers both languages, desktop and mobile layouts, and all seven panel sections without connecting to the user's Home Assistant installation.

### Explicit limitations and safe upgrade

- **Real Home Assistant visual and end-to-end acceptance has not yet been performed** in FR/EN on desktop and mobile. Synthetic browser/isolated Home Assistant tests do not replace production acceptance. Further corrections may be needed in later betas.
- **Controlled deletion of legacy technical entities is not included.** Recorder, dashboards, automations and other references have not all been exhaustively audited. Potentially obsolete entities are presented for investigation only: no automatic cleanup is permitted.
- This beta does **not** guarantee complete historical reconstruction, migration or seamless continuity of existing Energy statistics. Estimated values are not source readings, and historical costs are not invoices.
- Before any subsequent history import, migration, Energy switch or cleanup on a real installation, first make and verify a **backup of Home Assistant, Recorder and `.storage`**, inspect the preview and obtain separate explicit approval for that operation. Updating or installing this beta itself is not permission to perform those actions.
- Do not select multiple versions or physical and consolidated alternatives for the **same consumption** in Energy: doing so may double-count.

**Scope:** issues #36, #37, #42 and #45. **Status:** open beta; outstanding real-world acceptance and safe cleanup remain tracked rather than represented as completed.

---

# 0.2.0b17 — Preserve coexisting physical meters and safely switch Energy

- Recognize a legacy Trybatec meter alongside its already registered live
  replacement only when ownership, physical device, account, unit, lot and
  identity are verified. Both entity IDs, unique IDs and Recorder histories
  remain unchanged; no collision is forcibly reassigned.
- New administrator-only `preview_live_meter_energy` read-only action and
  `activate_live_meter_energy` explicit confirmed action for replacing one
  Energy source with its verified active meter. It checks existing Recorder
  sum metadata, compatible units and Energy slots, rejects competing selected
  statistics, saves an audit snapshot, re-reads persisted preferences, and
  rolls back on a verifiable write failure.
- Support Recorder-verified b15 heating series in an existing gas-type Energy
  source when the unit is kWh, consistent with HA Core's gas source schema.
- All prior source IDs and historical Recorder rows are left intact. A source
  reference switch does not automatically join older and newer sensor series
  into a continuous Energy history. A verified consolidated history must be
  imported and selected separately for that purpose.
- Add regression tests for identity collision spoofing, cold/hot water,
  heating, duplicate series, unit/category mismatches and stale approval.

**No automatic production changes**: installing b17 does not migrate a
registry entry, reconfigure Energy or write Recorder. Production operations
remain separately previewed, backed up and approved.

---

# 0.2.0b16 — Defer first Trybatec synchronization until HA has started

- The first vendor index request runs **after** Home Assistant signals
  `homeassistant_started`, not during config-entry setup. On an integration
  reload while HA is already running, the initial refresh still starts
  immediately.
- Meter entities are created from a successful vendor response, without
  synthetic readings or speculative units. Existing entity and Recorder IDs
  remain unchanged.
- An initial network/data failure is retried by the coordinator after
  approximately one minute instead of waiting for the normal polling
  interval (default 12 hours). After success, the configured polling interval
  resumes. Authentication failures still request reauthentication.
- Pending first-poll listeners are canceled on integration unload; no
  historical Recorder import, Energy write or entity migration runs at startup.
- Isolated Home Assistant regression tests cover boot ordering, transient
  failure and recovery, and unload before the started event.

**Scope and limitations:** This targets startup timing and resilience; it
cannot guarantee availability of the external Trybatec service. Any
production history import, Energy switch or entity migration still requires
independent review, backup and explicit confirmation.

---

# 0.2.0b15 — Experimental beta (opt-in history and Energy tools)

**PR #38 was merged into `main` after successful mandatory CI. Installation or publication alone does not authorize a historical Recorder import or a change to Energy preferences on a real Home Assistant instance.**

### Changes currently implemented

- Configuration from username and password for a single unambiguous housing,
  plus a strictly validated full Index page URL fallback; native
  reauthentication retaining the same HA config entry.
- Persistent access problem notifications with delayed network-failure
  threshold and recovery dismissal.
- Configurable historical sparse-period and zero-day alert thresholds.
- Opt-in, read-only linear residual reconstruction from actual physical
  meter index bounds; explicit user-declared review decisions and confirmation.
  Retain raw measured index readings, including zeros and retired devices.
  Date-based daily proposals use Europe/Paris civil days and never represent
  estimated consumption as a measured index.
- A new native review path in integration options for manual/telemetry
  explanations and individual sparse periods. Decisions are locally
  stored against exact source fingerprints; changed source values invalidate
  stale choices.
- Read-only physical-meter alternative consumption variants: measured-only
  or measured plus confirmed linear gap estimates. Separate meter generations
  remain distinct; a logical dwelling+fluid consolidation adds consumption,
  never cumulative indexes.
- Experimental, **non-executing** modules to preview entity migrations,
  track V1/V2/V3 historical revision states, and prepare exclusive Energy
  preference replacements and rollback snapshots.
- API-visible retired meters can appear as historical-only index sensors,
  without being treated as continuously increasing live consumption.
- Synthetic Python and isolated Home Assistant tests have been added. Their
  complete status must be checked at the exact final PR head.

### Further implementation (not yet accepted on the target installation)

- `history_plan_b15.py` creates hourly UTC Recorder plans from Paris civil-day
  consumption, for each verified physical meter variant and one selected
  dwelling/fluid consolidation. Index readings are **not** combined.
- `trybatec.preview_b15` produces a source-specific fingerprint;
  `trybatec.import_b15` requires the same fingerprint, a confirmed backup and
  explicit approval. This stores the import journal before enqueuing new `_vN`
  Recorder IDs. Old generations are never overwritten or deleted.
- `trybatec.verify_b15` reads back every persisted hourly sum and only
  then marks imported versions as verified.
- `trybatec.preview_b15_energy` checks the exact Energy preference snapshot,
  Recorder verification and **all** same-dwelling physical alternatives.
  `trybatec.activate_b15_energy` is an explicit admin-only action that
  flushes and re-reads Home Assistant Energy preferences and the b15 version
  ledger. Audited, guarded rollback is attempted on failure, never
  overwriting a concurrent unrelated Energy edit.
- `trybatec.archive_b15_meters` persistently saves the exact identities
  and latest actual index observations of retired physical meters from the
  complete vendor history. After an integration reload, historical-only
  sensor devices remain consultable even if no longer returned by current
  portal polling.
- `trybatec.preview_b15_migration` and `trybatec.apply_b15_migration`
  support a conservative **one-entity-at-a-time** technical unique-ID
  migration, only if same lot/serial/fluid/unit provenance can be verified.
  The actual Home Assistant `entity_id` is kept unchanged, preserving
  dashboard and automation references and Recorder history.
  Unprovable legacy identity cases remain blocked for manual review.

### Known validation limitations and safety requirements

- Validate all new Recorder, Energy and historical-device actions on
  isolated HA, including restart/recovery and genuine Recorder persistence.
- Verify Energy rollback on real current-version Home Assistant and
  compatibility with the schema used on the user's instance.
- Migrate or explicitly retain any legacy technical entities whose
  physical identity or source unit cannot be proven; no unsafe cleanup.
- Mandatory automated CI checks passed for the PR and the merge on `main`; the
  final release workflow must verify the exact tag target and the post-merge
  main CI before publishing.
- User-controlled acceptance of the final IHM and runtime behavior,
  with no automatic production import or settings modifications.

**Compatibility limitation:** accounts managing several copropriétés are not
validated as an automatic configuration scenario. Never silently select a
housing or use a portal UUID without checking that account's authorization.

**This is an experimental prerelease, not a claim of complete field acceptance.**
Do not perform production history imports, Energy switching or legacy migration
without isolated validation and backups.

---

# 0.2.0b14 — Unreleased candidate: full-range first, adaptive history recovery

**Pull request only — no merge, release, HACS installation or Home Assistant changes.**

- First request the **entire historical interval selected by the administrator**, without pre-splitting every 92 days or imposing a global duration/window/request ceiling.
- If a response is oversized, malformed, missing required structure, explicitly rejected as a window (HTTP 408/413/414/422), or times out, retry shorter overlapping intervals until all are obtained or the smallest interval still fails.
- Keep auth failures and unrelated network/HTTP errors fail-closed. Limit each individual response's bytes, lines and observations; space sequential requests. Do not log vendor payloads, tokens or credentials.
- Combine all authorized physical meters (including replaced/retired meters), deduplicating repeated timestamp/value pairs across overlapping intervals. Reject contradictory observations instead of selecting one silently.
- A persistently invalid one-day interval blocks the entire preview and any Recorder import; report its dates and a sanitized error reason. Preserve any previous successful review cache.
- Expose accepted/rejected window counts and a source-window coverage flag in the read-only preview. These prove successful API responses for requested ranges, **not** independent vendor data completeness.
- Remove aggregate history row/meter/reading ceilings that arbitrarily prevent otherwise valid multi-year collections. Keep vendor *per-response* safeguards and per-meter identity checks.
- Regression tests cover the full-range-first behavior, multi-decade requests, seven current/retired meters and 1,497 **synthetic** observations in a single successful response, adaptive splitting of large histories, duplicate boundary readings, unresolvable days, and API error classification.

**Publication gate:** all required CI checks, then explicit permission to merge/publish, followed by user-controlled live preview against the vendor. Synthetic tests cannot verify the vendor's undocumented behavior.

---

# 0.2.0b13 — Candidate correction: adaptive historical preview and readable unit facts

**Draft only — no tag or release; no installation or changes to Home Assistant.**

- Recover long Trybatec history previews when an API index response fails with a data-format/size error by retrying smaller, overlapping periods. This directly targets the reported October 1–November 9 window failure (a 39-day request), while the November 1–9 request succeeds. The **92-day segmentation is not a proven vendor limit**.
- Keep history integrity strict: do not omit any date, silently accept partial data, overwrite the previous preview cache, or import Recorder rows when any subwindow is invalid. There is no fixed total-request ceiling; individual responses remain bounded, and requests are sequential and briefly spaced.
- When even a single day is invalid, report the exact failing date window and a fixed, nonsensitive error category. Never log vendor bodies, credentials or tokens.
- Remove the global 10-year and 45-window ceilings. Count actual attempted requests, including rejected larger windows, in `api_requests`. Dates must be valid, ordered and no later than today.
- In the unit options form, show the physical meter, chart reference unit, and explicit API unit on **three separate Markdown lines** with **bold values**. Escape portal-supplied meter labels so they remain literal text.
- Add automated regression tests for recoverable oversized windows, a persistently invalid day, retrieval spanning more than six years and seven physical meters with over 80 requests, absence of cache replacement on failure, and French/English formatted labels.

**Unverified until live testing:** whether October's real API response will become recoverable through subdivision, and the exact visual line-break rendering on a live French Home Assistant frontend.

No automatic history import, Recorder write, HACS install or publication is authorized by preparing this candidate. Merge is permitted only by the user's explicit instruction after full CI checks.

---

# 0.2.0b12 — Candidate corrective: default meter units and saved selections

**Draft candidate only; no tag or release, no merge, no changes to running Home Assistant.**

- The saved, user-confirmed unit of each physical meter (lot + fluid + serial) is the first choice when an options form is reopened, including retired meters found in the cached historical preview.
- If no unit was saved, propose an explicit valid API index unit, otherwise the configured portal chart display unit as the selected radio choice. Clicking **Save** confirms it as a manual choice; opening the form never writes any unit.
- Keep an explicit *Unknown* choice, strict allowed-unit validation, and existing safeguards against contradictory API index-unit evidence. Retain per-meter UUIDs and all other options.
- Remove misleading warnings and explain that the chart reference shown is configured rather than dynamically retrieved.
- Add focused tests for EF/ECS/CET, all saved per-meter selections, revisiting a form after a new options flow starts, and physically replaced meters.
- **Unrelated historical preview investigation:** a November 1–9, 2026 preview succeeded with one API window, whereas an October 1 start failed, also with one API window. The 92-day chunking cannot by itself explain the October failure. This candidate does not change historical fetching.

**Release gate:** all required CI controls followed by actual Home Assistant visual verification of radio defaults before approving a beta release.

---

# 0.2.0b11 — Corrective draft: restore direct, readable options navigation

**Not released. PR draft only; no change to a running Home Assistant installation.**

- Restore six direct principal destinations: Settings, Diagnostics, Meter units, History overview, Meter details and History review. Remove intermediate options menus introduced in b10 that produced blank entries in the real frontend.
- Select a meter and open its edit form directly; keep existing verified-unit persistence, UUID validation, logging options and safe historical writes.
- Keep mandatory explicit historical confirmation, without navigation-only commits or automatic Recorder imports.
- Test Home Assistant's real OptionsFlow manager and French/English backend translation loader, in addition to checking the shipped locale files and code-level menu names.
- **Publication is blocked until** the user validates the rendered menu and relevant screens on a real Home Assistant frontend. CI alone cannot establish this.

No actual Trybatec API, stored history, Energy settings, notifications, or HA configuration is modified by preparing this candidate.

---

# 0.2.0b10 — Saved-unit consistency and native one-click navigation

**Released experimental beta; user-reported UI regression.** Several menu entries appeared blank in the real Home Assistant frontend even though backend CI passed. This release must not be considered visually validated.

- Standardize all read-only navigation on Home Assistant native click-to-open menus with explicit links to the preceding level and to the main menu. Settings, diagnostics, meter selection and historical review have dedicated navigation menus.
- Remove the post-submit navigation radio field from editing and confirmation forms. Validate and save entered values before moving on; meter-unit changes return to the meter list by default. Selection radios remain only for actual data choices such as measurement units and source readings.
- Before an historical decision is persisted, provide a separate one-click navigation menu for approval, safe return to the previous step, or exit without saving. The final confirmation checkbox and out-of-period approval remain mandatory.
- Document the menu-versus-form UI contract for future screens in `docs/OPTIONS_UI_CONVENTIONS.md`.
- Recompute each meter's displayed verified unit from the current persisted options. List labels put the real status first (manual/API confirmation or needs confirmation), instead of relying on a stale coordinator snapshot.
- Choose units and meter/reading lists with explicit Home Assistant `SelectSelector(mode=list)`, which renders radio buttons even for more than five options. Keep selections separate from post-save navigation.
- On editable forms, validate and save the chosen unit/UUID, logging threshold or settings before returning to the main menu or meter list. Invalid inputs never navigate as if the save succeeded.
- On read-only menus and the historical review decision menu, use native one-click Home Assistant menu entries without an extra radio-button selection and Submit. Never record a historical decision until the separate explicit confirmation (and any required out-of-period confirmation).
- Preserve historical correction draft fields when navigating back; navigation to the main menu after an approved decision saves first, then returns.
- Replace the generic Developer Tools link with Home Assistant's official preselected action redirect for `trybatec.preview_history`. Opening the link does not execute the action.
- Add pure and actual Home Assistant options-manager tests for saved options, safe navigation, radio selectors, and published translations.

No API polling, Recorder statistical import, Energy dashboard modification or external notification is triggered by navigation.

---

# 0.2.0b9 — Historical menu recovery, explicit unit provenance and diagnostics

**Experimental prerelease candidate.** Never automatically import real Recorder statistics or alter the Energy dashboard; approval for a future b9 GitHub release and a real Home Assistant installation remains a separate control.

## Changes
- Fix a Home Assistant flow-manager UnknownStep regression: all three historical no-preview/unavailable/empty menus now have actual handler methods, so they remain navigable instead of returning a bare error. The action and log links remain instance-relative and clickable.
- Replace escaped literal line breaks in translated historical recovery messages with real paragraphs.
- Preserve a previously confirmed meter unit when consistent with the API; otherwise preselect a clearly detected explicit API index unit. A chart display-unit reference is never auto-confirmed. A conflict or unrecognized API unit remains unverified.
- Clearly label the unit's origin (manual confirmation / explicit API detection / chart-only suggestion); provide revised French and English guidance for the optional device UUID and the unverified unit.
- Add **Configure → Diagnostics and logging** with ERROR / WARNING (default) / INFO / DEBUG. This is a shared Trybatec logger threshold on the Home Assistant instance, and is applied without reloading the integration when that is the only option changed.
- Add sanitized INFO/DEBUG diagnostics identifying portal fetch stage, elapsed time and number of meters, without response bodies, usernames, raw readings or tokens.
- Regression tests for Home Assistant's actual options-flow manager, blank-menu recovery navigation, API-first defaults, and logging option updates.

**Validation boundary:** Tests use simulated Home Assistant and invented meter data; real Trybatec API failures and future self-updating in the user's Home Assistant are not confirmed by CI.

---

# 0.2.0b8 — Unit confirmation recovery and actionable history review

**Experimental prerelease.** This update does not authorize historical Recorder imports or modification of Energy configuration.

## Fixes
- Confirming a unit for a physical meter now updates the active coordinator from the last successful bounded index response, without unloading the entire integration or sending another portal request. Saves with an unchanged/empty optional device UUID mapping no longer force reloads. A new verified meter entity is registered with its distinct stable identifier; the prior unverified entity stays without a usable index, avoiding accidental statistic reuse or double counting.
- Malformed previously saved unit overrides no longer prevent live meter polling: invalid overrides are ignored safely, with an error log and unverified index units.
- A failed initial portal fetch remains a retryable setup failure, rather than silently accepting unverified data. The sanitized exception category is logged without vendor payloads or credentials.
- Historical-review navigation no longer terminates in a bare error dialog when the integration is unavailable, the preview is missing after a restart, or the selection has expired. Each state has a clear explanation, a return-to-menu option and direct in-app links to Developer Tools → Actions and/or Trybatec logs.
- An actual preview with no flagged readings is explicitly distinguished from a missing preview; persisted review decisions remain unchanged.
- Annual monetary estimates no longer declare the unsupported Home Assistant MEASUREMENT state class; entity IDs remain unchanged.
- Additional synthetic Home Assistant runtime and UI regression tests cover options-save lifecycle, restart with confirmed units, invalid existing overrides and navigation.

**Limits:** The underlying cause of the user's live Trybatec API failure has not been confirmed without HA traceback. Vendor API connectivity and response format remain outside CI coverage. No real vendor data or production Recorder is used in these tests.

---

# 0.2.0b7 — Historical diagnostics, cost estimates and import safeguards

**Experimental pre-release.**
Publication of this beta does not approve production historical import, change Energy settings or modify any Home Assistant installation.

### Changes from b6

- Read-only diagnostics for sparse intervals, declining/conflicting indexes,
  overlapping or replaced physical meters, and unverified source units.
- Read-only annual historical cost estimates in EUR with physical-meter
  isolation and separate, explicitly authorized accounting allocations.
- Explicit water index conversion (L and m³ to m³), thermal conversion
  (kWh, MWh and GJ to kWh), and refusal of missing, conflicting or incompatible
  source units. Chart display units do not certify raw meter index units.
- Fix annual energy/water YTD estimate sensor state classes: no misleading
  `measurement` statistics for annually resetting or revisable estimates.
- Protect `retry_pending`: immutable source and approved plan fingerprints
  prevent requeueing if the vendor supplies changed source readings or
  import parameters. Unfingerprinted pre-existing pending entries require
  verification rather than blind retry.
- Harden Recorder readback: mismatched, missing and ambiguous duplicate
  hourly buckets cannot be marked verified. An import returns a pending state
  until explicit `verify_history` confirms every expected statistic.
- Expanded synthetic unit, Recorder SQLite, HA process-restart and
  multi-meter interruption tests. No test interacts with a real vendor account.

### Migration / cautions

- Back up Home Assistant configuration, Recorder and `.storage` before any
  attempted import; verify access to restoration material and keys.
- Existing b5/b6 statistics are not deleted or migrated automatically.
  Do not use two generations of the same usage simultaneously in Energy.
- Confirm each real meter's index unit and review each abnormal historical
  reading before accepting an import. Manual confirmation is required.
- Simulated failure tests do not establish transaction-level crash recovery
  inside the Recorder SQLite thread. Costs remain estimates rather than
  approved building charges.
- Publication requires explicit authorization and passing all release gates.

---

# 0.2.0b6 — Per-meter units, Recorder verification and historical preflight

Experimental pre-release. Back up Home Assistant, including Recorder and .storage, before import.

- Explicit source units: recognize known unit fields if Trybatec returns them. No assumption that those fields actually exist on every account. If absent, require a manual unit per physical meter (also for old meters visible in the history preview).
- Water: m³ or L → m³. Thermal: kWh, MWh or GJ → kWh. Incompatible and conflicting units remain unavailable; old global heating-unit setting is no longer used.
- Separate b6 meter entity IDs and history_v5 statistic IDs; no automatic migration, deletion or Energy dashboard switching. Do not select multiple generations of the same usage in Energy.
- Import stages a pending journal before Recorder queueing, blocks blind reimports and provides administrator action trybatec.verify_history. It checks every expected hourly bucket and sum against recorder.get_statistics. This verification is a separate step after Recorder processes the queue; import is not atomic.
- Added per-meter unit UI and graphical read-only history overview. Displays possible replacements and overlaps without merging different physical meter histories.
- Improved test coverage for missing/conflicting units, multiple lots, pending journals and recorder bucket verification.

Remaining limits: no evidence that the undocumented Trybatec API exposes unit metadata, no full-page bulk review editor, no automated Energy dashboard migration, no production proof across multiple Trybatec accounts. Installing or updating never automatically writes historical statistics.

## Fix included in b7: Home Assistant annual sensor state classes

- Corrects the runtime warning: annual estimated cold/hot-water usage had device class `water` and heating usage had `energy`, but all three incorrectly used `state_class: measurement`.
- YTD estimated usage now declares no state class: a revision or calendar-year reset must not be misinterpreted as a continuous meter statistic.
- Verified physical meter index sensors continue to use `total_increasing`. Existing entity IDs and Recorder history are not rewritten by this fix.
