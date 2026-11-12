# Charte transversale UI/UX / Project-wide UI/UX guidelines

> **Décision utilisateur / User decision : 12 novembre / November 2026.**  
> **Portée / Scope :** toutes les interfaces ha-trybatec, panneau dédié et options natives lorsqu'elles sont sous le contrôle du projet / all project-controlled ha-trybatec interfaces, including the panel and native options.  
> **Statut / Status :** spécification validée ; l'implémentation et la recette restent à démontrer / approved specification; implementation and acceptance remain to be demonstrated.

**Références / References :** [Design system](DESIGN_SYSTEM.md), [#70](https://github.com/christophejaubert/ha-trybatec/issues/70), [#83](https://github.com/christophejaubert/ha-trybatec/issues/83), [#84](https://github.com/christophejaubert/ha-trybatec/issues/84), [WCAG 2.2](https://www.w3.org/TR/WCAG22/). Ces règles précisent les choix antérieurs sans annuler les protections métier de #36/#37/#81.

## Autorité des décisions et portée / Decision precedence and scope

**FR :** La palette canonique fixée par l'issue #70 le 10/11/2026 reste obligatoire. En revanche, sa consigne initiale de *simple recoloration sans changement de géométrie du logo* est remplacée, pour les travaux ultérieurs, par le **nouvel emblème approuvé** décrit dans [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) : symbole sans texte, trois formes circulaires entrelacées, séparation blanche, accents verts internes, aucun cercle vert extérieur. Cette clarification documentaire ne valide ni la génération des ressources graphiques, ni leur mise en production. Les anciennes spécifications restent consultables comme historique, pas comme normes concurrentes.

**EN:** The canonical palette from issue #70 (November 10, 2026) remains mandatory. Its earlier *recolor-only, unchanged-logo-geometry* instruction is superseded for subsequent work by the **later approved emblem** described in [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md): text-free symbol, three interlaced circular shapes, white separation, inner green accents and no outer green circle. This documentation does **not** prove that assets were updated, deployed or visually accepted. Older specifications remain historical records, not competing current rules.

**FR / EN :** Une règle documentée n'est ni une fonction implémentée, ni un contrôle CI réussi, ni une recette Home Assistant réelle. / A documented requirement is not implemented functionality, a successful CI run or real Home Assistant acceptance.

## FR — Règles obligatoires

### UI-01 — Dimensions indépendantes
Séparer systématiquement **état du contrôle** (Conforme / Anomalie détectée / Non vérifié / Non applicable), **disponibilité de l'opération** (Disponible / Bloquée), **caractère obligatoire ou facultatif selon le parcours**, **risque de l'action** (lecture seule / modification ordinaire / sensible / destructrice), et **provenance/qualification des données**. Aucune de ces dimensions ne doit servir de raccourci pour une autre. Un blocage de prérequis ou un paramètre facultatif absent ne constitue pas une panne générale.

### UI-02 — Pictogrammes et couleurs sémantiques
| État | Libellé | Picto recommandé (concept) | Couleur sémantique |
|---|---|---|---|
| Contrôle réussi | Conforme | Cercle avec coche | Vert succès |
| Problème réellement constaté | Anomalie détectée | Triangle d'alerte | Orange alerte |
| Données insuffisantes / contrôle non réalisé | Non vérifié | Cercle avec ? | Gris neutre **contrasté** |
| Contrôle hors contexte | Non applicable | Cercle avec trait | Gris secondaire |
| Gravité critique **démontrée** | Anomalie détectée + critique | Octogone d'alerte | Rouge danger |

La criticité est **un attribut supplémentaire**, pas un cinquième état de vérification. Un résultat inconnu ne peut jamais être converti en « anomalie » sans preuve. Si une analyse ne retrouve aucune donnée, expliquer **ce qui a été consulté** plutôt que présumer une défaillance. Ne pas utiliser la couleur seule : icône, libellé et explication lisibles. Les codes de couleurs et pictogrammes de fluides ne servent jamais de statut.

### UI-03 — Boutons : sémantique d'action, pas de statut
| Action | Rendu |
|---|---|
| Consulter, rechercher, vérifier, prévisualiser, naviguer, revenir | **Neutre actif**, contrasté et visiblement interactif |
| Action principale ordinaire / enregistrer | Neutre **renforcé** (hiérarchie, pas « vert = sûr ») |
| Confirmer une décision | Libellé explicite ; pas de vert automatique si l'action comporte un risque |
| Sensible (import Recorder, migration, basculement Énergie) | Avertissement de risque, description des conséquences et confirmation distincte |
| Destructive (suppression définitive) | Style danger rouge si effectivement destructif |
| Impossible actuellement | État réellement désactivé et explication accessible hors de la commande désactivée |

**Règle cardinale :** la couleur d'un bouton **ne reprend jamais automatiquement** la couleur du contrôle associé. Le vert Trybatec reste une **couleur de marque**, pas une preuve de sécurité. Le vert succès reflète un résultat vérifié, pas l'innocuité d'un clic. Un bouton neutre actif ne doit jamais ressembler à un bouton grisé/désactivé.

### UI-04 — États d'interaction et accessibilité
Différencier visuellement et fonctionnellement : actif, survol, focus clavier, pressé/sélectionné (si pertinent), chargement, désactivé. Conserver une bordure, une surface et un texte suffisamment contrastés sur les boutons actifs neutres ; focus visible. Désactivation native/effective (pas un simple changement d'opacité ou de couleur), raison du blocage accessible dans un texte adjacent. Ne pas dépendre uniquement d'une infobulle impossible à atteindre au clavier. Une opération en chargement empêche les doubles déclenchements ; annoncer le résultat après vérification.

### UI-05 — Couleurs métier et marque
Préserver la palette canonique et ses variantes de thème définies dans [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) : eau froide EF `#0A84D8`, eau chaude ECS `#C73A5C`, chauffage CET `#E0A126`, marque `#4E9E4A`. Le jaune/ambre CET n'est **pas une alerte** ; le vert du logo n'est **pas un statut de validation**. Les tokens succès/alerte/danger/neutre sont distincts des tokens marque/fluides. Vérifier **chaque couple texte/pictogramme et fond réellement rendu** en clair et sombre avant d'adopter de nouveaux hex.

### UI-06 — Messages et diagnostic
Distinguer succès confirmé, information, vérification requise, avertissement démontré, erreur confirmée et blocage de sécurité. Une donnée absente, non chargée, non encore analysée, non applicable ou un réglage facultatif absent ne justifient pas automatiquement un avertissement. Donner cause, périmètre vérifié, conséquence et suite accessible ; ne jamais annoncer un succès sur la seule acceptation d'une requête asynchrone. Pas de détail privé en journal ou dans la documentation.

### UI-07 — Parcours et navigation
Organiser par objectif utilisateur, pas par organisation interne du code. Parcours contextuels, prérequis uniquement pertinents, navigation retour, sélection de compte/logement/compteur et saisies conservées lors des déplacements. Pas d'ordre obligatoire artificiel entre fonctions indépendantes. Diagnostics avancés accessibles séparément, sans étape imposée en permanence. Une ouverture de page ou un lien de navigation n'exécute aucune opération sensible. Les liens de résolution ne sont affichés comme actifs que si leur destination est réellement implémentée ; ils doivent préserver l'identité du compte, du logement et du compteur physique, avec un chemin de retour. Un scan fournisseur ou un import reste une action explicite distincte.

### UI-08 — Formulaires
Libellés explicites, unités, caractère obligatoire/facultatif, validation locale et serveur adaptée. Messages à proximité du champ ; conserver les valeurs après erreur. Distinguer modifications non enregistrées et données sauvegardées. L'enregistrement ne modifie que les paramètres explicitement concernés, après vérification des états concurrents si nécessaire. Pas de formulaires imposant du JSON à un utilisateur ordinaire.

### UI-09 — Sécurité des actions
Pour import Recorder, migration, corrections d'historique, références Énergie, nettoyage ou suppression : **préparation → aperçu avant/après → prérequis et sauvegarde récupérable lorsqu'exigée → confirmation spécifique → exécution autorisée côté serveur → contrôle de persistance / retour arrière si pris en charge**. Pas de réécriture implicite des index fournisseur ni d'index fictifs présentés comme mesurés. L'ouverture d'une page ou d'un lien de consultation ne déclenche aucune écriture ni analyse fournisseur lourde implicite ; une recherche fournisseur nécessitant une action explicite affiche sa progression et ses limites.

### UI-10 — Hiérarchie et composants
Composants réutilisables et cohérents : titres, cartes, champs, bordures, boutons, badges, chronologies, tableaux et espacements. Éviter surcharges et fausses affordances (une carte n'est cliquable que si elle fonctionne comme telle, avec rôle et focus). Préférer les conventions natives Home Assistant lorsqu'elles répondent au besoin. Conserver les interfaces existantes pendant toute migration de présentation.

### UI-11 — WCAG 2.2 AA et ergonomie
Texte normal au moins **4,5:1**, texte large **3:1** ; contrastes non textuels fonctionnels **3:1**. Clavier complet, focus visible et non masqué, nom/rôle/valeur explicites pour lecteurs d'écran, reflow 320 CSS px, texte 200 %, espacement de texte. Cibles au minimum 24×24 CSS px selon exceptions WCAG 2.5.8, objectif de confort 44×44 si pertinent. Tester gris/monochrome, déficiences de vision des couleurs, mobile/bureau, clair/sombre et bascule à chaud ; respecter les préférences de réduction des animations. Un test automatique n'est pas un audit d'accessibilité complet.

### UI-12 — Valeurs, unités et provenance
Distinguer **valeur**, **disponibilité**, **statut de vérification**, **provenance**, **qualité** (mesurée, estimée, corrigée, non qualifiée). Conserver la précision et les horodatages source ; afficher les dates/nombres selon la locale et le fuseau Home Assistant. Monnaies avec codes **ISO 4217** (EUR), unités explicites (m³, kWh). Une unité vérifiée via choix manuel n'est pas décrite comme « certifiée par le fournisseur ». Ne pas qualifier une absence dans un snapshot comme absence définitive de relevé historique.

### UI-13 — Tokens communs
Centraliser les tokens de **marque**, **fluides**, **états**, **risques/actions**, **surfaces**, **textes**, **bordures**, **focus**, **sélection**, **désactivation**, **espacements** et **tailles** dans le design system. Chaque token doit avoir une variante lisible clair/sombre. Pas de couleur locale isolée qui contredit la charte. Ajouter les composants partagés seulement quand le code correspondant est effectivement développé et testé.

### UI-14 — Recette et non-régression
Tester au minimum états conforme/erreur/non vérifié/non applicable, opérations disponibles/bloquées, caractère facultatif, boutons actifs/désactivés/chargement, cas de compteurs en service/déposés, historique absent/non chargé/consulté, unités manuelles/API, navigation contextualisée, thèmes, langues FR/EN, clavier et accessibilité. Tester les actions sensibles sans écritures de production. Consigner **séparément** fonctionnalité implémentée, CI réussie sur le SHA exact et recette Home Assistant réelle validée.

### UI-15 — Gouvernance
Tout chantier d'IHM (issue, PR, revue) référence cette charte et [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md), documente les dérogations motivées et évite les régressions. Les issues [#70](https://github.com/christophejaubert/ha-trybatec/issues/70) (design), [#83](https://github.com/christophejaubert/ha-trybatec/issues/83) (parcours), [#84](https://github.com/christophejaubert/ha-trybatec/issues/84) (fiches compteurs) suivent des **applications ciblées** de règles communes. La spécification n'autorise pas à elle seule fusion, release, modification Home Assistant ni migration.

---

## EN — Mandatory project-wide guidelines

### UI-01 — Separate independent dimensions
Model check result (**Passed / Issue detected / Not verified / Not applicable**), operation availability (**Available / Blocked**), workflow optionality, action risk, data provenance and qualification **independently**. Missing optional settings or missing prerequisites are not a general system fault.

### UI-02 — Status icons and semantic colors
Use a **green check** for verified success, **orange warning triangle** for a demonstrated issue, **neutral grey question mark** for unverified information and **secondary grey minus** for not applicable. **Critical danger red** requires a *proven critical severity*, not an assumed fifth check state. Always accompany icons/colors with meaningful text. Distinguish missing snapshot fields from confirmed missing supplier history.

### UI-03 — Buttons convey action, not associated status
Use **high-contrast neutral enabled controls** for read, review, search, previews, navigation and ordinary saves; strengthen hierarchy without defaulting to green. Distinguish sensitive operations using risk messaging and separate confirmations; reserve destructive red for genuinely destructive actions. **Never inherit the status color into the action button.** Trybatec brand green never asserts that an action is safe; an active neutral button must not resemble a disabled control.

### UI-04 — Interaction states
Provide distinct enabled, hover, focus, pressed/selected when relevant, busy and disabled states. Disable functionally, expose accessible adjacent reasons and clear focus; don't rely solely on tooltip or opacity. Prevent duplicate submissions and confirm persistence before displaying success.

### UI-05 — Brand and fluids
Maintain the canonical EF `#0A84D8`, ECS `#C73A5C`, CET `#E0A126` and brand `#4E9E4A` colors. Fluid/brand colors are **not** semantic warning/success colors. Check actual foreground/background contrast across light/dark Home Assistant themes.

### UI-06 — Feedback and diagnostics
Separate verified success, information, verification needed, demonstrated warning, confirmed error and safety blocker. Do not convert unconfigured, unloaded or unverified data into false warnings. Include verified scope and actionable next steps. Never report an asynchronous request as completed before persistence is checked.

### UI-07 — User journeys and navigation
Group actions by user goal, show only relevant prerequisites, maintain account/dwelling/meter selection and return navigation, preserve edits. No artificial global step ordering. Keep advanced diagnostics available but not permanently mandatory. Opening a view is not an authorization for writes. Only implemented contextual destinations may appear as active links; preserve account, dwelling and physical meter context with a working return path. Supplier scans and imports require separate explicit actions.

### UI-08 — Forms
Explicit field labels, units, optional/required metadata, field-level errors, preserved draft values and separate persisted/unsaved states. Validate server-side and avoid requiring raw JSON from ordinary users.

### UI-09 — Sensitive actions
Separate preparation, preview, recoverable backup where required, explicit confirmation, backend authorization, execution and persistence/rollback verification. Never rewrite vendor indexes implicitly or turn estimates into real measurements. Navigation and view rendering must not trigger supplier scans or writes automatically.

### UI-10 — Layout
Consistent reusable controls, typography, spacing, borders, cards and navigation. Avoid noninteractive surfaces that look clickable. Prefer suitable Home Assistant native conventions and preserve existing functionality.

### UI-11 — WCAG 2.2 AA
Normal text contrast >=4.5:1, large text >=3:1, meaningful non-text UI >=3:1. Keyboard, screen reader semantics, visible/unobscured focus, 200% text scaling, 320 CSS px reflow; WCAG target 24×24 CSS px subject to exceptions, ergonomic preference 44×44. Test actual light/dark themes, mobile/desktop, greyscale and color-vision simulations, reduced motion. Automated tests do not replace human review.

### UI-12 — Data integrity and localization
Display value, availability, verification, provenance and data quality independently. Preserve raw timestamp and precision, use Home Assistant locale/time zone, explicit units and ISO 4217 currency codes (EUR). A manually verified unit is not automatically vendor-certified. An empty snapshot is not proof of absent historical readings.

### UI-13 — Shared design tokens
Centralize brand, fluid, status, action-risk, surfaces, text, borders, focus, selection, disabled, dimensions and spacing tokens in the design system, with usable light/dark variants. Avoid ad hoc per-page colors. Only claim a shared component is implemented when corresponding code exists and is tested.

### UI-14 — Testing and acceptance
Cover every check/operation state, optional features, interactions, retired/current meters, historical data not yet retrieved, unit provenance, contextual navigation, FR/EN, responsive themes, keyboard and accessibility. Do not write production data during tests without separate user approval. Track **implemented / CI passed on exact SHA / real HA accepted** distinctly.

### UI-15 — Governance
All UI issues and PRs must cite this document and the [design system](DESIGN_SYSTEM.md), disclose justified exceptions and preserve existing flows. #70, #83 and #84 cover distinct applications. The specification itself authorizes neither merge, release nor production changes.
