# 🤖 #155 — Matrice de qualification indépendante / Independent qualification matrix

**FR — Référence figée :** `main` `8d621da9703b40662800b4a7c286707e8a7f895f`. Développement concurrent #156 : SHA mobile, à recontrôler à la réconciliation. Tests ajoutés sur une branche **distincte** et limitée à `scripts/browser-ci/`. Aucune donnée réelle, aucune connexion fournisseur, aucun accès à Home Assistant, aucune écriture Recorder/Énergie. Une recette navigateur synthétique, même réussie, n'est **pas** une recette sur HA.

**EN — Fixed baseline:** `main` `8d621da9703b40662800b4a7c286707e8a7f895f`. Concurrent #156 head is moving and must be rechecked. This test-only branch modifies `scripts/browser-ci/`. No real meter data, vendor requests, HA connections, Recorder/Energy writes or production acceptance.

## Matrice / Coverage

| Critère | Contrat vérifié / Assertion | Exécutable ou preuve antérieure | Limite / Boundary | Propriétaire des corrections |
|---|---|---|---|---|
| **C1** | Entités indisponibles 0=succès, >0=alerte, inventaire inconnu=neutre ; icône + texte | `qualification_155_cross.cjs` dans 8 combinaisons ; `tests/test_panel_issue_155.py` sur #156 | Vérification synthétique, non lecteur d'écran réel | #155 UI (#156) |
| **C2** | Aucun scan lourd à l'ouverture des vues ; scan explicite global, lecture seule | `qualification_155_cross.cjs` C11 ; tests ciblés #156 | Exhaustivité fournisseur non prouvable dans navigateur ; pas de données réelles | #155 UI + C11 historique |
| **C3** | Sélection clavier conserve la clé physique et révèle la bonne fiche/focus | `qualification_155_cross.cjs` C3, `acceptance.cjs` existant | Focus visuel synthétique, non VoiceOver/TalkBack | #155 UI (#156) |
| **C4** | Aucun accès visuel à l'affirmation « données inventées/non inventées » ; provenance conservée | C4 sur sept vues + tests statiques #156 | Traductions natives hors navigateur couvertes par test ciblé #156 | #155 UI (#156) |
| **C5** | Ligne physique : état terminé/à vérifier/à traiter et pictogramme distinct du fluide ; absence de faux avertissement | `qualification_155_cross.cjs` C5-C6 ; contrôle de boutons Energy existant dans `acceptance.cjs` | Tous les boutons métiers ne sont pas simulés ; désactivation explicative à étendre | #155 UI (#156) |
| **C6** | Déposé avec dernier index historique **brut** distinct de l'index courant : ne pas qualifier automatiquement et ne pas exiger d'index courant | `qualification_155_cross.cjs` C5-C6, deux générations EF | Qualité/continuité physique dépend de #37 ; pas de preuve source réelle | #155 UI + #37 |
| **C7** | Absence de lien/bouton d'ancienne révision dans les **sept vues** | `qualification_155_cross.cjs` C7 | Les routes natives externes ne sont pas ouvertes ; absence de régression backend couverte ailleurs | #155 UI (#156) |
| **C8** | Contexte et jeton de fluide visibles, styles fluides et identités séparées | `qualification_155_cross.cjs` C8 ; `acceptance.cjs` et sonde a11y existantes | Comparaison chromatique exhaustive par fluide et lecteur d'écran réel restent à faire | #155 UI (#156) |
| **C9** | Bornes compte/compteur distinctes, indication **partielle**, inconnu=vide, date manuelle conservée, extension à aujourd'hui, aucune lecture déclenchée | `qualification_155_cross.cjs` C9, vérification Recorder par `acceptance.cjs` | Rechargement complet et concurrence réseau doivent être complétés ; pas d'import | #155 UI + #36 |
| **C10** | Origine initiale indéterminée ; confirmation de lissage bloquée sans motif ; texte d'aide | `qualification_155_cross.cjs` C10 | Persistance de décision approuvée testée dans les tests backend #36, non écrite par navigateur | #155 UI + #36 |
| **C11** | Échec → non-complet, saisie tarifaire possible, réessai explicite, cache, absence de relance par navigation, annulation et absence de mutation | `qualification_155_cross.cjs` C11 ; `tests/test_panel_issue_155.py` C2 | La reprise partielle sûre, fenêtres vérifiées et catégories d'erreur nécessitent contrat backend C11 ; un cache n'est pas une preuve d'exhaustivité | C11 historique + #155 UI |

## Exécution / Execution

```bash
npm ci --prefix scripts/browser-ci --ignore-scripts --no-audit --fund=false
node scripts/browser-ci/acceptance.cjs
```

L'exécution appelle `qualification_155_cross.cjs` **en plus** des parcours existants : 2 langues × 2 tailles × 2 thèmes × 7 vues = **56 observations de navigation conservées**. Les assertions métier supplémentaires sont indépendantes et produisent des résultats `PASS` / `FAIL` par combinaison dans la sortie standard. Une assertion échouée entraîne un code de sortie non nul : **aucun test attendu échoué n'est converti en réussite**. Le workflow existant `browser-acceptance.yml` lance le script principal à chaque PR modifiant `scripts/browser-ci/` ; aucun workflow n'est modifié ici.

The existing workflow executes the same primary script automatically on PRs modifying browser tests. Its original 56 view observations remain intact; the new cross-module checks emit per-matrix PASS/FAIL results and fail the run on missing behavior. Existing Playwright a11y evidence is a separate 56-screen **probe**, not a WCAG certification.

## Verdict et portes de qualification / Gates

- **Développé / Developed:** tests ajoutés, qualité à établir par la CI exacte.
- **Testé / Tested:** uniquement après contrôle d'une exécution **sur le SHA exact** de la PR de qualification. La CI de #156 sur un autre SHA n'est pas transférable.
- **Recetté / Live accepted:** **non** — aucune installation réelle.
- **Fusionné / Merged:** **non**.
- **Publié / Released:** **non**.
- **Installé / Installed:** **non**.

**Blocages à attribuer / Owners:** UI C5–C10 à #156 ; mutualisation, reprise partielle et diagnostics C11 au chantier historique ; preuve d'identité inter-générations à #37 ; validation Recorder à #36 ; admission et absence d'écriture Énergie sans accord à #88. Un échec navigateur prouve l'écart du scénario synthétique, pas automatiquement sa cause ; conserver logs expurgés et SHA précis.

**Protection / Safety:** fixtures `SYNTH-*` et identifiants fictifs de test uniquement. Aucun jeton, compte, adresse réelle, historique réel, accès portail ou service distant.
