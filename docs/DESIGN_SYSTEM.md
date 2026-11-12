# Système de conception Trybatec — palette et accessibilité visuelle

> **Référence normative interne** : décision du 10 novembre 2026. Périmètre : toutes les interfaces de l'intégration Trybatec, ses pictogrammes, ses graphiques et ses fichiers de marque. Issue de recette : [#70](https://github.com/christophejaubert/ha-trybatec/issues/70), désormais rattachée à la préversion progressive [0.3.1b1](RELEASE_SCOPE_0.3.1b1.md). **Document de spécification, non preuve de conformité**.

## Palette canonique de marque

| Usage | Terme UI | Code interne | Couleur | Hex |
|---|---|---|---|---|
| Eau froide | CEF | `EF` | Bleu franc | `#0A84D8` |
| Eau chaude | CEC | `ECS` | Rouge framboise | `#C73A5C` |
| Chauffage | CTH | `CET` | Ambre doré | `#E0A126` |
| Identité Trybatec | — | — | Vert | `#4E9E4A` |

Les couleurs de référence sont **identiques** sur les logos, indépendamment du thème de l'hôte. Ne pas adapter les couleurs du logo aux modes sombre/clair. Pour 0.3.1b1, le **nouveau visuel approuvé** remplace cette ancienne consigne de non-refonte : symbole sans texte, trois formes circulaires entrelacées, séparation blanche, accents verts internes et **aucun cercle vert extérieur**. Pictogrammes : goutte EF, goutte ECS avec trois traits de chaleur, flamme CET. Les précédentes icônes de la PR #71 ne constituent pas le logo final validé. Pour les interfaces, les couleurs ci-dessous **dérivent** de la palette canonique afin de garder une lisibilité acceptable.

**Identification :** la couleur de fluide ne code **jamais** l'état d'un compteur. Les états « En service », « Déposé », « Inconnu », « Erreur » restent des données distinctes, avec libellés et états sémantiques propres.

## Variantes contrastées et paires à tester

| Catégorie | Texte/icône clair | Fond clair | Contraste calculé | Texte/icône sombre | Fond sombre | Contraste calculé |
|---|---|---|---:|---|---|---:|
| EF | `#075A9B` | `#E8F3FC` | 6,34:1 | `#65B8FA` | `#18334B` | 6,07:1 |
| ECS | `#A9234A` | `#FCE9F0` | 5,97:1 | `#FF7897` | `#43232F` | 5,52:1 |
| CET | `#805500` | `#FBF3DE` | 5,90:1 | `#FFD166` | `#3F3218` | 8,67:1 |
| Marque | `#286C32` | `#EBF7EC` | 5,80:1 | `#8ADD8F` | `#203A29` | 7,55:1 |

