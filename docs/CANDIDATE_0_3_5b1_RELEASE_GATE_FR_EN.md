# 🤖 0.3.5b1 — Dossier de candidate et tri du backlog / Candidate gate and backlog triage

> **FR : document de préparation, PAS des notes de publication définitives.** **EN: preparation draft, NOT final published release notes.**
>
> Relevé GitHub lors de la création : #164 HEAD `57fc7563fe577e40919fb00e3c467495d5b189af` au début de l'inventaire ; vérifier le HEAD et les CI exacts après ajout du présent fichier. Base publiée `main` : `8d621da9703b40662800b4a7c286707e8a7f895f`, manifeste `0.3.4b1`. **Version visée : `0.3.5b1`, non certifiée et non incrémentée.**
>
> Code/doc publiques uniquement ; aucune donnée réelle d'installation, de logement, d'historique ou de compte fournisseur.


## 🤖 Nouvelle preuve L7 isolée / New isolated L7 evidence — 14/11/2026

**FR :** après la première mise à jour bornée ci-dessous, #158 a qualifié avec **vrai** HA Core 2026.11.0 : archive native localisée, lecture/décryptabilité appropriée aux archives non chiffrées, restauration hors ligne dans une cible CI distincte, transaction additive L7 avec journal et réécriture Energy réelles, rollback après échec injecté, crash après persistance et relecture du journal, refus d'une archive corrompue et préservation des modifications tierces. [CI #158 SHA exact](https://github.com/christophejaubert/ha-trybatec/actions/runs/43578096175), 231 tests d'intégration réussis et 2 ignorés. #164 a intégré ces modules/tests ; la CI sur son SHA final reste obligatoire. Les preuves de sélection L6 **dans le test transactionnel** sont fictives, même si le collecteur natif L6 fait l'objet d'autres essais SQLite positifs. La confirmation WebSocket/écriture réelle L7 reste **désactivée**. Aucune restauration ou écriture sur l'installation utilisateur.

**EN:** The earlier bounded-contract note below predates new native L7 isolation evidence. Real HA Core 2026.11.0 backup/archive, separate-target startup restoration, additive Energy transaction, persistent journal, rollback, cancellation, external writer conflict and corrupted archive refusal are exercised with synthetic L6 **inputs**. #158 [exact SHA CI](https://github.com/christophejaubert/ha-trybatec/actions/runs/43578096175) passed 231 isolated HA integration tests (2 skipped). #164 integrated the owner changes. This is NOT native full selected Recorder-to-L7 E2E qualification nor a production restart or authorization. Production write route remains hard-disabled. Recheck #164 exact final SHA CI.

## 🤖 Mise à jour bornée / Bounded update — 14/11/2026

**FR :** le contrat autorisé porte désormais sur les seules écritures Trybatec. Le chemin natif mesuré Recorder → filiation → admission L6 est testé avec SQLite/Store HA réels et données fictives, sans remplacer les producteurs de preuves. Le journal traite concurrence, interruption et dérive tardive sans réparation destructive. Voir [garanties et limites actuelles](CONVERGENCE_CURRENT_FR_EN.md). La transaction L7 positive, sauvegarde/restauration et reprise natives restent à qualifier ; aucune activation réelle ni publication. Les références antérieures ci-dessous décrivent les étapes historiques et ne rétablissent pas une exigence d'exclusion universelle des writers externes.

**EN:** the authorized contract now covers Trybatec-controlled writes only. Actual isolated HA SQLite/Store and synthetic inputs exercise measured Recorder → physical lineage → positive L6 with real proof producers, plus concurrency, interruption and late-drift quarantine without destructive repair. [Current guarantees and limits](CONVERGENCE_CURRENT_FR_EN.md). Native positive L7, backup/restore and recovery remain unqualified; no real activation or release. Earlier references below are historical, not a renewed universal external-writer exclusion requirement.

## FR — Périmètre de la candidate (projet de notes de release)

