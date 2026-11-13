# 🤖 Qualification UI/UX — protocole réel / Live HA acceptance protocol

> **Recette réelle 0.3.4b1 / Real acceptance:** aucune plateforme HA de test n'est disponible. La recette en lecture seule et toute opération de production explicitement autorisée suivent [le protocole de production](PRODUCTION_ACCEPTANCE_0.3.4b1_FR_EN.md). Les scénarios de pannes, corruption, restauration destructrice ou concurrence artificielle décrits ci-dessous restent **réservés aux fixtures synthétiques**, sans toucher à l'installation réelle. / No HA staging system is available. Separately approved production acceptance follows the linked protocol; destructive fault, corruption and restore drills below remain synthetic-only. Aucun feu vert de release n'est déduit de ces tests. / This does not authorize release.


**Dépôt / Repo:** `christophejaubert/ha-trybatec` — issues [#70](https://github.com/christophejaubert/ha-trybatec/issues/70), [#83](https://github.com/christophejaubert/ha-trybatec/issues/83), [#84](https://github.com/christophejaubert/ha-trybatec/issues/84).  
**Références / References:** [Charte UI](UI_GUIDELINES.md), [Design system](DESIGN_SYSTEM.md), [WCAG 2.2](https://www.w3.org/TR/WCAG22/).

## FR — Mode d'emploi

**Cette procédure ne constitue pas une autorisation de se connecter à Home Assistant ou de modifier sa configuration.** Obtenir séparément l'autorisation de lecture réelle, identifier la version installée et effectuer les tests avec des données/confidentialités protégées. Ne jamais publier une capture non expurgée.

Pour chaque combinaison de `RECETTE_REELLE_56.csv` : noter version Home Assistant, version intégration, SHA exact installé s'il est vérifiable, terminal, navigateur, thème, langue, date, contrôleur et résultat. Les 56 cellules démarrent à **Non exécuté**. Une capture synthétique Chromium ne remplit aucune de ces cellules.

### Parcours sans écriture

1. Parcourir les **sept sections** : Vue d'ensemble, Compteurs, Historique et lissage, Tarifs, Énergie et versions, Diagnostics, Réglages.
2. Exécuter FR/EN × bureau/mobile × clair/sombre. Vérifier titres, informations, états, sélections et retours.
3. Tester Tab/Shift+Tab, Enter/Espace, focus visible et non masqué, navigation contextuelle et causes des commandes réellement désactivées.
4. Zoom texte 200 %, reflow 320 pixels CSS, espacement WCAG 1.4.12, tailles de cible (minimum 24 × 24 selon exceptions).
5. Vérifier les contrastes sur **couleurs compositées réellement affichées**, au moins 4,5:1 texte, 3:1 textes larges et éléments fonctionnels non textuels.
6. Tester niveaux de gris, simulations de déficiences de vision des couleurs, formes des séries graphiques, légendes et alternatives.
7. Tester VoiceOver et/ou TalkBack, en FR puis EN ; documenter noms, rôles, valeurs, annonces de changement d'état.
8. Basculer clair→sombre→clair à chaud et vérifier conservation du contexte et absence de régression.

### Parcours fonctionnels #83

- Distinguer « Conforme », « Anomalie démontrée », « Non vérifié » et « Non applicable » de l'opération disponible/bloquée et du caractère facultatif.
- Installation nouvelle/existante ; tarifs absents (facultatifs), unité inconnue, compteur déposé, versions Recorder manquantes, Énergie absente ; aucune fausse erreur générale.
- Contrôler la navigation des parcours historiques, tarifs, unités, versions Recorder, ajout groupé Énergie **sans lancer leurs actions de modification**.
- Vérifier que l'accès aux diagnostics est facultatif, que le statut bloqué précise la cause, et qu'aucune activation n'est présentée comme opérationnelle sans implémentation vérifiée.

### Fiches compteurs #84

Lire séparément valeur, provenance et qualification des cinq informations : dernier index disponible ; première observation connue ; dernière observation source ; date du dernier index exploitable ; statut/provenance de l'unité. Cas absent/non chargé/recherche infructueuse/compteur déposé/unité manuelle/API/conflit démontré.

Tester le maintien du compte/logement/`physical_key` en ouvrant une **consultation d'historique** et en revenant. Si le compteur disparaît, ne jamais afficher silencieusement celui d'un tiers. L'ouverture d'une consultation ne doit déclencher ni modification, ni scan fournisseur implicite.

### Sécurité

**Interdits sans décision distincte :** sauvegarde, migration, import Recorder, ajout ou remplacement Énergie, modification d'unité, correction de relevé, suppression et écriture fournisseur. Les prévisualisations lourdes ne se lancent pas implicitement. Les preuves réelles (identités, serials, volumes, adresses, logs bruts) restent privées ; seules des conclusions anonymisées sont publiables.

La recette est validée uniquement si chaque critère de chaque issue dispose d'une preuve datée, traçable et reliée à la version réellement installée. Ne pas clôturer #70/#83/#84 sur CI seule.

## EN — Live acceptance

This checklist **does not authorize connecting to, changing or testing a real Home Assistant installation**. Obtain separate authorization for any live read-only inspection. Record version, installed SHA if verifiable, language, device, browser, theme, date, tester, sanitized evidence and result for each of the 56 cases.

Cover all seven sections in FR/EN × desktop/mobile × light/dark. Verify keyboard order, focus visibility/occlusion, true 200% text resizing, 320 CSS px reflow, text spacing, touch target sizes, rendered contrast, greyscale and color-vision-deficiency simulations, VoiceOver/TalkBack, and hot theme switching. Test the #83 optional/blocked/unverified states and the #84 five meter-detail fields, provenance, exact physical meter context and safe return behavior.

**Read only.** Do not trigger real supplier scans, configuration saves, historical imports, Energy activation, destructive operations or migrations. Keep personal evidence private. Synthetic browser passes and source token arithmetic are not human HA acceptance.
