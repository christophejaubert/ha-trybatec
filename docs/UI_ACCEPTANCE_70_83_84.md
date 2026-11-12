# 🤖 Qualification UI/UX #70, #83, #84 / UI acceptance

**FR — Statut : préparation technique uniquement, sans recette métier réelle.**  
**EN — Status: technical evidence preparation only; no live business acceptance.**

Périmètre / Scope: [#70](https://github.com/christophejaubert/ha-trybatec/issues/70), [#83](https://github.com/christophejaubert/ha-trybatec/issues/83), [#84](https://github.com/christophejaubert/ha-trybatec/issues/84).  
Références / References: [UI_GUIDELINES.md](UI_GUIDELINES.md), [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md), [WCAG 2.2](https://www.w3.org/TR/WCAG22/).  
Apports précédents / Existing work: PR [#85](https://github.com/christophejaubert/ha-trybatec/pull/85) (charte / guidelines), [#90](https://github.com/christophejaubert/ha-trybatec/pull/90) (états et navigation / states and links), [#91](https://github.com/christophejaubert/ha-trybatec/pull/91) (guidage Énergie / Energy guidance).

## FR — Portée et niveaux de preuve

Ce dossier ne modifie aucun composant de production, aucune configuration Home Assistant, aucune donnée fournisseur, aucune statistique Recorder et aucune préférence Énergie. Il ne modifie pas `trybatec-panel.js`, réservé au chantier #42.

Distinguer systématiquement :

1. **Code présent** : la fonction existe, sans présumer de son comportement dans HA.
2. **Test automatisé** : preuve reproductible liée au SHA exact, avec périmètre et limites.
3. **Recette HA réelle** : manipulation humaine sur une version installée identifiée, capture expurgée, résultat et anomalies.

**Base examinée le 12/11/2026 :** `main` à `6ebbd7245cbb5bff90c3fb98084a9a78fc47b4b6`, runs [compatibilité 43240130126](https://github.com/christophejaubert/ha-trybatec/actions/runs/43240130126) et [navigateur 43240130211](https://github.com/christophejaubert/ha-trybatec/actions/runs/43240130211) réussis. La branche de préparation est créée depuis une révision ultérieure de `main` ; ces runs antérieurs **ne prouvent pas** la CI sur son SHA final.

### Matrice exigence → preuve → résultat → reste à faire

| Référence | Preuve existante | Résultat limité | Reste à faire |
|---|---|---|---|
| #70 BRAND-01 | Ressources PNG présentes ; tailles 256/512 px et transparence vérifiées | Partiel | Examiner silhouette, petit format et intégration dans HA |
| #70 BRAND-02 | Audit PLTE de deux PNG | **Écart constaté** : les quatre hex canoniques ne figurent pas exactement dans les palettes | Correction graphique indépendante, puis test rendu final |
| #70 UI-CLR-01/02/03 | Tokens fluide et thème dans panneau ; huit variantes synthétiques | Partiel | Vérifier les sept sections et la bascule du thème HA à chaud |
| #70 UI-SEL-01 | `aria-pressed` et état sélectionné dans le code | Partiel | Vérifier annonce vocale et absence de décalage |
| #70 A11Y-01/02/03 | Texte + pictogrammes, vérification contraste d'un bouton neutre synthétique | Partiel | Tous les couples texte/fond, bordures, graphiques et états HA |
| #70 A11Y-04 | Reflow 320 CSS px synthétique sur **3 sections uniquement** | Incomplet | Étendre à 7 sections ; texte 200 % et espacement |
| #70 A11Y-05/06/07 | Focus de navigation synthétique ; rôles ARIA partiels | Incomplet | Clavier complet, lecteurs d'écran, monochromie et simulations |
| #70 REG/REL | CI de la révision historique réussie | CI seulement | CI SHA candidat, revue et recette réelle |
| #83 états et facultativité | Tests PR #90/#91 sur erreurs prouvées, non vérifié, tarifs facultatifs | Synthétique | Scénarios réels nouveau/existant, unités/Recorder/Énergie |
| #83 parcours et prérequis | Guidage Énergie et liens de repli | Partiel | Tous les parcours, dépendances exactes et retour contextuel |
| #84 cinq champs/provenance | Tests `test_panel_ui_semantics_83_84.py` et interface | Synthétique | Contrôler cinq valeurs, statuts et origines dans HA |
| #84 compteurs déposés, historique | Recherche liée au `physical_key`, retours contextualisés | Synthétique | Tester compteurs déposés et périmètre de recherche réelle |
| #84 clavier/écran/FR/EN | Huit variantes et focus partiel | Incomplet | Lecteurs d'écran, tabulation exhaustive, 200 % réel |

### Les sept sections

1. Vue d'ensemble / Overview — état de configuration, contrôles distincts, tarifs facultatifs.
2. Compteurs / Meters — cinq champs, statut du compteur, provenance, actions explicites.
3. Historique & lissage / History & smoothing — bornes, état de vérification, retour au compteur.
4. Tarifs / Tariffs — état, unité/prix et années affichées ; ne pas enregistrer en recette.
5. Énergie & versions / Energy & versions — prérequis et absence d'activation implicite.
6. Diagnostics / Diagnostics — disponibilité de l'audit, sans suppression implicite.
7. Réglages / Settings — présentation et aide ; ne pas enregistrer en recette.

**Grille à exécuter :** chaque section × `FR`/`EN` × `bureau`/`mobile` × `clair`/`sombre` = **56 cas**. La CI navigateur existante vise ces 56 captures synthétiques, mais la preuve HA réelle démarre à 0/56.

Pour chaque cas : version HA, version intégration, SHA déployé si déterminable, type de terminal, navigateur, langue, thème, date/heure, auteur, résultat (`Non exécuté` / `Validé` / `Échec` / `Non applicable`), preuve expurgée, référence de l'anomalie. Ne pas capturer de compte, secret, série physique ou historique personnel en clair.

### Contrôles transversaux à exécuter en lecture seule

- **Clavier :** ordre Tab/Shift+Tab dans 7 sections ; entrée/espace ; pas de piège ; focus visible et non masqué ; explication des actions désactivées.
- **Lecteur d'écran :** VoiceOver macOS/iOS et/ou TalkBack Android ; rôles/noms/valeurs, états sélectionnés, messages dynamiques ; pas de faux élément activable.
- **Zoom/texte :** zoom 200 %, espacement WCAG 1.4.12, reflow 320 CSS px dans les 7 sections, sans défilement horizontal général ni perte fonctionnelle hors exceptions WCAG.
- **Contraste :** 4,5:1 texte standard ; 3:1 grand texte et éléments non textuels requis ; contrôle sur **couleurs effectivement rendues**, non seulement tokens théoriques.
- **Vision des couleurs :** gris, protan/deutan/tritan ; pictogrammes, légende et alternatives des graphiques ; jamais la couleur seule.
- **Toucher :** 24 × 24 CSS px selon exceptions WCAG 2.5.8 ; objectif ergonomique 44 × 44 px.
- **Thèmes :** bascule clair→sombre→clair sans rechargement, vérifier fond, boutons, état sélectionné et contraste.
- **Sans écriture :** ouvrir seulement des pages et liens de consultation explicitement identifiés comme sûrs. Ne pas cliquer sur enregistrer, importer, migrer, appliquer, supprimer, changer d'unité ou lancer une recherche fournisseur réelle.

### Jeu de scénarios métier (#83/#84)

- Installation initiale / configuration existante ; compteurs actifs/déposés.
- Tarifs absents facultatifs ; Recorder absent ; Energy non configurée ; fonctionnalités bloquées.
- Unité absente, unité API explicite, confirmation manuelle, proposition de graphique, conflit démontré.
- Index courant absent sur compteur déposé ; historique snapshot non chargé ; analyse non exécutée ; recherche terminée sans preuve attribuable au compteur exact.
- Navigation `historique`, `relevés`, `unité` avec compte/logement/`physical_key` conservés ; retour contextuel ; aucune lecture fournisseur lourde implicite.
- Absence d'accès au compteur précédemment sélectionné : repli sûr, sans divulgation d'un autre compteur.
- Vérification des cinq champs : dernier index disponible ; première observation connue ; dernière observation source ; date du dernier index exploitable ; statut et provenance de l'unité.

### Outil d'audit de marque

`python scripts/brand_asset_audit.py` : rapport JSON **non bloquant**, sans accès réseau, sans modification de fichiers.  
`python scripts/brand_asset_audit.py --strict` : retourne un échec si tailles/transparence/palette exacte déclarée ne sont pas toutes vérifiées. **Ne pas activer la variante stricte en CI avant correction des assets.**

L'outil contrôle le conteneur PNG, les CRC, dimensions, `tRNS` et la présence des teintes exactes dans `PLTE` lorsqu'elle existe. Il ne décode pas les pixels RGBA/RGB, ne prouve ni usage des couleurs, ni silhouette, ni contraste du thème, ni recette HA.

Constat de référence au 12/11/2026 pour `icon.png` : couleurs les plus proches observées dans la palette : EF `#0B85D7`, ECS `#C7395C`, CET `#DF9F24`, marque `#4F9E49` ; valeurs canoniques respectives `#0A84D8`, `#C73A5C`, `#E0A126`, `#4E9E4A`. Vérifier l'asset final après évolution.

### Décision MOE

**Ne clôturer aucune issue #70, #83 ou #84 sur les seuls tests synthétiques.** Évaluer les écarts réels, faire valider la recette, puis réconcilier GitHub. La présence d'un commentaire, d'une case cochée ou d'un statut CI n'autorise pas fusion ou release.

---

## EN — Scope and acceptance procedure

**No writes to Home Assistant, vendor data, Recorder or Energy; no modification to `trybatec-panel.js`.** The baseline has documented design rules (#85), synthetic states and contextual navigation (#90), and synthetic Energy guidance (#91). They are not a live HA acceptance test.

The acceptance matrix above is bilingual by reference/meaning. In brief:

- **Brand #70:** dimensions and PNG transparency verified; canonical palette declarations currently differ from required exact hex values. Visual geometry and real theme contrast are not accepted.
- **Themes and A11Y #70:** synthetic FR/EN × desktop/mobile × light/dark coverage; 320 CSS px only explicitly asserted on Overview, Meters and History; focus only partially checked; no demonstrated real 200% text zoom, full keyboard, screen reader or color-blindness testing.
- **Guided setup #83:** control state, availability, optionality and causes must remain separate. Retired meters, absent optional tariffs, unknown units or pending Recorder verification are not automatically proven failures.
- **Meter details #84:** verify all five values with **status and provenance**; distinguish missing snapshot data from absent vendor history; retain exact physical meter context in read-only navigation and safe back flow.

Run all **56 live configurations** (seven sections × two languages × two devices × two themes), document version/SHA/date/tester, pass/fail and sanitized evidence. Review complete keyboard/VoiceOver/TalkBack access, text zoom 200%, 320 CSS px reflow across **all seven sections**, text spacing, contrast of computed colors, greyscale/CVD simulations, focus visibility, and accessible disabled reasons. Check light/dark switching while the panel is open.

For scenarios, test initial/existing installations, active/retired meters, unverified/manual/API units, incomplete or unqueried history, partial/missing Recorder versions, absent Energy setup, optional tariffs, physical-key navigation, safe missing-target behavior, and no implicit writes.

The read-only PNG audit command reports JSON by default; `--strict` is an **opt-in** future gate and currently exposes a known logo palette discrepancy. A palette declaration check cannot substitute for pixel, visual or assistive-technology acceptance.

**Gate:** CI on exact final commit + review + real HA acceptance are independent. Do not close issues or merge a PR solely because CI passes.
