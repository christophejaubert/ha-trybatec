# Coûts annuels estimés dans le panneau Trybatec

Depuis l'onglet **Tarifs**, choisir l'exercice et demander **Calculer les coûts**. Le calcul n'est jamais lancé automatiquement, ni à l'ouverture du panneau, ni lors d'un changement de tarif.

Le service existant `trybatec.preview_costs` répond en lecture seule pour l'exercice choisi. L'année courante se termine à la date civile du jour en Europe/Paris. Les trois fluides sont demandés : EF (eau froide), ECS (eau chaude sanitaire), CET (chauffage).

## Résultats

Le tableau indique, par année, fluide et provenance :
- consommation considérée, unité normalisée m³ ou kWh ;
- tarif annuel et son origine, commun ou propre au compteur physique ;
- coût estimé en **EUR**, état du tarif (provisoire/approuvé/mixte) ;
- quantité et coût estimé par compteur lorsque les relevés et tarifs le permettent ;
- avertissement lorsque des périodes sont incomplètes ou des compteurs exclus.

Un coût reste **indisponible** si le tarif de l'exercice manque ; aucune reprise silencieuse du tarif d'une autre année, aucun montant de facture ou de charges votées n'est inventé. Les coûts de compteurs différents ne sont pas fusionnés sur la seule base du numéro de série ; le périmètre est lot + fluide + numéro physique.

## Portée de calcul

Ce premier aperçu est volontairement conservateur : seules les consommations journalisées à cadence vérifiée et les imputations comptables explicitement qualifiées sont chiffrées. Les intervalles espacés encore indéterminés, lissages et origines initiales estimées non présents dans le calcul de coût sont **exclus**, même lorsqu'ils apparaissent dans un autre aperçu de série Recorder.

Le mot « Approuvé » décrit uniquement le tarif saisi. Il ne certifie ni une facture, ni les charges de copropriété, ni l'exhaustivité des relevés.

## Sécurité

- Lecture de l'API et des options Trybatec ; aucune modification Recorder, Énergie, registre d'entités ou index source.
- Tout formulaire de tarif reste administrateur uniquement, avec sauvegarde et validation côté serveur.
- Les anciens tarifs `annual_tariffs` restent présents, sans changement de format ni de valeur dû à cette visualisation.
- Une publication reste subordonnée aux critères complets de l'issue #45 et à une recette sur Home Assistant réel.

Références : issues #42 et #45.
