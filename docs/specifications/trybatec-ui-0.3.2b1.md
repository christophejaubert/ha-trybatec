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

## UI-003 — Reprise exhaustive de l'ancienne interface Options Trybatec
- **Parité des réglages** : fréquence de synchronisation (jours/heures/minutes), seuil d'intervalles espacés, seuil d'index nul, tarifs annuels par fluide et par compteur, niveau de journalisation, unités des compteurs physiques et UUID facultatif.
- **Unités et UUID** : l'onglet Compteurs présente les unités explicitement fournies par l'API, celles des graphiques à titre indicatif, l'origine de la présélection, les unités autorisées par fluide et l'UUID de chaque compteur. Le choix est confirmé séparément. Une unité contradictoire avec l'API est refusée par le serveur ; aucune unité ne peut être inférée d'un graphique sans décision explicite. Les choix restent associés uniquement à la clé du compteur physique (lot, fluide, numéro).
- **Historique** : l'aperçu affiche les compteurs, lacunes et conflits par fluide, puis les lacunes, baisses d'index, conflits et bornes datées par compteur. La synthèse provient de la même analyse historique source que le flux Options ; elle est disponible après une prévisualisation explicite, sans trafic fournisseur à l'ouverture du panneau.
- **Revue des relevés** : acceptation, correction mesurée ou imputation comptable, rejet, report, sélection d'un intervalle précédent et lissage restent disponibles sous les mêmes restrictions de preuve, d'unité et de confirmation que l'ancien parcours.
- **Journalisation** : déplacer le niveau ERROR/WARNING/INFO/DEBUG dans un encart dédié « Journalisation et diagnostics » doté d'un enregistrement distinct. Le niveau est stocké par compte mais appliqué au journaliseur de l'ensemble de Trybatec ; le niveau le plus verbeux des comptes chargés prévaut. Aucune modification des autres intégrations.
- **Accès par l'engrenage** : le flux Options Home Assistant montre un lien local direct vers `/trybatec` lorsque le panneau est enregistré. Home Assistant ne propose pas ici de redirection automatique native. Les options existantes restent accessibles comme solution de secours, en particulier lorsque le panneau est indisponible, jusqu'à la validation complète de la parité ; le panneau expose lui aussi un accès au secours natif.
- **Persistance et concurrence** : réutiliser les options de l'entrée de configuration existante, protégées par l'empreinte complète des options. Refuser une sauvegarde issue d'un état périmé. Aucun second stockage, aucun enregistrement fournisseur, Recorder ou Énergie à la seule modification d'une unité, d'un UUID ou d'un niveau de journalisation.
- **Validation** : tests Python des bornes et contradictions, des UUID et du refus des états périmés ; recette navigateur synthétique pour les deux encarts de réglages et les compteurs en FR/EN, bureau/mobile, puis validation manuelle sur une installation de test avant tout retrait du secours natif.

## Recette minimale
Tests unitaires et navigateur synthétique FR/EN mobile/bureau, modes clair/sombre, bornes de dates et DST, unités, nombres, hauteurs de composants, parcours absent/présent, non-régression Recorder/Énergie/Options, et contrôles CI sur le SHA final. Aucune validation automatique ne remplace l'examen et l'autorisation explicite de fusion.

## UI-004 — Limites techniques et budgets historiques (validé)

- Sous « Réglages → Journalisation et diagnostics », afficher **en lecture seule**
  les limites réellement appliquées (tailles 16 Mio/64 Kio, 60/30/25/20 s
  selon endpoint, lignes/points, temporisations et tentatives).
- Les valeurs proviennent des constantes Python effectives, pas d'une
  duplication en JavaScript. Signaler honnêtement les plafonds globaux non définis.
- **Budgets candidats validés pour essais, non actifs tant que la recette
  de charge n'est pas terminée :** standard 120 s et 24 requêtes ; exhaustive
  600 s et 80 requêtes ; pause cible 500 ms ; 1 analyse par compte.
- Présenter séparément les limites effectives et les budgets proposés.
  Ne jamais qualifier « actif » un plafond non appliqué côté serveur.
- Prévoir progression non bloquante, annulation et reprise sûre, aucune
  historisation partielle présentée comme complète. Les contrôles UI
  correspondant à une fonction non développée ne doivent pas être affichés
  comme opérationnels.
- La correction du lecteur HTTP fragmenté et des tests de charge
  représentatifs conditionne toute activation des budgets proposés.
- Spécification complète : [Budgets et diagnostics historiques](trybatec-history-resource-guardrails-0.3.2b1.md).
