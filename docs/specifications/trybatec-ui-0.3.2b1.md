# Spécifications d'interface Trybatec 0.3.2b1 — recette

Document de portée générale, sans donnée d'installation individuelle. Cette version est une préversion ; aucune publication ou activation n'est autorisée par le seul document ou par les contrôles CI.

## COR-001 — Dates et heures localisées
- Présenter les dates dans la langue de l'utilisateur Home Assistant et dans son fuseau horaire configuré.
- Date calendaire seule par défaut ; indiquer l'heure uniquement si elle est utile à la désambiguïsation d'un relevé ou d'une opération. Ne pas interpréter minuit comme heure réelle de passage du releveur sans preuve.
- Préserver en interne l'ISO 8601, le fuseau source et l'intégralité des horodatages ; laisser aux champs `input[type=date|time]` les valeurs normalisées requises.
- Couvrir les détails de compteur, chronologies, périodes historiques, corrections, graphiques, coûts et périodes Recorder.

## COR-002 / COR-004 — Navigation Home Assistant et Trybatec mobile
- Bouton visible pour ouvrir le menu principal Home Assistant via l'événement `hass-toggle-menu`.
- Barre d'onglets réellement défilante, indicateur et chevron d'extension, défilement au toucher ; auto-présentation de l'onglet actif.
- Accessibilité clavier, focus visible, repères sémantiques et tailles de cibles tactiles adaptées.

## COR-003 — Compteurs physiques déposés
- Rapprocher uniquement des identités physiques exactes, dans le périmètre du compte, les bornes datées provenant de la lecture historique fournisseur.
- L'historique du fournisseur peut être absent du flux de relevé courant. Ne jamais assimiler un champ nul à la preuve d'absence de relevé historique.
- Une valeur historique brute est étiquetée comme non qualifiée lorsqu'elle n'a pas été validée pour Recorder ; absence de fusion implicite des index physiques.
- Ne pas inférer de date de pose/remplacement/dépose. Aucun enregistrement d'historique ou modification fournisseur au seul affichage.

## COR-005 — Accès au manifeste sans blocage
- Déjà fourni dans la PR prérequise #74 ; ne pas dupliquer son implémentation.
- La lecture de la version du manifeste ne doit jamais bloquer la boucle événementielle.

## EVO-001 — Parité eau froide, eau chaude, chauffage
- Les trois fluides participent au calcul de prévisualisation Recorder sans case isolée « Inclure le chauffage ».
- Les critères d'éligibilité, d'unité, de sauvegarde, de contrôle de persistance, de confirmation et de gestion de conflits restent obligatoires pour chacun.

## EVO-002, EVO-004 et UI-001 — Charte visuelle
- Éléments d'action et navigation avec la palette verte de marque ; couleurs EF/ECS/CET propres aux fluides dans les listes, titres et pictogrammes.
- États métier et erreurs séparés des couleurs de fluide. Titres accessibles en thèmes clair/sombre, mobile et bureau.
- Respecter WCAG 2.2 AA, sans prétendre à une validation sans contrôle dynamique.

## EVO-003 — Durée de synchronisation
- Présenter trois champs (jours 0–7, heures 0–23, minutes 0–59) ; durée totale admise 60–10 080 minutes.
- La configuration HA continue d'utiliser le champ existant `poll_minutes`, sans changer les données ni les automatisations.
- Préremplir les composantes à partir du total, contrôler les bornes avant sauvegarde et conserver les réglages d'origine si l'utilisateur annule.

## EVO-005 — Santé et préparation
- L'accueil distingue les compteurs courants synchronisés, observations historiques manquantes, versions Recorder, références Énergie, tarifs facultatifs et portée partielle des audits techniques.
- Proposer des liens contextuels vers les écrans concernés, sans actions automatiques ni fausses alertes sur les fonctions facultatives.
- Ne pas interpréter 0 entité indisponible comme 0 sujet à auditer.

## UI-002 — Affichage des quantités
- Séparer les milliers selon la locale ; pour `fr-FR`, utiliser l'espace fine insécable U+202F et la virgule décimale.
- Ne pas arrondir ou muter les index sources ; conserver séparément leur précision originale et les unités.

## EVO-006 — Disponibilité du remplacement d'une version Énergie
- La sélection d'une ancienne source et d'une nouvelle version est désactivée visuellement et fonctionnellement en l'absence de l'un des deux prérequis.
- La version cible doit avoir été importée puis vérifiée par Recorder ; une source Trybatec doit déjà être référencée dans Énergie pour autoriser son remplacement.
- La première activation d'une source Énergie est un parcours distinct, sans remplacement implicite ni validation par défaut.
- Les boutons de prévisualisation et d'écriture restent inactifs tant que l'opération ne peut pas être instruite.
- La confirmation explicite et la sauvegarde restent obligatoires ; aucun import ni basculement déclenché par l'ouverture de l'écran.

## Recette minimale
Tests unitaires et navigateur synthétique FR/EN mobile/bureau, modes clair/sombre, bornes de dates et DST, unités, nombres, hauteurs de composants, parcours absent/présent, non-régression Recorder/Énergie/Options, et contrôles CI sur le SHA final. Aucune validation automatique ne remplace l'examen et l'autorisation explicite de fusion.
