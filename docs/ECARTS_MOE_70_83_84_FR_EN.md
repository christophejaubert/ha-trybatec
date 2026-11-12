# 🤖 Écarts et coordination #70/#83/#84 / Gap register

**Référence de départ / Baseline:** `main` `a1bd6d8558c8fe1cc13cadeb1ff4aaa20528dc53` ; PR [#118 tarifs](https://github.com/christophejaubert/ha-trybatec/pull/118) toujours propriétaire du panneau et de `scripts/browser-ci/acceptance.cjs`. Vérifier son dernier SHA avant chaque modification commune.

## FR — Priorisation

| Priorité | Exigence | Fait observé | Reste à réaliser |
|---|---|---|---|
| P1 | #70 BRAND-01/02 | Palette du logo écartée sur baseline ; correction dans une PR graphique indépendante | Test visible des pixels, revue silhouette, petit format et thème HA |
| P1 | #70 A11Y-04 | Reflow 320 px testé sur 3 vues dans le navigateur de référence | Sonde indépendante des 7 vues × 8 variantes ; correction fonctionnelle après stabilisation de #118 |
| P1 | #70 A11Y-05/07 | Focus partiel ; pas de recette lecteur d'écran | Clavier complet, VoiceOver/TalkBack, zoom 200 %, focus non masqué |
| P1 | #83 parcours | Guided Energy fallback, états et actions contextuelles PR #90/#91 | Parcours complets tarifs/unités/historique/Recorder/Énergie, dépendances vraies ; garde-fous serveur |
| P1 | #84 cinq champs | Tests synthétiques et provenance API/manuelle | Vérification sur le compteur exact, compteur déposé et contexte introuvable dans HA |
| P2 | #70 UI-CLR | Boutons neutres présentent un fort contraste **de tokens statiques** | Test contrastes rendus HA, clair/sombre à chaud, 7 écrans |
| P2 | #70 graphique | Aucune preuve de toutes les alternatives au code couleur | Légendes, formes/points, tableaux accessibles et monochromie |

### Lots

**Lot graphique #70 :** deux PNG + test des pixels visibles + documentation. Aucun fichier de #118.

**Lot audit autonome #70/#83/#84 :** contrôleur statique WCAG, sonde Chromium synthétique indépendante et grille 56 cas réelle FR/EN. Aucun fichier de #118. L'ajout d'un workflow CI dédié doit être coordonné avec le chantier CI/CD ; le simple ajout d'un script ne démontre pas son exécution.

**Lot de correctifs fonctionnels différé :** `trybatec-panel.js` (et éventuellement `acceptance.cjs`) après stabilisation/fusion autorisée de #118 et synchronisation de `main`, sans migration/Recorder/Énergie implicite.

### Niveaux de preuve

Code développé ≠ tests réussis sur SHA ≠ validation métier dans HA réel. Les 56 configurations ne sont pas toutes recettées du seul fait de leur présence dans un CSV. Les exigences non démontrées restent ouvertes. Les captures, logs et index privés ne sont jamais publiés.

## EN — Gaps and delivery boundaries

P1: exact logo color use and final visual approval; full seven-view 320 CSS px coverage; keyboard/focus/text zoom/assistive technology; comprehensive #83 setup workflows; all five #84 physical meter fields and context-safe navigation.

P2: real light/dark computed contrasts, hot theme switch, graph alternatives and colour-independent indicators. Source-only tests and synthetic browser fixtures cannot establish real HA acceptance.

Deliver independently of tariff PR #118, with no changes to `trybatec-panel.js` or its `acceptance.cjs` until coordinated. Keep #70/#83/#84 open and prohibit implicit configuration writes, migration, merging or release.


## FR — Mesures Chromium synthétiques vérifiées le 12/11/2026

**Preuve :** [workflow UI accessibilité #43283214906](https://github.com/christophejaubert/ha-trybatec/actions/runs/43283214906), SHA `2d61e281e75c8949e736567e91c5150fef6c3fbe`. La sonde a achevé les 56 combinaisons synthétiques ; aucune recette Home Assistant réelle.

| Mesure | Constat | Qualification |
|---|---|---|
| Reflow 320 CSS px | **4/56 observations de débordement** | **P1 :** toutes les variantes FR (bureau/mobile × clair/sombre) de la section **Énergie et versions**, largeur document `373 px` à viewport `320 px` |
| Contour de focus | 0 observation de contour absent | Contrôle limité à la navigation synthétique, pas à tous les champs |
| Focus hors viewport | **40/56 avant défilement ; 0/56 après scrollIntoView** | Barres d’onglets défilantes : anomalie de masquage non démontrée par cette sonde ; parcours clavier complet restant |
| Cibles <24 CSS px | **24 observations / 8 variantes : trois cases à cocher natives 13×13 px**, chacune dans un libellé cliquable | Deux libellés à 19 px de haut : augmentation à min. 32 px dans PR empilée #138 ; vérifier nouveau SHA et exceptions WCAG |
| VoiceOver/TalkBack, zoom texte 200 % | Non testés | Recette complémentaire nécessaire |

Les **4 cas de débordement concernent le texte français d'Énergie et versions** ; aucun débordement n'est observé par cette sonde dans les 52 autres combinaisons. Ce résultat synthétique n'identifie pas encore à lui seul l'élément CSS responsable. Correctif de panneau à coordonner **après** stabilisation de la PR tarifaire #118 ; ne pas modifier ce fichier dans la présente PR de preuves.

## EN — Verified synthetic Chromium observations (2026-11-12)

[Evidence run #43283214906](https://github.com/christophejaubert/ha-trybatec/actions/runs/43283214906), SHA `2d61e281e75c8949e736567e91c5150fef6c3fbe`: all **56 synthetic** configurations executed; zero live HA acceptance.

**Four** 320 CSS px overflows occur only on French **Energy & versions**, across desktop/mobile and light/dark: measured document width **373 px** for a **320 px** viewport on baseline main. A refined probe measured 40 navigation buttons initially offscreen, **zero after explicit scroll-to-view**, zero button centers obscured and zero missing focus outlines. It found **24 observations of three 13px native checkboxes**, all inside clickable labels, two of whose heights are 19px. The independent stacked draft #138 raises direct action-label min-height to 32px and fixes French Energy reflow; **those fixes are not yet in main**. These are synthetic observations, not live HA WCAG certification. Screen readers, true 200% text resizing, and full keyboard traversal remain untested.

Coordinate any shared panel fix with tariff PR #118. Keep #70/#83/#84 open for complete real acceptance.

### Preuve affinée / Refined probe evidence

**FR/EN :** [Workflow #43307386560](https://github.com/christophejaubert/ha-trybatec/actions/runs/43307386560), SHA `b6a7b9ed3c18cc3c0d0d5e3efed6cfa0744b937f` : 56 cas synthétiques, reflow FR Énergie 4/56 sur baseline, focus visible et 0/56 hors fenêtre **après** défilement, petites cibles précisées en cases à cocher avec libellés. Les valeurs précédentes 40/56 et 56/56 provenaient de l'ancienne sonde, moins précise ; ne pas les réutiliser comme des échecs WCAG certifiés. Aucun test HA réel.

---

## FR — Revue sécurité du workflow #133 (CI/CD)

**État source :** [PR #133](https://github.com/christophejaubert/ha-trybatec/pull/133), SHA `7cbd79859f7b1e3ff07d9318df05badebbdbe1de`, [workflow #43283574524](https://github.com/christophejaubert/ha-trybatec/actions/runs/43283574524) réussi. Test **synthétique** uniquement, sans connexion au Home Assistant réel, sans jeton HA, sans identifiant de compteur ni donnée de consommation. Le rapport initial comportait 56 cas dont 4 débordements FR Énergie ; la sonde affinée de #133 distingue désormais 40 éléments initialement hors écran, aucun après défilement explicite, et 24 observations de petites cases à cocher natives dans des libellés cliquables. Ces mesures restent synthétiques et ne constituent pas une certification WCAG.

**Contrôles d'isolation vérifiés :** `permissions: {}`, checkout sans identifiants persistants, actions référencées par SHA immuable, conteneur Playwright référencé par digest, utilisateur non root 1001, `npm ci --ignore-scripts` depuis lockfile, un artefact JSON synthétique à rétention limitée. L'audit n'a identifié aucune donnée réelle incluse dans le jeu de test. La CI verte ne prouve pas l'absence absolue de fuite en cas de modification malveillante d'un script de PR, ni une conformité WCAG.

**Correctif CI proposé séparément :** compléter les filtres de déclenchement quand les dépendances ou tests du diagnostic changent ; tester et valider la structure 56 cas et le marqueur `synthetic-only`, refuser les champs à risque et les destinations externes dans l'artefact ; interdire l'upload si la validation ou le diagnostic échoue (`if: success()`, `if-no-files-found: error`). Aucune modification fonctionnelle du panneau. L'intégration du correctif à #133 requiert une décision de fusion distincte. Les résultats synthétiques restent des **écarts** et non une recette réelle.

## EN — #133 CI security review

[PR #133](https://github.com/christophejaubert/ha-trybatec/pull/133) at `7cbd7985`, [run #43283574524](https://github.com/christophejaubert/ha-trybatec/actions/runs/43283574524), passed its synthetic 56-case probe with **zero real HA sessions**. Initial synthetic diagnostics reported four French Energy 320-px overflows; the refined #133 probe now distinguishes 40 targets initially offscreen but zero after explicit scrolling, and 24 small native checkbox observations inside clickable labels. These are not automatically proven WCAG failures.

Baseline isolation uses zero GitHub permissions, a credential-free checkout, SHA-pinned actions, a digest-pinned non-root Playwright container, script-free locked npm installation and a short-lived synthetic JSON artifact. No real meter or supplier data was found in the fixed fixture. A passing untrusted-PR workflow is **not** proof against all possible malicious code or live HA accessibility. The separate CI follow-up adds complete change-path triggers, schema/identifier checks and fail-closed artifact upload after successful probe and validation. It does not change business UI code or authorize merging #133.
