# Origines estimées — approbation et séries historisées

## Nature de l'information

Une origine estimée est une **hypothèse de consommation**, jamais un index mesuré ou un relevé Trybatec. Elle s'applique uniquement au **même compteur physique** (lot, fluide et numéro de série), entre une date de départ estimée et le **premier index source réellement observé**.

L'écran « Historique & lissage » du panneau « Trybatec » exige :

1. Un aperçu historique préalable couvrant le début proposé.
2. La vérification de l'unité **brute** de l'index (par exemple L ou m³ ; kWh, MWh ou GJ pour CET) ; le graphique du portail ne prouve pas cette unité.
3. Une date, un index estimé et un motif déclaré.
4. Un aperçu et une confirmation explicite avant la sauvegarde de l'hypothèse.
5. Une nouvelle confirmation pour réviser une hypothèse déjà approuvée.

Une sauvegarde d'hypothèse **ne déclenche pas** de modification de l'index brut, Recorder, tableau Énergie ou registre d'entités.

## Preuve et changements de données

L'approbation se rattache à une empreinte de la première observation exacte du compteur et de son **unité source**, afin que les nouveaux relevés postérieurs ne provoquent pas automatiquement une nouvelle approbation. La preuve du lot, du fluide, du numéro, de l'horodatage et de la valeur initiale reste impérative.

Une autre empreinte, calculée sur **l'ensemble des relevés et des décisions sources** du plan historique, lie la prévisualisation Recorder à son import. Toute correction de la source ou des décisions susceptible de changer la série oblige à produire un nouvel aperçu avant import.

L'origine estimée ne contribue **qu'à la variante lissée** du compteur et à la série logique consolidée qui la sélectionne. La variante brute du compteur continue à contenir ses consommations observées ; aucune paire d'index de compteurs différents n'est soustraite ou additionnée. Les unités des consommations résultantes sont normalisées (m³ ou kWh).

## Compatibilité entre versions

Les hypothèses éventuellement sauvegardées avec l'ancienne empreinte fondée sur **tous les relevés** restent dans leur stockage, mais leur sélection dans une série Recorder est **refusée** jusqu'à une nouvelle approbation explicite sous le schéma de preuve stabilisé. Aucune migration silencieuse ne requalifie ces hypothèses.

Une modification de la première observation, de l'unité source, un index nul non qualifié ou un conflit de relevés bloque également le plan. Le refus ne doit ni supprimer la décision historique, ni écrire une série partielle.

## Recorder et Énergie

- Le calcul de la variante et le prévisualiseur b15 sont en lecture seule.
- Un **import Recorder** est une action administrative distincte avec sauvegarde confirmée, empreinte du plan et contrôle de la persistance Recorder.
- Le **choix de la version Énergie** est ensuite une transaction distincte, avec sauvegarde confirmée et vérification des statistiques.
- Il ne faut jamais activer simultanément les variantes physique brute, physique lissée et consolidée lorsqu'elles représentent tout ou partie de la même consommation.

## Limitations de recette avant 0.3.0b1

Aucun fonctionnement graphique FR/EN ou mobile n'est attesté par les tests unitaires seuls. L'inventaire complet des dépendances et le nettoyage des entités techniques obsolètes nécessitent des contrôles et autorisations séparés sur une installation réelle. Une sauvegarde restaurable est nécessaire avant toute mutation sur l'installation.

Références : issues #36, #37 et #45.