- **Développé / intégré dans #164 :** panneau C1–C11 et mutualisation de découverte historique par compte ; options de tarifs et cohérence visuelle FR/EN ; identité des compteurs et filiation physique ; journal Recorder, contrôle de conservation par jour, SQLite HA isolé ; collecteur natif de sélections admin L6, relecture SQL, validation de propositions Énergie, WebSocket et moteur L7 isolé. Ces fonctionnalités ne sont pas toutes **utilisables en production** : distinguer code de fonction activée.
- **Fonctions proposées à la recette après opération autorisée :** panneau Trybatec, consultation et diagnostic de l'historique, configuration et édition des tarifs, audit d'identités. Le comportement sur HA installé et les parcours FR/EN, accessibilité, mobile et thème nécessitent leur propre recette, sans l'inférer de la CI.
- **Fonction volontairement indisponible :** écriture groupée de sources dans Énergie (L7). `NATIVE_ENERGY_BULK_WRITES_ENABLED_88=False`. L'API WebSocket de confirmation reste inactive ; aucune importation automatique Recorder/Énergie n'est autorisée.
- **L6 :** sélection et contrôles natifs disponibles en code. Les prévisualisations positives sont obtenues dans les tests avec témoins de filiation/immutabilité **fictifs**. Le producteur réel #36 ne garantit pas les écritures Recorder tardives et rend `independent_future_writer_exclusion_verified=False` et `selected_version_state=verified_scoped_observation_only`. #37/#88 refusent correctement de promouvoir ce reçu en admission L7.
- **L7 :** moteur transactionnel conçu avec sauvegarde, empreintes, journal durable, vérification, contrôles d'ajouts, rollback et relecture. Les tests positifs exécutent des ports/fixtures fictifs, **pas une transaction native positive HA isolée**. La garantie contre tous les écrivains Énergie externes et la restauration native sur environnement adapté ne sont pas qualifiées.
- **CET/chauffage :** ne pas prétendre qu'un traitement kWh permet automatiquement une catégorie chauffage valide dans Energy. La recette réelle du dashboard CET se déroule **après publication/installation distinctement autorisées**, pas comme prérequis artificiel avant bêta.
- **Sécurité :** aucun faux zéro pour journée absente ; aucune soustraction d'index entre compteurs physiques différents ; pas de revendication d'exhaustivité globale de l'historique fournisseur ; aucune révélation des données privées dans les preuves CI.
- **Candidat non prêt pour fusion/publication :** la validation fonctionnelle L7 positive et les garanties persistantes de non-concurrence manquent ; l'autorité reste à MOE 03 pour fusion, release, installation, migration, restauration et HA.

### Critères de qualification attendus (C1–C11 et chaîne native)

| Axe / Area | Contrôle exigé / Required evidence | Statut démontré / Verified level |
| --- | --- | --- |
| C1–C11 | FR/EN, clavier/lecteur d'écran, clair/sombre, desktop/mobile, scan/cache/erreurs | Harnais navigateur **synthétique** présent ; pas de recette HA réelle |
| Recorder #36 | Révisions/identités exactes, jours et sommes, relecture SQL, crash/retry, writer tardif | Vérifications SQLite isolées ; exclusivité future **non démontrée** |
| Filiation #37 | Compte/lot/fluide, génération physique, provenance, mêmes jours, source C11 | Tests natifs et physiques ; manque attestation forte sur échelle réelle |
| Admission L6 | Source serveur authentifiée, autorisations, alternatives, absence de doublons | Sélection native et contre-tests ; succès complet réel **bloqué par #36** |
| Transaction L7 | Prévisualisation, consentement, backup vérifié, verrou exclusif, rollback, idempotence | Ports fictifs testés ; route d'écriture native **désactivée** |
| Interruption/concurrence | Relecture après suspension, writer tardif, modifications tierces, journal ambigu | Contre-tests présents ; garanties universelles **non établies** |
| Confidentialité | Aucun secret ni donnée réelle dans les changements et traces | Tests/contrôles GitHub à vérifier au **SHA final** |
| Livraison | Tous checks obligatoires verts sur SHA final et revue fonctionnelle | **À recontrôler après dernier commit** ; jamais inférer d'un SHA parent |

