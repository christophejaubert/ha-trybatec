# 🤖 Pilotage MOE / MOE release tracking


## ÉTAT COURANT — 13 novembre 2026 / CURRENT VERIFIED STATUS — 13 November 2026

> **FR — Priorité de lecture :** ce relevé GitHub daté fait foi pour le statut courant constaté. Toutes les sections du 12 novembre plus bas sont **des preuves historiques conservées**, y compris lorsqu'elles disent que la bêta n'était pas publiée. Les décisions détaillées restent dans les issues fonctionnelles.
>
> **EN — Read first:** this dated GitHub snapshot supersedes earlier status summaries. The 12 November sections below are **preserved historical evidence**, including their now-outdated unreleased-beta statements. Functional issues remain authoritative for accepted requirements.

### Publication, SHA et CI / Release, SHA and CI

| Élément / Item | Fait vérifié / Verified fact |
| --- | --- |
| Main protégé / Protected main | [main](https://github.com/christophejaubert/ha-trybatec/tree/main) — SHA **8d621da9703b40662800b4a7c286707e8a7f895f** |
| Tag et release / Tag and release | [0.3.4b1](https://github.com/christophejaubert/ha-trybatec/releases/tag/0.3.4b1) **publiée / published**, prerelease=true, 2026-11-13 08:53:01 UTC ; tag = main = SHA précité |
| Notes / Notes | FR/EN présentes ; mention des limites Recorder #36, filiation #37 et Énergie #88, et de la recette réelle ultérieure |
| Post-merge tests | [CI sur main #43396107451](https://github.com/christophejaubert/ha-trybatec/actions/runs/43396107451) **success** ; tests Python 3.13/3.14, Ruff, HACS, Hassfest, HA isolé, Recorder, persistance et Gitleaks réussis ; préparation de brouillon de release ignorée (facultative) |
| Contrôles liés / Other workflows | [CodeQL #43396107132](https://github.com/christophejaubert/ha-trybatec/actions/runs/43396107132), [navigateur #43396107511](https://github.com/christophejaubert/ha-trybatec/actions/runs/43396107511), [accessibilité #43396107561](https://github.com/christophejaubert/ha-trybatec/actions/runs/43396107561), [supply-chain #43396107546](https://github.com/christophejaubert/ha-trybatec/actions/runs/43396107546) : success, **même SHA** |
| Publication automatisée contrôlée / Authorized publisher | [workflow manuel #43396699868](https://github.com/christophejaubert/ha-trybatec/actions/runs/43396699868), success, **même SHA**, publication par déclenchement explicite |
| Total des checks visibles / Visible checks | **23 checks : 22 success, 1 skipped facultatif** en incluant l'étape de publication ; ne pas compter skipped comme un succès |
| Installation et recette / Deployment and acceptance | L'issue #155 relate une installation servant aux retours d'interface, **mais l'état HA actuel et une recette exhaustive ne sont pas vérifiés ici**. GitHub prouve fusion/publication, pas installation ou validation production |

**FR.** La version expérimentale est publiée, non pleinement opérationnelle pour reprise sélective Recorder et ajout groupé Énergie. La chronologie validée pour une prochaine bêta **testable** est : développement fonctionnel sécurisé → qualification synthétique + CI sur SHA exact → fusion autorisée → release autorisée → installation HA autorisée → recette réelle avec autorisation distincte de toute écriture ou restauration. Ne pas exiger une recette sur production avant la publication de la bêta nécessaire à cette recette.

**EN.** The experimental beta is published, but selective Recorder retry and bulk Energy writes are not fully usable. Approved sequence for the next testable beta: safely complete implementation → independent synthetic tests and exact-SHA CI → separately authorized merge → release → HA installation → production acceptance with separate write/restore permissions. Live acceptance is not a prerequisite for first publishing the beta that enables it.

### Décision business owner confirmée / Reconfirmed business owner decision (13/11/2026)

**FR — Règle non validée retirée.** Toute formulation, y compris dans les anciens instantanés conservés plus bas, imposant une « recette réelle puis publication » est **caduque et ne doit plus servir de critère de livraison**. **Séquence obligatoire :** développement complet et garanties de sûreté préparées → CI/tests synthétiques sur SHA exact → fusion expressément autorisée → **publication bêta expressément autorisée** → inventaire/sauvegarde/installations autorisés sur HA de production → **recette réelle après installation** → décisions et correctifs éventuels. La publication ne constitue ni recette ni autorisation d'écriture. Aucun périmètre métier D3 n'est réduit et les verrous #36/#37/#88 demeurent en place tant que leurs conditions de sûreté ne sont pas démontrées. Le protocole applicable est [PRODUCTION_ACCEPTANCE_0.3.4b1_FR_EN.md](PRODUCTION_ACCEPTANCE_0.3.4b1_FR_EN.md), corrigé sur la présente branche MOE #161. Les décisions existantes dans [#45](https://github.com/christophejaubert/ha-trybatec/issues/45) sont cohérentes avec cet ordre ; aucune décision de fusion, release, installation ou écriture n'est conférée par cette correction documentaire.

**EN — Unapproved rule removed.** Any preserved older wording requiring **live acceptance before beta publication** is superseded and NOT a delivery gate. Mandatory order: complete safe development → exact-SHA CI/synthetic tests → separately authorized merge → **separately authorized beta publication** → production inventory/backup/installation under distinct approvals → **live acceptance after installation** → business decision and possible fixes. Publication is neither acceptance nor permission to write. The approved D3 scope is unchanged; #36/#37/#88 fail-closed guards remain until safety prerequisites are met. See the corrected [production acceptance protocol](PRODUCTION_ACCEPTANCE_0.3.4b1_FR_EN.md) on MOE draft #161. No merge, release, HA installation or mutation is approved by this documentation update.


### Décisions fonctionnelles, écarts et qualification / Decisions, functional gaps and qualification

| Issue | Acquis / Approved scope | Preuve et blocages actuels / Evidence and blockers |
| --- | --- | --- |
| [#155](https://github.com/christophejaubert/ha-trybatec/issues/155) | **C1–C11 tous validés** ; spécifications FR/EN et tests négatifs dans l'issue / all requirements approved | [PR #156](https://github.com/christophejaubert/ha-trybatec/pull/156) brouillon : code et tests en progression, **CI de sa nouvelle tête en cours à 11:38 UTC (tests Python réussis, confidentialité encore en cours)**, C11 distinct, aucune recette C1–C11 exhaustive |
| [#36](https://github.com/christophejaubert/ha-trybatec/issues/36) | Index sources intacts, provenance, lissage résiduel linéaire, révisions Vn Recorder, sélection Énergie unique / immutable readings, traceable smoothing and versions | Contrats et protections fail-closed présents ; **preuve indépendante d'absence d'écrivain Recorder tardif ou concurrent manquante**, reprise sélective verrouillée, reprise/versions/persistance et non-doublons à qualifier |
| [#37](https://github.com/christophejaubert/ha-trybatec/issues/37) | Identités des **compteurs physiques** distinctes des entités HA ; générations actives/déposées et continuité / physical generations and HA entities separated | Filiation partielle ; exhaustivité des générations/observations, transitions, attribution des jours et continuité historique dans Énergie non démontrées ; pas de nettoyage destructeur |
| [#88](https://github.com/christophejaubert/ha-trybatec/issues/88) | Ajout groupé unique avec aperçu/confirmation, eau froide/chaude et chauffage compatible, conservation autres sources, coûts facultatifs / guarded bulk enrollment | Contrats de lecture seule et composants L7 présents mais **L6 ne fournit pas d'admission positive, port L7 non raccordé et UI administrateur non opérationnelle**. Pas d'ajout réel ni rollback production attesté |
| [#39](https://github.com/christophejaubert/ha-trybatec/issues/39) | Marketplace/HACS après stabilisation / stable-version marketplace preparation | Préparation ouverte, aucun référencement soumis/autorisé ; critères officiels à revérifier lors de la candidature |
| [#45](https://github.com/christophejaubert/ha-trybatec/issues/45) | Mandat MOE et arbitrages validés / project decisions | Référencer les preuves sans confondre les étapes ni clôturer automatiquement les issues |

**C1–C11, synthèse des décisions validées (issue #155 fait foi) :** C1 : 0 indisponible vérifié = succès, positif = alerte, inconnu = indéterminé ; C2 : une recherche historique **globale par compte**, bornée, explicitement montrée ; C3 : fiche du compteur sélectionné immédiatement visible ; C4 : messages utilisateur débarrassés des affirmations inutiles « inventé/fictif » sans perdre la provenance ; C5 : actions nécessaires mises en valeur **à l'aide des commandes existantes, sans nouvel encart redondant** ; C6 : indications pertinentes pour déposés sans faux défaut d'index courant ; C7 : supprimer les liens vers l'ancienne IHM sans supprimer les fonctions ; C8 : pictos et couleurs par fluide cohérents ; C9 : dates par premières/dernières **observations connues** du compte ou compteur, raisons dynamiques affichées, choix personnalisés préservés, jamais de borne arbitraire ; C10 : origine des intervalles **indéterminée par défaut**, texte d'aide compréhensible ; C11 : réutiliser la découverte globale entre inventaire/historique/tarifs, diagnostiquer échecs expurgés et reprises contrôlées, saisie manuelle des tarifs toujours possible. Aucun scan lourd automatique ni écriture implicite.

**EN — Approved C1–C11 summary (see #155 for exact wording):** C1 verified zero/positive/unknown semantics; C2 explicit bounded account-wide history scan; C3 immediate selected-meter detail; C4 actionable user texts preserving provenance; C5 reuse existing buttons for action states; C6 meaningful retired-meter controls; C7 remove all legacy UI links; C8 consistent fluid visuals; C9 evidence-based account/meter bounds with rationale, retained custom dates; C10 unknown origin default; C11 cached shared historical discovery with safe diagnostic/retry and tariff editing even after errors. No implicit writes, expensive automatic scans or widened resource budget.

### CI sur SHA exact / Exact-head qualification

| Cible / Target | SHA vérifié / Verified SHA | Résultat exact / Exact result |
| --- | --- | --- |
| main, release 0.3.4b1 | **8d621da9703b40662800b4a7c286707e8a7f895f** | Workflows CI post-fusion et release réussis, **pas de recette réelle exhaustive** / successful automated workflows, no full live acceptance |
| [PR #156](https://github.com/christophejaubert/ha-trybatec/pull/156) | **48a5c5839095b5b0957af88bf135e7e05853ae52** (instantané 13/11, 11:38 UTC) | **CI non encore terminée** : tests Python 3.13/3.14, navigateur et accessibilité synthétiques, CodeQL, Gitleaks, intégrité et un contrôle confidentialité réussis ; une autre exécution confidentialité encore in_progress ; 1 préparation manuelle skipped. Aucune validation intégrale C1–C11 ni recette réelle déduite. |
| [#149](https://github.com/christophejaubert/ha-trybatec/pull/149) #36 | 461a1e9c7b546c07c6989cd1a1f2c27092c42ccb | Ancienne branche brouillon, succès/échec historiques non transférables à une nouvelle composition / historic draft, no inherited qualification |
| [#150](https://github.com/christophejaubert/ha-trybatec/pull/150) #37 | 400dab811544d561b5bc7a63fa6462d78c5fe9c7 | Idem / same |
| [#151](https://github.com/christophejaubert/ha-trybatec/pull/151) #88 | e50e7c7c07282e34fe58d8d59bfed731fa3837d5 | Idem / same |
| [#153](https://github.com/christophejaubert/ha-trybatec/pull/153) convergence | daab196ce4f67b1ed73f1623dc385c5d405a101f | Ancienne preuve de lecture seule, pas d'activation / historical readonly proof |
| [#154](https://github.com/christophejaubert/ha-trybatec/pull/154) convergence CI | 2dbea9e5ad92d464123a7d8eb00781696407fed1 | **PR de preuve historique — NE PAS FUSIONNER / proof-only DO NOT MERGE** |

**Historique du contrôle / Superseded observation :** SHA 4e6d863e989039a3a7a45a99a94678e139556def avait deux tests Python en échec ; le SHA 48a5c5839095b5b0957af88bf135e7e05853ae52 les a corrigés, mais une autre exécution était encore en cours à 11:38 UTC. Les résultats d'un SHA ne se transfèrent jamais à l'autre. / Earlier Python failures on 4e6d are superseded by successful Python checks on 48a5; exact-head CI must still complete.

**FR/EN :** toujours relire les têtes et checks exacts avant décision, particulièrement #156 qui évolue rapidement / recheck exact heads and checks before decisions, especially rapidly changing #156. Un test vert ne certifie ni les onze critères ni une recette réelle ; skipped ≠ passed / green automation is not full business acceptance.

### Matrice des branches et fichiers communs / Branch and shared-file matrix

| Chantier / Stream | PR et situation / PR and status | Fichiers à coordonner / Shared paths |
| --- | --- | --- |
| #36 Historique / History | #127, #128, #149, acquis déjà fusionnés dans main à comparer / compare with integrated main | history_recorder_*, history_coverage_l2.py, history_recorder_handoff_36.py, panel_history*.py, panel_api.py |
| #37 Compteurs / Lineage | #125, #150, #153, main | meter_lineage_37.py, lineage_history_bridge_37.py, lineage_energy_handoff_37.py, meter_identity.py, sensor.py |
| #88 Énergie / Energy | #129, #130, #151, #153, main | energy_bulk_*, panel_api.py, panel/trybatec-panel.js et contrats Recorder/lineage |
| #155 Interface | #156 ; historiques #133/#138/#144 | panel/trybatec-panel.js, panel_history.py, panel_history_jobs.py, panel_tariff_years.py, strings.json, translations/fr.json, translations/en.json, tests de navigateur |
| CI/CD sécurité / Security | #124, #140, #152, preuve #154 | .github/workflows/*, .github/ci/*, .gitleaksignore, scripts/public_privacy_preflight.py — **hors mandat MOE** |
| MOE documentaire | [ancienne PR #134](https://github.com/christophejaubert/ha-trybatec/pull/134) et présente branche doc / former draft and current documentation branch | **docs/MOE_RELEASE_TRACKING.md seulement** ; aucune reprise automatique de #134 |

**FR.** Les PR historiques #149–#153 ont des diffs volumineux contre main contenant potentiellement des acquis déjà fusionnés. Leurs listes de chemins **ne sont pas** un backlog résiduel. Rechercher précisément les différences de blobs, les conflits et les dépendances : ne ni fusionner ni rejouer en bloc les anciennes PR de preuve #145/#146/#154. Au point de contrôle : **31 PR ouvertes en brouillon et 13 issues ouvertes**, ce qui ne représente pas 31 chantiers distincts. La PR #134 touche également le document MOE : cette branche nouvelle est volontairement indépendante et basée sur main publié.

**EN.** Historical stacked PR diffs may contain code already merged into published main; file lists alone do not identify remaining work. Compare exact blobs and conflicts, do not replay proof PRs or automatically merge the old MOE draft #134. 31 open drafts and 13 open issues were observed, not 31 distinct pending features. This branch starts from published main and owns only this MOE document.

### Propriétaires, prérequis et décision candidate / Ownership, gates and candidate decision

| Responsable / Owner | Livrable probant / Required evidence |
| --- | --- |
| Conversation UI #155 / PR #156 | C1–C10 : contrôles état/actions, fiches, dates, origine, FR/EN, mobile/bureau, clair/sombre, clavier/a11y et **CI finale verte sur dernier SHA** |
| Conversation scan historique & tarifs C11 | Une recherche sûre et mutualisée compte entier ; cache, couverture complète/partielle, progression, reprise prouvée ou nouveau départ déclaré, erreurs catégorisées expurgées ; tarifs toujours éditables |
| Conversation recette indépendante C1–C11 | Matrice par critère, cas négatifs, 7 vues Playwright, tests UI/Recorder/Énergie croisés ; aucune confusion avec recette réelle |
| Conversation #36 | Relevés/provenance/versionnement, contrôles Recorder et **preuve externe indépendante contre écrivains tardifs** avant reprise sélective |
| Conversation #37 | Exhaustivité physique/générations, index datés, continuité de consommation sans double comptage, identités #81 et statut des déposés |
| Conversation #88 | L6 **admissibilité positive** fondée sur identité, unité, continuité, couverture, Recorder, provenance, concurrence ; L7 bouton admin et transaction de bout en bout, sauvegarde, empreinte, relecture et rollback sûrs |
| Conversation CI/CD | Protection main et checks requis, Gitleaks nouveaux commits + historique, preflight confidentialité, intégrité, qualification synthétique sur SHA candidat ; aucun affaiblissement |
| MOE #45 | Réconcilier liens/SHAs/risques, cadrer la décision de livraison sans prendre la décision utilisateur |

**Grille préalable FR :** vérifier le périmètre complet et réellement fonctionnel de la candidate ; obtenir la **décision utilisateur sur la version et le contenu exact** (aucune date/version/amputation fixée ici) ; démontrer les garde-fous, tests de pannes et critères métiers, y compris l'opérationnalité L6/L7/Recorder ; résoudre chevauchements et conflits avec main, sans duplication de commits ; réunir **tous les checks obligatoires réussis sur le SHA final** et un contrôle confidentialité fiable ; documenter limites, risques, notes FR/EN, plan d'installation et protocole de recette. Ne pas imposer de recette HA préalable chronologiquement impossible pour la première bêta testable. Soumettre ensuite des **autorisations distinctes** : fusion, release, installation, écritures Recorder/Énergie, sauvegarde/restauration, migration. Aucun changement HA, automatisme de fusion/publication ou modification de code n'est autorisé par cette réconciliation.

**EN delivery grid:** Confirm user-approved exact version and candidate scope without unilateral cuts or dates; qualify fully testable guarded features and negative incident tests; reconcile each specialist diff against published main; obtain every mandatory check and privacy proof on the **final SHA**, and prepare bilingual notes, risk/limitation matrix, installation and live acceptance plan. Live HA acceptance follows approved publication and installation of a testable beta. Merge, release, HA deployment, Recorder/Energy writes, backups, restore and migrations are **independent authorizations**.

---

### ARCHIVES : instantanés historiques conservés / ARCHIVED historical snapshots retained

Les paragraphes suivants sont conservés pour la preuve et la chronologie. Ils ne décrivent pas la tête actuelle de main ni le statut de publication. / The following text remains as historical evidence; its prior SHA and release-state statements are not current.

## Réconciliation — 12 novembre 2026 / Reconciliation — 12 November 2026

**FR.** Cible unique `0.3.4b1`, non autorisée à être fusionnée, publiée ou installée. **`main`** : `a1bd6d8558c8fe1cc13cadeb1ff4aaa20528dc53`. Dernière release : `0.3.3b1`. À cette vérification : **24 PR ouvertes en brouillon**, **12 issues ouvertes**. Les SHA ci-dessous sont ceux des branches individuelles et non d'une candidate complète. L'issue [#45](https://github.com/christophejaubert/ha-trybatec/issues/45) fait foi pour les décisions D2–D7, non pour le succès de tests non exécutés.

**EN.** One target prerelease `0.3.4b1`; merges, publishing and deployment are not authorized. Main and last published release as above. **24 open draft PRs**, 12 open issues at this snapshot. Individual PR checks do not qualify a combined candidate.

| PR | SHA observé / Observed SHA | Lot / Track | Tests individuels / Individual checks | Blocage / Blocker |
|---|---|---|---|---|
| [#82](https://github.com/christophejaubert/ha-trybatec/pull/82) | `5fc1d126c7a31a2da1d9769948d05a1fbb3070cb` | Exclu / Excluded | 10 contrôles requis verts* | Migration historique |
| [#118](https://github.com/christophejaubert/ha-trybatec/pull/118) | `8d5aab1343aaf2bf33d57accb92aa7e935c53011` | A tarifs / Tariffs | 10 contrôles requis verts* | Raccorder natif/YTD |
| [#120](https://github.com/christophejaubert/ha-trybatec/pull/120) | `54aa8e9e68b64e33dfa4b442773b1e9701dd2846` | A identités / IDs | 10 contrôles requis verts* | Chevauchement #132 |
| [#124](https://github.com/christophejaubert/ha-trybatec/pull/124) | `926f7bbeb2689bf9b812f71364725825f794093a` | A Gitleaks | 10 contrôles requis verts* | Scan historique planifié |
| [#125](https://github.com/christophejaubert/ha-trybatec/pull/125) | `60a571f7e98b5b114262286538923c75f50784c1` | B filiation / Lineage | 10 contrôles requis verts* | Brancher #36/#88 |
| [#126](https://github.com/christophejaubert/ha-trybatec/pull/126) | `8fd1971fe3872784aaeb16d8a6ea3114609cc34d` | A release CI | 10 contrôles requis verts* | Contrôler notes FR/EN |
| [#127](https://github.com/christophejaubert/ha-trybatec/pull/127) | `f0f74f2fdd48961c6f7322cab8defde627f623b3` | B provenance | 10 contrôles requis verts* | Brancher Recorder |
| [#128](https://github.com/christophejaubert/ha-trybatec/pull/128) | `ba7e25c8669743ba9a39837b93431035fb879133` | B Recorder | 10 contrôles requis verts* | Writer/reprise/restauration |
| [#129](https://github.com/christophejaubert/ha-trybatec/pull/129) | `299d913d80b4844bd8aaa6db2242d3edc8bdbe5b` | B Énergie L6 | 10 contrôles requis verts* | Admissibilité non prouvée |
| [#130](https://github.com/christophejaubert/ha-trybatec/pull/130) | `407f994133e1bd8ef446408f5387ebbbb21cc989` | B Énergie L7 | 10 contrôles requis verts* | Port HA en refus total |
| [#131](https://github.com/christophejaubert/ha-trybatec/pull/131) | `d87fe2adbc1747f5f34668e25619ac0fb31f375c` | A/B marque / Brand | 10 contrôles requis verts* | Recette visuelle |
| [#132](https://github.com/christophejaubert/ha-trybatec/pull/132) | `2c7ef18d7d6f315db56bbe6bcc9441a99ab3135c` | A accès / Access | 10 contrôles requis verts* | Chevauchement #120 |
| [#133](https://github.com/christophejaubert/ha-trybatec/pull/133) | `ed807d3811da36a5223e8fff46ab503e8a04d42e` | B a11y | 10 contrôles requis verts* | Empilement #142 |
| [#134](https://github.com/christophejaubert/ha-trybatec/pull/134) | SHA mouvant (présent document) / Self-updating | MOE | Requalifier après cette édition | Auto-référence |
| [#136](https://github.com/christophejaubert/ha-trybatec/pull/136) | `4275b20ed79b73f72d354b1748463cd3b8d7a183` | A YTD | Checks réussis, trusted sauté / Trusted skipped | Empilée #120 |
| [#137](https://github.com/christophejaubert/ha-trybatec/pull/137) | `7117489ad160f26c5825932e879f5175b3b5e351` | Hors fusion / Proof only | 10 contrôles requis verts* | Ne jamais fusionner |
| [#138](https://github.com/christophejaubert/ha-trybatec/pull/138) | `4c005f9631c61bd8456007760c385e2d44d6529f` | A/B reflow | Checks réussis, trusted sauté / Trusted skipped | Empilée #118 |
| [#139](https://github.com/christophejaubert/ha-trybatec/pull/139) | `fa0c49cb07284088bf92d11b5aff35a9f9210cd0` | A options | Checks réussis, trusted sauté / Trusted skipped | Empilée #120 |
| [#140](https://github.com/christophejaubert/ha-trybatec/pull/140) | `258807304707ee240afdffd47a3cb1929d9a3db0` | A confidentialité / Privacy | 10 contrôles requis verts* | Intégration + ruleset non autorisés implicitement |
| [#142](https://github.com/christophejaubert/ha-trybatec/pull/142) | `8260b269a0b23dd970bafaacb63f3fb6d5a708ce` | B a11y CI | CI 41 succès; contextes sautés | Empilée #133 |
| [#143](https://github.com/christophejaubert/ha-trybatec/pull/143) | `c886e747fd67915936afec60fbde970d6d50cae5` | Hors fusion / Proof only | CI 41 succès; contextes sautés | Ne jamais fusionner |
| [#144](https://github.com/christophejaubert/ha-trybatec/pull/144) | `cb08ddca023a5e50e484e8f51a3db5e47c33a27e` | Lot A intégré / Batch A | 10 contrôles requis verts* | Recette HA réelle, dépendance B |
| [#145](https://github.com/christophejaubert/ha-trybatec/pull/145) | `cb77625ceca508239336272e25caf73087b1059c` | Lot B intégré / Batch B | 10 contrôles requis verts* | L6/L7 natifs, Recorder, recette HA |
| [#146](https://github.com/christophejaubert/ha-trybatec/pull/146) | `d88b24817851f5aa1b7c2415052cfc44a4ca9ffb` | Preuve candidate / Integrated proof | 24/25 contrôles réussis, 1 préparation manuelle sautée / 24 passed, 1 skipped | **Ne pas fusionner** ; qualification globale et recette manquantes |

* **FR :** Les dix checks obligatoires de `main` (Python 3.13/3.14, Ruff, HACS, Gitleaks, HA import/runtime, Hassfest, persistance et intégrité workflow) ont réussi sur les branches directes vérifiées. Préparation manuelle de release sautée. #136/#138/#139 ont le check d'intégrité sauté dans leur contexte empilé ; #142/#143 partagent un SHA avec 41 checks réussis, mais aussi des contextes sautés. **EN:** Ten required checks green on observed direct branches; separate stacked and skipped contexts must not be reported as fully qualified. No integrated-SHA acceptance has been proven.

### FR — Deux lots, une seule qualification

- **A — socle, tarifs, conformité :** [#144](https://github.com/christophejaubert/ha-trybatec/pull/144) compose déjà #120/#132/#118/#136/#139/#138/#131 au SHA `cc95a878df9ae4bd13e1f128e4aa4474b8defb25`, **brouillon non fusionné**, avec CI en cours au premier constat. Revalider le SHA final et les conflits `config_flow.py`, `coordinator.py`, `sensor.py`, options-flow, traductions, tarifs/YTD et panneau. Ne pas recomposer ailleurs ce qui est déjà repris. Vérifier séparément les correctifs CI #124/#126 et #140. D1 : conserver identité Git ; D2 : contrôle `public-privacy-preflight` obligatoire seulement après fusion explicitement autorisée, qualification depuis un workflow de confiance puis modification ciblée du ruleset ; D3 : aucune réécriture d'historique.
- **B — historique, déposés, Énergie, UI :** #127/#128 + #125 + #129/#130 + #133/#142, en raccordant #120/#144 et la composition UI #138/#131 déjà en A. #137 et #143 restent des **preuves non fusionnables** ; ne pas réintégrer leurs commits artificiellement. Périmètre actif #35/#36/#37/#42/#70/#83/#84/#88 et #81 exclusivement non migrant ; **exclusions #82/#34/#39**.
- **Qualification :** branche unique de preuve [#146](https://github.com/christophejaubert/ha-trybatec/pull/146) **créée et non fusionnable** ; assemblage des têtes #144/#145/#142/#124/#126/#140/#134 sans conflit de fichiers, puis mise à jour B. Rejouer et examiner les dix contrôles obligatoires, CodeQL, dépendances, Gitleaks, confidentialité, tests d'intégration et navigateur, inventorier `xfail`, avertissements et tâches sautées. L'ancien essai CI #146 a été bloqué par un accès à l'API GitHub publique indisponible/limité dans `resolve-test-refs` ; ne jamais interpréter ce cas comme une recette ni contourner le contrôle. **Une branche de preuve combinée existe désormais (#146), mais aucun SHA global n'est qualifié à ce stade**.

### EN — A single qualification gate

Batch A has draft composed PR #144, batch B has draft composed PR #145, and draft proof-only PR #146 combines them with access/UI/CI/privacy evidence. Do not duplicate any source work. Batch B must wire provenance/Recorder and physical lineage to L6/L7, plus #133/#142 a11y evidence, preserving A's shared files. Run full CI and browser/HA synthetic tests on the *new combined SHA*, not old proof PR #137/#143. Exclude migration #82 and issues #34/#39. A passing check does not grant merge, release or production access.

### FR — Critères métier et risques bloquants

1. **#36 Recorder :** `history_recorder_b15.py` refuse le rejeu sélectif sans preuve indépendante de quiescence du writer. Exiger lecture intégrale, snapshots immuables V1/V2/V3, vérification de persistance, collisions, redémarrages, crash/reprise, copie isolée et restauration d'essai ; préserver l'absence de double comptage.
2. **#37 :** inventaire et filiation de générations physiques, dates, lacunes, index et unités ; agréger seulement les consommations admissibles, jamais les index cumulés.
3. **#88 L6/L7 :** aucune admissibilité native prouvée ; `energy_bulk_native_observer_l7.py` refuse explicitement toute sauvegarde, écriture de journal et mutation Énergie en production. L'automate L7 et ses tests synthétiques ne remplissent donc pas encore l'exigence d'ajout groupé réel. Préparer un adaptateur et une restauration HA sûrs, mais n'exécuter aucune écriture sur l'installation de l'utilisateur.
4. **Interface :** tests synthétiques FR/EN mobile/bureau clair/sombre et WCAG à relancer sur candidate ; les 56 cas de recette réelle ne sont pas réputés effectués.
5. **Confidentialité :** vérifier les patches et artefacts avant toute contribution publique ; aucun secret, adresse personnelle autre que l'identité Git autorisée, référence d'installation, index ou consommation réelle.

**EN — Remaining functional blockers:** Recorder needs independent writer-quiescence and full readback/recovery proof; physical generation boundaries and no double-counting are unproven end to end; L6 cannot presently admit real sources, and L7's native adapter denies all actual writes/backups/journal operations; browser/a11y checks remain synthetic rather than live HA acceptance.

### FR — Résultats exacts de la preuve combinée #146 (non fusionnable)

- **SHA vérifié :** `d88b24817851f5aa1b7c2415052cfc44a4ca9ffb` ; **24/25 contrôles réussis**, seule la préparation manuelle non déclenchée est `skipped`. Les dix protections GitHub existantes sont vertes sur ce SHA. Voir [PR #146](https://github.com/christophejaubert/ha-trybatec/pull/146).
- **Python 3.13 et 3.14 :** 866 tests réussis, 53 sous-tests réussis, couverture 79,42 % (seuil 75 %) et **2 avertissements** sur les options pytest `asyncio_mode` et `asyncio_default_fixture_loop_scope` pour chaque job ; aucun `xfail` signalé dans ces résumés. Ces résultats sont synthétiques, pas de la recette HA réelle.
- **Autres contrôles verts :** Ruff, HACS, Hassfest, import HA, stockage, Gitleaks, CodeQL, `trusted-workflow-integrity`, dépendances (audit advisory), persistance et Recorder E2E isolés, navigateur FR/EN mobile/bureau et accessibilité 7 vues **synthétiques**.
- **Confidentialité D2 non achevée :** #140 est développée et dans la preuve, mais `public-privacy-preflight` n'est **pas obligatoire** dans le ruleset actuel ; il ne peut être revendiqué comme vérifié sur `main` tant que sa fusion et son exécution de confiance ne sont pas autorisées et observées.
- **Important :** la branche documentaire #134 peut avoir un SHA ultérieur à celui capturé dans l'arbre de preuve #146 ; une modification uniquement documentaire ne valide ni n'invalide les fonctions prouvées. Vérifier l'écart avant toute demande de fusion finale.

### EN — Exact combined proof results

#146 proof SHA `d88b24817851f5aa1b7c2415052cfc44a4ca9ffb`: 24 of 25 completed checks passed, with one manual unreleased draft step skipped; all ten current mandatory checks passed. Python 3.13/3.14: 866 tests plus 53 subtests passed per job, 79.42% coverage, two pytest configuration warnings per job, no xfails reported in these summaries. Browser, a11y, Recorder, persistence and dependency evidence is synthetic or advisory, not live Home Assistant acceptance. `public-privacy-preflight` requires a separate trusted-main gate and ruleset activation after specifically authorized merge of #140. No publication is authorized.

### FR — Notes de release de travail (non publiables en l'état)

**`0.3.4b1` — cible**, pas une release autorisée : installation/réauthentification et notifications ; nouvelles identités physiques stables *pour les nouveaux comptes uniquement* sans migration ; tarifs annuels natifs, calcul YTD par compteur et interface mobile ; provenance historique, continuité des compteurs déposés et contrôle Recorder ; diagnostics L6 et mécanisme transactionnel L7 sous verrou ; sécurité, confidentialité et preuves d'accessibilité améliorées. **Ne pas annoncer un ajout groupé Énergie opérationnel ni une restauration réelle validée** : ces critères restent bloquants. Revalider les notes après recette, SHA final et périmètre approuvé.

### EN — Working release notes (not publishable yet)

Target `0.3.4b1`: setup/re-auth and access notifications; stable physical identities for new accounts only; native annual tariffs and per-meter YTD; responsive UI; historical provenance, retired-meter lineage and Recorder safeguards; guarded Energy L6 evidence and dormant L7 transaction logic; CI/privacy/a11y improvements. **Do not claim operational bulk Energy enrollment or tested native recovery**: these are release blockers. Revise against the final SHA, real acceptance results and approved scope before any release authorization.

### FR — Campagne de recette unique (non exécutée)

**Préparer un environnement de test isolé avec fixtures fictives.** Consigner une baseline `0.3.3b1` (anciens comptes, entités, Recorder, sources Énergie), le SHA exact testé, la version HA, les snapshots et un plan de retour arrière.

**Enchaînement :** mise à niveau sans migration historique ; préservation des comptes/IDs/Énergie ; nouveaux comptes ; authentification 401/403 et réauthentification ; notifications ; tarifs, options natives, persistance et YTD ; compteurs en service/déposés et provenance ; Recorder V1→V2/V3, crash/reprise, absence de rejeu dangereux ; contrôles L6, confirmation L7, sauvegarde/réécriture/récupération en environnement isolé ; navigation FR/EN, clair/sombre, mobile/bureau, clavier et lecteur d'écran ; redémarrage, retour arrière, trace des refus et de l'absence de doublons. **Les opérations réelles de sauvegarde, installation, Recorder, Énergie et restauration requièrent chacune une autorisation explicite couvrant l'opération.**

**EN — One HA acceptance campaign (not executed):** record baseline and exact candidate SHA; test existing/new accounts, stable identities, auth/re-auth/alerts, native tariffs and YTD, measured/estimated history and lineage, Recorder persistence/crash/recovery, guarded bulk Energy and backup/rollback, browser/accessibility and restart/downgrade. Real operations require separate explicit user approval.

### Décisions à venir / Future decisions

**Fusion / Merge:** demande consolidée seulement après vérification des SHA, dépendances, conflits, CI et portée de chaque PR. **Publication / Release:** décision distincte `0.3.4b1`, tag technique sans emoji, titre `🤖 `, SHA exact, notes FR/EN, périmètre D3/D4, résultats et risques. **Installation / Deploy:** troisième décision indépendante. Toute réduction du périmètre exige un accord utilisateur exprès ; pas de suppression silencieuse. / No unauthorized merge, release, tag, install, migration, cleanup, restore or Home Assistant change.

---

## Instantané documentaire antérieur (historique) / Earlier document snapshot (historical)

> Les sections ci-dessous représentent l'état enregistré avant cette réconciliation et peuvent citer des PR encore en brouillon à l'époque. Ne pas les utiliser comme source courante sans vérifier GitHub. / The following sections document an earlier snapshot and may describe PRs as drafts before their later merges. Use the current section above and live GitHub state for decisions.

> **État au 12 novembre 2026 / Snapshot on 12 November 2026.**
> Dépôt / Repository: [christophejaubert/ha-trybatec](https://github.com/christophejaubert/ha-trybatec).
> **Document de préparation, non autorisation de fusion, de publication ou de modification Home Assistant. / Preparation only; no merge, release or Home Assistant change is authorized.**

## FR — Décisions et référence

- **Décision D1 validée par l'utilisateur :** préparer une préversion sans migration historique des comptes existants ; préserver leurs identifiants et le verrou de migration. La migration réelle de la [PR #82](https://github.com/christophejaubert/ha-trybatec/pull/82) demeure exclue, en brouillon, et l'[issue #81](https://github.com/christophejaubert/ha-trybatec/issues/81) ouverte.
- **Version cible validée D2 :** `0.3.4b1` pour la livraison intégrée ; **publication, SHA et calendrier non autorisés**. Dernière release publiée vérifiée : [`0.3.3b1`](https://github.com/christophejaubert/ha-trybatec/releases/tag/0.3.3b1).
- **Référence `main` au constat :** [`a21906bada0b01a9a069afc2a1b84235b2590cc7`](https://github.com/christophejaubert/ha-trybatec/commit/a21906bada0b01a9a069afc2a1b84235b2590cc7) ; la [PR #117](https://github.com/christophejaubert/ha-trybatec/pull/117) (correctifs historiques L2) y est fusionnée. Toute fusion ultérieure exige une nouvelle vérification de `main`.
- **Gouvernance :** les décisions D1–D6 ci-dessous proviennent de validations utilisateur ; la matrice n'est pas elle-même une autorisation d'action GitHub ou Home Assistant. Aucune PR de ce tableau n'est autorisée à fusionner du seul fait de sa CI ; ni clôture automatique d'issue mère.
- **Autorité :** [issue MOE #45](https://github.com/christophejaubert/ha-trybatec/issues/45) et décisions utilisateur explicites ; suivre les références GitHub plutôt que les rapports recopiés. Préserver les critères historiques `COMPAT-01..06` et `UI-01..12` jusqu'à validation réelle documentée.


### Décisions MOE D2–D6 validées / Approved scope decisions (12 novembre 2026)

- **D2 — Validée :** `0.3.4b1` est la **version cible approuvée pour la release fonctionnelle intégrée**. Cela n'autorise **ni la publication, ni sa date, ni un SHA** sans décision ultérieure.
- **D3 — Validée :** inclure l'intégralité des évolutions et correctifs propres au périmètre retenu des issues [#35](https://github.com/christophejaubert/ha-trybatec/issues/35), [#36](https://github.com/christophejaubert/ha-trybatec/issues/36), [#37](https://github.com/christophejaubert/ha-trybatec/issues/37), [#42](https://github.com/christophejaubert/ha-trybatec/issues/42), [#70](https://github.com/christophejaubert/ha-trybatec/issues/70), [#83](https://github.com/christophejaubert/ha-trybatec/issues/83), [#84](https://github.com/christophejaubert/ha-trybatec/issues/84) et [#88](https://github.com/christophejaubert/ha-trybatec/issues/88). La continuité historique, les fonctionnalités Recorder et l'ajout groupé Énergie font partie de la **cible fonctionnelle**, à sécuriser et recetter ; ils ne sont pas déclarés prêts aujourd'hui. Leur activation réelle reste soumise aux confirmations et autorisations applicables.
- **D4 — Validée :** inclure les fonctionnalités **non migrantes** de [#81 via PR #120](https://github.com/christophejaubert/ha-trybatec/pull/120) pour les **nouveaux comptes**, tout en préservant intégralement les comptes historiques et leurs identifiants.
- **D5 — Validée :** exclure [#39](https://github.com/christophejaubert/ha-trybatec/issues/39) (Marketplace/HACS externe, suivi distinct) et [#34](https://github.com/christophejaubert/ha-trybatec/issues/34) (pondération DJU future) de `0.3.4b1`.
- **D6 — Validée :** exclure les **migrations et nettoyages des anciens identifiants** de [PR #82](https://github.com/christophejaubert/ha-trybatec/pull/82) et des sous-critères associés de #37 ; maintenir les verrous, la non-migration et les garanties de non-suppression. **Ne pas exclure pour autant les compteurs déposés, leur filiation ou leur contribution historique**, requis par #37.
- **D7 — Maintenue :** ne publier `0.3.4b1` **qu'après** intégration et qualification du périmètre D3/D4 (en tenant compte des exclusions D5/D6), validation des critères et risques, CI sur le SHA final et autorisation explicite de release. Si une fonction n'est pas qualifiée, maintenir le blocage de publication ou solliciter une **nouvelle décision de réduction du périmètre** ; ne pas la supprimer silencieusement.

**EN — Approved decisions:** **D2** makes `0.3.4b1` the agreed *target version*, not an authorized publication. **D3** includes all selected integration features/fixes from #35/#36/#37/#42/#70/#83/#84/#88, including complete safe Recorder/history continuity and guarded bulk Energy enrollment, subject to development and acceptance. **D4** includes nonmigrating new-account stable IDs from #120 while preserving existing-account identifiers. **D5** excludes Marketplace #39 and future climate-weighted smoothing #34. **D6** excludes legacy-ID migration/cleanup #82 (including corresponding #37 subcriteria), but **not** retired-meter continuity. **D7** prohibits publication until the complete agreed scope is qualified or the user explicitly changes it; merger, actual Home Assistant writes and release remain separately authorized.


### Matrice PR / preuves — FR

| PR / Lot | SHA de tête observé | Qualification GitHub observée | Intégration / Étape suivante |
|---|---|---|---|
| [#117](https://github.com/christophejaubert/ha-trybatec/pull/117) — #36/L2 calcul | `5144d79be6e3880090bcd298f4632426554d352c` (PR) | Fusionnée ; CI sur `main` à vérifier après chaque nouveau merge | **Dans `main`** en squash `a21906bada0b01a9a069afc2a1b84235b2590cc7`. #36 et recette métier restent ouvertes |
| [#118](https://github.com/christophejaubert/ha-trybatec/pull/118) — #42 tarifs | `6898e8af352250f68905d3ba2aca7fb310b2397c` | 22 checks success, 1 skipped ; brouillon | Revue, compatibilité native JSON, coût YTD/dérogations, recette HA ; fusion distincte |
| [#119](https://github.com/christophejaubert/ha-trybatec/pull/119) — #35 installation | `2efcb3a64388ee2729938bb27ba810501e1c295c` | 21 success, 1 skipped ; brouillon ; 2 xfail métier déclarés | Revue tests/docs ; anomalies de notification et refus de logement à traiter séparément |
| [#120](https://github.com/christophejaubert/ha-trybatec/pull/120) — #81 identité neuve, D1 | `2fd05544070d8055495883829bab7c18a09967aa` | 20 success, 1 skipped ; brouillon | Revue compatibilité des comptes historiques et risque de retour arrière des nouveaux comptes ; pas de migration |
| [#121](https://github.com/christophejaubert/ha-trybatec/pull/121) — #88/L3 preuves Énergie | `75cd46826402211d0e4c4b6ad6dd329481c23f8e` | 22 success, 1 skipped ; brouillon | Revue du collecteur dormant en lecture seule ; ne pas activer l'ajout groupé |
| [#122](https://github.com/christophejaubert/ha-trybatec/pull/122) — #70/#83/#84 | `f6444a383de84cc1f54e6cafc8147579af0ab318` | 20 success, 1 skipped ; brouillon | Revue tests/docs ; rejouer/établir la preuve navigateur sur SHA exact ; recette WCAG/HA à faire |
| [#82](https://github.com/christophejaubert/ha-trybatec/pull/82) — migration historique | `5fc1d126c7a31a2da1d9769948d05a1fbb3070cb` | 20 success, 1 skipped ; brouillon | **Hors candidate D1** ; inventaire externe, restauration éprouvée et recette réelle manquants |

Les chiffres des checks ci-dessus sont des **photographies par SHA** et non des déclarations de réussite de toutes les CI à venir. Les étapes `skipped` correspondent notamment à une préparation manuelle de release, non exécutée.

### Matrice des issues / backlog — FR

| Priorité | Issue | Développé / testé / intégré | Reste à prouver ou décider pour clôture |
|---|---|---|---|
| P0 | [#45](https://github.com/christophejaubert/ha-trybatec/issues/45) Release intégrée | Version historique `0.3.3b1` publiée ; candidate `0.3.4b1` proposée ; matrice préparée | Périmètre approuvé, SHA final, CI obligatoire, recette, notes FR/EN, risques, publication distinctement autorisée |
| P0 | [#42](https://github.com/christophejaubert/ha-trybatec/issues/42) Tarifs | Éditeur et services existants ; #118 testée mais non fusionnée | Champ JSON de l'interface d'options native, estimations YTD, recette fonctionnelle |
| P0 | [#35](https://github.com/christophejaubert/ha-trybatec/issues/35) Installation | #119 : tests/docs, non fusionnée ; deux échecs métier attendus | Notification après redémarrage, refus d'accès après découverte, recette HA |
| P0 | [#81](https://github.com/christophejaubert/ha-trybatec/issues/81) Identités | #120 non migrante testée ; #82 historique distincte | Décision d'intégration de #120 ; migration historique #82 et retour arrière non validés |
| P0 | [#70](https://github.com/christophejaubert/ha-trybatec/issues/70) Marque/a11y | #85/#90/#91 déjà intégrées ; #122 tests/docs | Palette PNG, contraste, zoom 200 %, reflow 320 px, clavier, lecteurs d'écran, recette réelle |
| P1 | [#83](https://github.com/christophejaubert/ha-trybatec/issues/83) Guidage | États et guidage codés et testés synthétiquement | Parcours métier complets et preuve HA réelle |
| P1 | [#84](https://github.com/christophejaubert/ha-trybatec/issues/84) Fiches | Cinq informations et navigation testées synthétiquement | Valeurs/provenance et contexte vérifiés réellement, accessibilité |
| P1 | [#36](https://github.com/christophejaubert/ha-trybatec/issues/36) Historique | #117 fusionnée : DST, zéros, unités, `Decimal` | Provenance quotidienne, couverture, remplacements/chevauchements, persistance Recorder, recette |
| P1 | [#37](https://github.com/christophejaubert/ha-trybatec/issues/37) Déposés | Inventaires/diagnostics partiels | Filiations, périodes, références externes, continuité, absence de nettoyage automatique |
| P1 | [#88](https://github.com/christophejaubert/ha-trybatec/issues/88) Énergie | #91/#92 fusionnées ; #121 L3 testée, dormante | L6 lecture seule ; L7 activation transactionnelle séparée, non autorisée |
| P2 | [#39](https://github.com/christophejaubert/ha-trybatec/issues/39) Marketplace | Suivi distinct | Vérifier tous les critères HACS/Marketplace après stabilisation |
| P3 | [#34](https://github.com/christophejaubert/ha-trybatec/issues/34) DJU chauffage | Différé | Étude et décision future ; hors release candidate |

### Critères historiques de #45

La description originale de #45 reste la source des **6 critères `COMPAT-01..06` et 12 critères `UI-01..12`**. Aucun n'est automatiquement validé par une PR fusionnée ou une CI réussie. Le suivi doit conserver les cases historiques ouvertes, documenter pour chacun le SHA, le test, la recette, le résultat et la limite ; **ne pas réécrire les objectifs originaux comme s'ils étaient déjà acceptés**.

### Chemin critique et ordonnancement — FR

1. **P0 — CI/CD :** analyser le [`gitleaks` échoué du run planifié #43254529863](https://github.com/christophejaubert/ha-trybatec/actions/runs/43254529863) au SHA `a21906bada0b01a9a069afc2a1b84235b2590cc7`, malgré la [CI sur push réussie #43251453215](https://github.com/christophejaubert/ha-trybatec/actions/runs/43251453215) sur ce même SHA. Ne pas présumer d'une fuite de secret ; identifier la cause et rétablir le contrôle obligatoire.
2. **P0 — Intégrations parallèles :** revue finale de #119 (tests/docs), #121 (module dormant) et #122 (tests/docs), puis décisions de fusion **séparées**. Examiner simultanément #118 (tarifs actifs) et #120 (comportement des nouvelles installations, risque de downgrade).
3. **P1 — Correctifs indépendants :** #35 notifications/accès, #42 JSON natif et estimation YTD, #70 palette/accessibilité, #36/#37 provenance/filiation, #88 L6 purement en lecture seule. Vérifier les propriétaires des fichiers avant tout changement.
4. **P1 — Candidate :** intégrer et qualifier toutes les fonctionnalités D3/D4, dont #88/L7 avec protections et validation adaptées, sans exécuteur/migration/nettoyage historique #82, et sans #34/#39. Conserver les actions réelles Recorder/Énergie sous confirmation spécifique ; ne pas publier un périmètre partiel sans nouvel arbitrage utilisateur.
5. **P1 — Recette puis publication :** contrôles CI sur SHA final, FR/EN et bureau/mobile, vérifications critiques réelles et non-régression du compte historique, plan de retour arrière et limites documentés. Numéro, SHA, notes et risques exigent accord utilisateur avant release.

**Anomalie de convention :** le workflow de publication [`.github/workflows/publish-experimental.yml`](https://github.com/christophejaubert/ha-trybatec/blob/main/.github/workflows/publish-experimental.yml) génère encore le titre `Trybatec VERSION` sans le préfixe `🤖 `. Correction CI/CD dédiée avant la prochaine release ; **le tag conserve son format sans emoji**.

**Autorisation :** ce document n'autorise aucune fusion, release, installation, migration, restauration ni modification Home Assistant. Les comptes historiques et leurs identifiants doivent rester préservés ; ne jamais publier de preuves réidentifiables.

---

## EN — Decisions, status and release path

**D1 approved by the user:** prepare an integrated prerelease that does **not** migrate existing historical accounts. Keep [PR #82](https://github.com/christophejaubert/ha-trybatec/pull/82) in draft and issue #81 open; stable IDs for **new** accounts are separately proposed through [PR #120](https://github.com/christophejaubert/ha-trybatec/pull/120). Preserve historic entity/device IDs and migration safety locks.

- **Approved target version (D2):** `0.3.4b1` (release not authorized); latest verified published tag: `0.3.3b1`.
- **Verified main baseline:** `a21906bada0b01a9a069afc2a1b84235b2590cc7`, including merged L2 [PR #117](https://github.com/christophejaubert/ha-trybatec/pull/117).
- **All six open PRs are drafts:** #82, #118, #119, #120, #121, #122. Their reported automated checks completed successfully on their **own exact heads**, with intentional manual steps skipped. No live HA business acceptance is implied.

### PR matrix — EN

| PR | Candidate purpose | State / blocking proof |
|---|---|---|
| [#117](https://github.com/christophejaubert/ha-trybatec/pull/117) | Safe L2 calculations | Merged; does not close #36 |
| [#118](https://github.com/christophejaubert/ha-trybatec/pull/118) | Annual tariff form | Draft; native JSON options, YTD estimate and live acceptance outstanding |
| [#119](https://github.com/christophejaubert/ha-trybatec/pull/119) | Setup/reauth test documentation | Draft; two known expected-failure cases need correction |
| [#120](https://github.com/christophejaubert/ha-trybatec/pull/120) | Greenfield stable IDs, no legacy migration | Draft; downgrade risk for newly created accounts |
| [#121](https://github.com/christophejaubert/ha-trybatec/pull/121) | Read-only dormant Energy evidence collector | Draft; full history/lineage verification and subsequent L6/L7 separate |
| [#122](https://github.com/christophejaubert/ha-trybatec/pull/122) | UI/UX evidence and brand audit | Draft; full browser-on-head and actual WCAG/HA acceptance outstanding |
| [#82](https://github.com/christophejaubert/ha-trybatec/pull/82) | One-time historical migration | **Excluded** from this candidate; external dependencies, proven recovery and live acceptance missing |

### Open issue backlog — EN

| Priority | Issue | Remaining gate |
|---|---|---|
| P0 | [#45](https://github.com/christophejaubert/ha-trybatec/issues/45) | Approved exact scope/SHA/version/notes, green mandatory CI, live acceptance, publication authorization |
| P0 | [#42](https://github.com/christophejaubert/ha-trybatec/issues/42) | Native JSON, YTD deviation behavior, live tariff acceptance |
| P0 | [#35](https://github.com/christophejaubert/ha-trybatec/issues/35) | Persistent notification after coordinator restart, discovered-property access denial, live acceptance |
| P0 | [#81](https://github.com/christophejaubert/ha-trybatec/issues/81) | Split greenfield delivery vs still-blocked legacy migration and recovery |
| P0 | [#70](https://github.com/christophejaubert/ha-trybatec/issues/70) | PNG palette, contrasts, keyboard, zoom, reflow, screen readers |
| P1 | [#83](https://github.com/christophejaubert/ha-trybatec/issues/83) | Actual guided-path acceptance |
| P1 | [#84](https://github.com/christophejaubert/ha-trybatec/issues/84) | Actual five meter fields/provenance and contextual navigation |
| P1 | [#36](https://github.com/christophejaubert/ha-trybatec/issues/36) | Daily lineage, coverage, overlaps, Recorder persistence |
| P1 | [#37](https://github.com/christophejaubert/ha-trybatec/issues/37) | Retired meter lineage, continuity, consumers and safe cleanup gates |
| P1 | [#88](https://github.com/christophejaubert/ha-trybatec/issues/88) | L6 read-only connection, separate L7 reversible enrollment |
| P2 | [#39](https://github.com/christophejaubert/ha-trybatec/issues/39) | Marketplace readiness after stabilization |
| P3 | [#34](https://github.com/christophejaubert/ha-trybatec/issues/34) | Degree-day smoothing research, deferred |

### Next steps / Required safeguards — EN

1. Investigate the scheduled `gitleaks` failure without assuming a credential leak. Fix the release-title `🤖 ` convention separately.
2. Review draft PRs #119/#121/#122 for independent integration; review functional PRs #118/#120 with stricter backward-compatibility and downgrade checks. **Each merge requires explicit user authorization**.
3. Reconcile `main`, exact SHA CI and remaining branches after every approved merge; rerun checks as appropriate.
4. Prepare an integrated nonmigrating candidate covering all approved D3/D4 features, including safe Recorder revision workflows and guarded Energy L7 bulk enrollment once qualified; exclude #82 legacy-ID migration/cleanup and #34/#39. Real Recorder/Energy operations retain separate confirmations and authorization; do not silently release a partial scope.
5. Require a separate user decision for exact version, SHA, FR/EN notes, acceptance scope, risks and publication; installation on Home Assistant and migration/restore are independent decisions.

**Evidence hierarchy:** developed ≠ CI-tested ≠ real Home Assistant accepted ≠ merged ≠ released ≠ installed. An issue is not closed merely because one PR merged. Only anonymized, non-reidentifying acceptance conclusions may be stored publicly; private installation data must stay private.
