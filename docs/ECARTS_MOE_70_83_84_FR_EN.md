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