### Références de code / Code references

- #159 (Recorder) `fb069ecba14941dc030799b8a6275ed03c61d243` : garde v2 conservative, conservation et durabilité.
- #160 (lineage) `783f7cc1332975d55d79fa2078777afa05b47777` : réconciliation physique, tests SQLite.
- #158 (Énergie) `fbf1775f4c89c9ab1719f7f2c82a469439207f46` : relecture native #36 désormais obligatoire, collecteur L6 et propositions Energy.
- #164 : `f3411648`, `7a0c8ebd`, `c7e50f7a` et tests supplémentaires de composition ; la CI doit être vérifiée sur le HEAD réel.

## EN — Draft release notes, not a release decision

This **unpublished candidate** assembles panel improvements C1–C11, shared history discovery and tariff editing, stable physical meter lineage, Recorder native attempt journal and isolated SQLite verification, authenticated read-only L6 selected collection, native Energy proposal validation and a guarded L7 transaction design. The positive selected L6 planner uses fictional attestations; actual #36 scoped v2 does **not** prove exclusion of delayed or foreign Recorder writers, and #37/#88 must deny any promotion to an immutable proof. **Native Energy enrollment remains disabled.** Existing interruption/concurrency/rollback/idempotence tests do not establish a successful real HA transaction, universal external-writer exclusion or a tested native restore. FR/EN, accessibility, privacy and all mandatory CI checks must be validated on the exact final integrated SHA. Real post-install CET Energy dashboard acceptance is separate. No merge, release, Home Assistant installation, backup, migration, import or restore is performed here.

## FR / EN — Réconciliation des 13 issues ouvertes / 13 open issues

Relevé de l'état GitHub, **pas une décision de clôture**. `Développé`, `testé`, `recetté`, `fusionné`, `publié`, `installé` sont des états séparés. Le tableau signale ce qui doit encore être vérifié ; aucune issue n'est déclarée résolue par la seule présence de code.