Calculs avec la luminance relative sRGB et la formule de contraste [WCAG 2.2](https://www.w3.org/TR/WCAG22/#dfn-contrast-ratio) ; les ratios ci-dessus concernent **uniquement** les couples de couleurs indiqués, pas tous les composants de l'interface. Les équivalents « texte couleur sur fond principal de l'hôte » doivent être recalculés sur les vrais thèmes Home Assistant.

### Tokens d'interface recommandés

```css
/* Exemple de références de conception — à intégrer selon le thème HA effectif */
:host {
  --trybatec-ef-brand: #0A84D8;
  --trybatec-ecs-brand: #C73A5C;
  --trybatec-cet-brand: #E0A126;
  --trybatec-brand-green: #4E9E4A;
  --trybatec-ef-fg: #075A9B;
  --trybatec-ef-bg: #E8F3FC;
  --trybatec-ecs-fg: #A9234A;
  --trybatec-ecs-bg: #FCE9F0;
  --trybatec-cet-fg: #805500;
  --trybatec-cet-bg: #FBF3DE;
  --trybatec-brand-fg: #286C32;
  --trybatec-brand-bg: #EBF7EC;
}
:host([data-trybatec-theme="dark"]) {
  --trybatec-ef-fg: #65B8FA;
  --trybatec-ef-bg: #18334B;
  --trybatec-ecs-fg: #FF7897;
  --trybatec-ecs-bg: #43232F;
  --trybatec-cet-fg: #FFD166;
  --trybatec-cet-bg: #3F3218;
  --trybatec-brand-fg: #8ADD8F;
  --trybatec-brand-bg: #203A29;
}
```

**Important :** le sélecteur `data-trybatec-theme` n'est qu'un exemple de contrat ; il faut le raccorder aux paramètres réels du thème Home Assistant et vérifier les bascules à chaud. Ne pas le supposer disponible automatiquement.

## Pictogrammes distinctifs et redondance

- EF : `mdi:water` + libellé « Eau froide ».
- ECS : goutte + indicateur de chaleur ou thermomètre (le pictogramme doit rester discernable d'EF) + libellé « Eau chaude ».
- CET : `mdi:fire` (flamme) + libellé « Chauffage » ; même concept graphique dans le nouveau logo.
- Un élément sélectionné comporte **au moins** : un fond distinct, un repère de bordure et un état textuel/accessible ; le contenu ne se décale pas lors de la sélection.
- Statuts toujours lisibles indépendamment des teintes (ex. « En service » reste vert même sur un compteur ECS rouge).
- Ne pas utiliser uniquement la couleur pour distinguer graphiques et séries : types de tracé/points, légende lisible, tableau de données en alternative.

## Critères d'accessibilité obligatoires (recette)

| Critère | Exigence de référence |
|---|---|
| WCAG 2.2 1.4.1 — Usage of Color | Ne jamais transmettre une information par la couleur seule. |
| WCAG 2.2 1.4.3 — Contrast (Minimum) | >=4,5:1 texte normal ; >=3:1 texte large. |
| WCAG 2.2 1.4.11 — Non-text Contrast | >=3:1 pour composants/états/graphismes porteurs de sens. |
| WCAG 2.2 1.4.4 — Resize Text | Jusqu'à 200 % sans perte de contenu/fonction. |
| WCAG 2.2 1.4.10 — Reflow | À largeur équivalente de 320 px CSS sans défilement bidimensionnel, hors exceptions applicables. |
| WCAG 2.2 1.4.12 — Text Spacing | Espacement personnalisable, pas de tronquage. |
| WCAG 2.2 2.1.1 / 2.4.7 / 2.4.11 | Clavier, focus visible, focus non masqué. |
| WCAG 2.2 2.5.8 | Cibles tactiles >=24 × 24 px CSS sauf exceptions ; viser 44 × 44 px quand pertinent sur mobile. |
| WCAG 2.2 4.1.2 | Nom, rôle, valeur et état accessible des commandes (dont sélection). |

**Objectif complémentaire de confort :** viser un contraste de 7:1 pour les données critiques lorsque possible. Cela n'est **pas** une affirmation de conformité AAA et ne dispense pas des tests.

Les tests doivent couvrir : modes clair/sombre réellement utilisés dans Home Assistant ; bascule de thème à chaud ; bureau et smartphone ; 200 % de texte ; zoom/reflow 320 CSS px ; valeurs longs numéros de compteurs ; clavier ; lecteurs d'écran ; monochromie ; simulations protanopie/deutéranopie/tritanopie. Les simulations ne reproduisent pas toutes les pathologies visuelles et ne remplacent pas les tests utilisateurs.

## Checklist de préversion 0.3.1b1

- [ ] Générer `icon.png` (256 px) et `icon@2x.png` (512 px) à partir du **nouvel emblème approuvé**, avec transparence et petits accents verts internes ; tester le rendu à petite taille sur fonds clair et sombre.
- [ ] Références du logo utilisées par le panneau, les intégrations et la documentation identifiées et cohérentes.
- [ ] Tokens clair/sombre utilisés partout (compteurs, listes, cartes, historique, tarifs, Énergie, diagnostics, réglages).
- [ ] Libellés et pictogrammes cohérents EF/ECS/CET, repères de sélection sans décalage.
- [ ] Tests automatiques de contrastes réels et vérifications humaines (PC et mobile).
- [ ] Tests FR/EN et non-régression : options actuelles, enregistrements, Recorder, Énergie, autorisations HA.
- [ ] Aucune affirmation d'accessibilité universelle ou de conformité globale sans audit.

La conformité effective doit être établie sur une révision de code et des captures des thèmes effectifs, pas sur les couleurs seules. Ne pas publier ni fusionner sur la seule base de cette checklist cochée.

## Références
- W3C, *Web Content Accessibility Guidelines (WCAG) 2.2*, Recommendation du 12 décembre 2024 : https://www.w3.org/TR/WCAG22/
- W3C, *Contrast ratio* : https://www.w3.org/TR/WCAG22/#dfn-contrast-ratio
- Issues de coordination : [#70](https://github.com/christophejaubert/ha-trybatec/issues/70), [#45](https://github.com/christophejaubert/ha-trybatec/issues/45), [#42](https://github.com/christophejaubert/ha-trybatec/issues/42).


---

## Extension UI/UX transversale — validée le 12 novembre 2026

**Source de vérité complémentaire : [UI_GUIDELINES.md](UI_GUIDELINES.md).** Ce design system définit les couleurs, composants, contrastes et pictogrammes ; la charte UI/UX définit les comportements et les risques. La palette du logo et des fluides ci-dessus reste inchangée.

### Tokens et interprétations sémantiques

| Usage | État / rôle | Repère |
|---|---|---|
| Contrôle conforme | Succès vérifié | Coche circulaire et **vert de succès** |
| Anomalie réellement détectée | Avertissement | Triangle et **orange d'alerte** |
| Anomalie critique démontrée | Gravité critique (complément de l'état « anomalie ») | Icône de danger et **rouge** |
| Non vérifié | Données ou analyse insuffisantes | Cercle avec ? et **gris neutre contrasté** |
| Non applicable | Contrôle hors contexte | Cercle avec moins et **gris secondaire** |
| Bouton de consultation / vérification | Action neutre **disponible** | Contraste fort, bordure explicite, focus visible |
| Bouton de modification ordinaire | Action principale neutre renforcée | N'implique **aucun succès ou innocuité** |
| Bouton d'opération sensible | Risque à exposer | Prévisualisation, prérequis et confirmation distincts |
| Bouton destructeur | Destruction effective | Danger rouge, confirmation spécifique |
| Bouton désactivé | Action indisponible | Désactivation technique et cause accessible |

Les valeurs hexadécimales des **nouveaux** tokens sémantiques ne sont **pas encore fixées** ; leur choix exige des paires texte/fond vérifiées sur les thèmes Home Assistant réels. Ne jamais réutiliser automatiquement \`--trybatec-brand-green\`, \`--trybatec-ef-*\`, \`--trybatec-ecs-*\` ou \`--trybatec-cet-*\` comme tokens de résultat, alerte ou risque.

**Séparer quatre dimensions :** résultat d'un contrôle ; disponibilité de l'opération ; caractère obligatoire/facultatif ; nature et risque de l'action. La couleur du bouton est choisie selon son **action** et ne recopie pas le statut voisin. Une commande active neutre ne doit jamais pouvoir être prise pour une commande désactivée. L'absence d'une donnée, d'une configuration optionnelle ou d'une analyse historique ne prouve pas une anomalie.

Les états requièrent **un texte et un pictogramme**, en plus de la couleur. Les boutons de navigation vers une résolution doivent rester des actions explicites, accessibles au clavier, et ne pas provoquer d'écritures ou de recherches fournisseur implicites. La provenance des valeurs (API, saisie manuelle, historique qualifié/non qualifié) doit rester lisible.

**Compatibilité documentaire :** la formule antérieure « éléments d'action et navigation avec la palette verte de marque » dans la spécification historique \`docs/specifications/trybatec-ui-0.3.2b1.md\` ne s'applique plus aux boutons de façon générale ; pour toute nouvelle implémentation, la présente règle et [UI_GUIDELINES.md](UI_GUIDELINES.md) prévalent. Cette clarification **ne modifie pas** le comportement du code déjà publié.

### Recette dédiée
- [ ] Couleurs sémantiques **séparées** des couleurs de marque et de fluides, y compris chauffage ambre.
- [ ] Paires de contraste vérifiées dans les **thèmes effectivement rendus** ; niveaux de gris et simulation de déficiences de perception des couleurs.
- [ ] Pictos/texte/états lisibles pour lecteurs d'écran ; commandes actives et désactivées non confondues.
- [ ] Bouton sensible jamais présenté comme « sans risque » par un vert par défaut.
- [ ] Vues Compteurs, Historique, Énergie, Tarifs, Diagnostics et Réglages cohérentes en FR/EN et mobile/bureau.
- [ ] Traces séparées de l'implémentation, des tests CI sur SHA exact et de la recette métier réelle.

## Project-wide UI/UX extension (EN) — approved November 12, 2026

**Companion source of truth:** [UI_GUIDELINES.md](UI_GUIDELINES.md). This design system covers colors, icons, contrast and visual tokens; the UI guidelines cover behaviors, actions and risks. Canonical brand and fluid colors above remain unchanged.

Status indicators: **Passed** = checked circle + success green; **Issue detected** = warning triangle + orange only when demonstrated; **critical** = additional proven severity + danger red; **Not verified** = question mark + contrasting neutral grey; **Not applicable** = minus circle + subdued grey. Severity is separate from the check-result category.

Buttons: use **contrasting neutral active styling** for read, examine, preview and ordinary save. A button's color communicates **action type/risk**, never automatically the color of a neighboring check. Trybatec green is a brand token, not a claim of harmlessness or approval. Truly disabled actions must be functionally disabled and explained; an active neutral button must remain unmistakably active. Destructive red is reserved for actual destructive operations. Sensitive operations require previews and explicit confirmations.

Create separate semantic tokens for success, warning, danger, neutral, actions and disabled states; **exact new hex values remain to be selected and tested** against actual light/dark Home Assistant surfaces. Brand and fluid tokens must not be automatically recycled as status tokens. Do not rely on color alone; expose icons, text and accessible semantics. Keep data provenance and unverified/history status distinct.

**Historical-document clarification:** the previous broad green-action recommendation in \`docs/specifications/trybatec-ui-0.3.2b1.md\` is superseded for future work by these rules; this does not retroactively change a release. Validate themes, grayscale, contrast, keyboard/screen readers, FR/EN, mobile/desktop and interaction states; distinguish implemented code, passing CI and real Home Assistant acceptance.