| Issue | Sujet / Subject | Résultat/limite du tri / Triage outcome |
| --- | --- | --- |
| [#34](https://github.com/christophejaubert/ha-trybatec/issues/34) | Évolution future : pondérer le lissage historique du chauffage par degrés-jours | Hors candidate : évolution degrés-jours future / Outside candidate: future degree-day weighting |
| [#35](https://github.com/christophejaubert/ha-trybatec/issues/35) | Simplifier l’installation Trybatec (login/mot de passe seuls), gérer la réauthentification et notifier les pertes d’accès | Présence de code et tests à vérifier sur SHA ; recette HA réelle non certifiée / Code and tests require exact-SHA and live-HA acceptance |
| [#36](https://github.com/christophejaubert/ha-trybatec/issues/36) | Évolution post-b14 — reconstitution et lissage des consommations, contrôle des index, révisions Recorder et basculement Énergie | Implémentation Recorder native + SQLite ; protection writers tardifs non démontrée / Native Recorder and SQLite, future-writer fence unproven |
| [#37](https://github.com/christophejaubert/ha-trybatec/issues/37) | [Spécification validée] Compteurs déposés, nettoyage des entités et continuité du tableau Énergie | Filiation physique par compteur et journée ; contrat conservateur si données manquantes / Physical lineage per meter and day; deny incomplete evidence |
| [#39](https://github.com/christophejaubert/ha-trybatec/issues/39) | Marketplace readiness — préparation exhaustive du référencement officiel HACS / Home Assistant | Préparation Marketplace ; référencement officiel non réalisé / Marketplace preparation; no official listing |
| [#42](https://github.com/christophejaubert/ha-trybatec/issues/42) | IHM — Saisie ergonomique des tarifs annuels par fluide (sans JSON) | Tarifs UX et natifs : présence candidate ; recette métier encore à vérifier / Tariff UX/native candidate, live acceptance pending |
| [#45](https://github.com/christophejaubert/ha-trybatec/issues/45) | 🤖 Préversion intégrée / Integrated prerelease (#45) | Pilotage de release et décisions MOE distinctes ; clôture interdite par CI seule / Release management remains separate from CI |
| [#70](https://github.com/christophejaubert/ha-trybatec/issues/70) | 🤖 design(ui): marque et accessibilité / Brand & a11y | Charte et accessibilité évaluées synthétiquement ; recette réelle à compléter / Synthetic brand and a11y, real acceptance pending |
| [#81](https://github.com/christophejaubert/ha-trybatec/issues/81) | 🤖 Identités stables / Stable IDs | Identités stables et migration : tests, pas de migration réelle autorisée / Stable IDs and migration, tests only |
| [#83](https://github.com/christophejaubert/ha-trybatec/issues/83) | 🤖 feat(ui): parcours guidés / Guided setup | Parcours guidés : tests synthétiques, recette HA réelle non attestée / Guided setup synthetic checks, live acceptance pending |
| [#84](https://github.com/christophejaubert/ha-trybatec/issues/84) | 🤖 feat(ui): détails compteurs / Meter details | Détails compteurs : tests synthétiques, recette HA réelle non attestée / Meter detail synthetic checks, live acceptance pending |
| [#88](https://github.com/christophejaubert/ha-trybatec/issues/88) | 🤖 feat(energy): ajout groupé / Bulk enrollment | Collecteur de sélection raccordé ; vraie transaction L7 non qualifiée / Native selected collector integrated, L7 real transaction blocked |
| [#155](https://github.com/christophejaubert/ha-trybatec/issues/155) | 🤖 Correctifs panneau et historique / Panel UX & global history scan | C1–C11 intégrés pour tests synthétiques ; recette HA réelle à confirmer / C1–C11 synthetically tested, live acceptance pending |

## FR / EN — Réconciliation des 42 PR ouvertes / 42 open PRs

Classification de **travail préparatoire**, fondée sur les sujets et les convergences connues ; **« historique » ne signifie pas doublon prouvé**. Une PR ne devient redondante qu'après comparaison de son arbre/blobs avec #164 et `main`, audit des assertions/CI et conservation de preuves dans #45. Aucun regroupement ci-dessous n'autorise une clôture.

| Groupe / Group | PR à conserver ou examiner / PRs for review | Nombre / Count |
| --- | --- | --- |
| Candidate / propriétaire / owner | [#158](https://github.com/christophejaubert/ha-trybatec/pull/158), [#159](https://github.com/christophejaubert/ha-trybatec/pull/159), [#160](https://github.com/christophejaubert/ha-trybatec/pull/160), [#164](https://github.com/christophejaubert/ha-trybatec/pull/164) | 4 |
| Chantiers actuels distincts / separate current work | [#156](https://github.com/christophejaubert/ha-trybatec/pull/156), [#162](https://github.com/christophejaubert/ha-trybatec/pull/162), [#163](https://github.com/christophejaubert/ha-trybatec/pull/163) | 3 |
| Recettes / pilotage / contrôles indépendants | [#157](https://github.com/christophejaubert/ha-trybatec/pull/157), [#161](https://github.com/christophejaubert/ha-trybatec/pull/161), [#165](https://github.com/christophejaubert/ha-trybatec/pull/165), [#166](https://github.com/christophejaubert/ha-trybatec/pull/166), [#167](https://github.com/christophejaubert/ha-trybatec/pull/167) | 5 |
| Historiques fonctionnels à rapprocher / historical functional candidates | [#82](https://github.com/christophejaubert/ha-trybatec/pull/82), [#118](https://github.com/christophejaubert/ha-trybatec/pull/118), [#120](https://github.com/christophejaubert/ha-trybatec/pull/120), [#125](https://github.com/christophejaubert/ha-trybatec/pull/125), [#127](https://github.com/christophejaubert/ha-trybatec/pull/127), [#128](https://github.com/christophejaubert/ha-trybatec/pull/128), [#129](https://github.com/christophejaubert/ha-trybatec/pull/129), [#130](https://github.com/christophejaubert/ha-trybatec/pull/130), [#136](https://github.com/christophejaubert/ha-trybatec/pull/136), [#139](https://github.com/christophejaubert/ha-trybatec/pull/139), [#145](https://github.com/christophejaubert/ha-trybatec/pull/145), [#149](https://github.com/christophejaubert/ha-trybatec/pull/149), [#150](https://github.com/christophejaubert/ha-trybatec/pull/150), [#151](https://github.com/christophejaubert/ha-trybatec/pull/151), [#153](https://github.com/christophejaubert/ha-trybatec/pull/153) | 15 |
| Historiques IHM / historical UX candidates | [#131](https://github.com/christophejaubert/ha-trybatec/pull/131), [#132](https://github.com/christophejaubert/ha-trybatec/pull/132), [#133](https://github.com/christophejaubert/ha-trybatec/pull/133), [#138](https://github.com/christophejaubert/ha-trybatec/pull/138), [#140](https://github.com/christophejaubert/ha-trybatec/pull/140), [#142](https://github.com/christophejaubert/ha-trybatec/pull/142), [#144](https://github.com/christophejaubert/ha-trybatec/pull/144), [#146](https://github.com/christophejaubert/ha-trybatec/pull/146), [#154](https://github.com/christophejaubert/ha-trybatec/pull/154) | 9 |
| Historiques CI / synthèses / historical CI and proof candidates | [#124](https://github.com/christophejaubert/ha-trybatec/pull/124), [#126](https://github.com/christophejaubert/ha-trybatec/pull/126), [#134](https://github.com/christophejaubert/ha-trybatec/pull/134), [#137](https://github.com/christophejaubert/ha-trybatec/pull/137), [#143](https://github.com/christophejaubert/ha-trybatec/pull/143), [#152](https://github.com/christophejaubert/ha-trybatec/pull/152) | 6 |

**Contrôle de complétude / Completeness:** 13 issues, 42 PRs dans l'inventaire courant ; 0 PR non classées (aucune / none). Les 42 PR restent ouvertes tant que MOE n'a pas rapproché individuellement leurs commits et preuves et pris les décisions de clôture autorisées.

### Procédure de réconciliation / Reconciliation rules

1. **FR :** pour chaque PR historique, vérifier HEAD et CI, différences de blobs/arbres par chemin et preuves uniques par rapport au HEAD #164 / `main` ; ne pas rejouer les commits empilés. **EN:** compare current heads, exact blobs, and unique proofs; never replay stacked changes blindly.
2. **FR :** si tout est intégré, noter dans #45 et fermer seulement avec décision MOE ; si un test/contrat reste utile, le transférer ou laisser la PR ouverte. **EN:** only close after preserving evidence and an authorized MOE decision; unresolved work stays open.
3. **FR :** pour les issues, conditionner la clôture à la recette métier requise et aux opérations de release/install nécessaires ; la CI verte seule ne suffit jamais. **EN:** close issues only on their acceptance criteria, not on green CI alone.
4. **FR :** aucune écriture publique de données réelles, journaux bruts, identifiants de logement, données de consommation ou secrets. **EN:** no real customer, home or consumption data, logs or secrets in public artifacts.

**Décision demandée à MOE 03 / MOE 03 release gate:** candidate à considérer **incomplète** tant que les garanties Recorder/Énergie et le scénario positif L7 natif isolé ne sont pas démontrés ; ne pas mettre le manifeste à `0.3.5b1` pour donner l'apparence d'une qualification acquise.
