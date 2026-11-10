# Recette de prépublication — ha-trybatec 0.3.0b1

**Statut initial : NON VALIDÉE.** Ce document décrit les preuves attendues, sans autoriser d'import Recorder, d'activation Énergie, de nettoyage, de fusion ou de publication.

**Issues :** #36, #37, #42, #45. Marketplace #39 et pondération climatique #34 sont des chantiers distincts.

## Invariants de sécurité

- Interface additive : les sept choix de **Configurer / Options Trybatec** restent disponibles ; un panneau supplémentaire nommé exactement **Trybatec** apparaît dans la barre latérale.
- Un compteur physique retiré reste un appareil historique. Une ancienne entité technique indisponible n'est pas un compteur physique supprimé ni une preuve d'absence de référence.
- Index Trybatec : aucune réécriture. Une origine estimée est conservée séparément et n'est jamais déclarée « mesurée ».
- Recorder : aperçu, import versionné, vérification de persistance, activation Énergie et retour arrière demeurent cinq étapes contrôlées avec sauvegarde et confirmation.
- Énergie : une seule série représentant la même consommation doit être activée ; ne jamais additionner des index cumulatifs de compteurs différents.
- Tarifs : édition par année, fluide et éventuellement compteur, EUR/m³ ou EUR/kWh ; aucun JSON saisi par l'utilisateur, aucune facture inventée.
- Nettoyage : jamais automatique ; aucun retrait possible sans vérification des usages, sauvegarde et consentement distinct.

## Matrice des preuves — ne rien valider par supposition

| N° | Scénario | État au début de la recette |
| --- | --- | --- |
| C01 | Anciennes Options : sept entrées visibles FR/EN, mêmes écrans et réglages avant/après | Recette HA réelle requise |
| C02 | Panneau « Trybatec » ordinateur ≥ 1280 px et mobile 360–430 px, clavier, focus visible, lecteur d'écran | Recette HA réelle requise |
| C03 | Tous les écrans, erreurs, confirmations et états FR/EN sans traduction restante, y compris lors du changement de langue | **Non attesté** |
| C04 | Inventaire par lot+fluide+numéro physique : en service, déposé, inconnu, premières/dernières observations justifiées | CI partielle, réel à tester |
| C05 | Anciennes entités techniques et variantes *_2 séparées des appareils historiques ; aucune suppression sur simple indisponibilité | CI partielle |
| C06 | Références Énergie exactes, conservation des références actives, absence de double comptage | CI partielle, réel à tester |
| C07 | Audit **exhaustif** des usages Recorder, automatisations, scripts, YAML et dashboards ; sauvegarde et restauration avant nettoyage | **Bloquant, non implémenté exhaustivement** |
| C08 | Seuil zéro 0/1/N par jours réellement consécutifs, absence de données ≠ zéro, DST Europe/Paris | CI à inventorier, réel à tester |
| C09 | Revue des relevés : conserver, corriger date réelle avec preuve, imputation comptable, exclure et lisser le précédent intervalle exact | CI partielle, réel à tester |
| C10 | Lissage linéaire du seul résiduel entre bornes du même compteur ; priorité aux mesures ; total conservé | CI, cas réels à vérifier |
| C11 | Origine initiale manquante : date requise, index estimé 0 modifiable, approbation et révision explicites | CI, cas réels à vérifier |
| C12 | Remplacements et chevauchements : consommations consolidées, index de compteurs distincts non additionnés | CI, cas réels à vérifier |
| C13 | Versions Recorder V1/V2/V3, import isolé, readback, idempotence, incident, reprise et rollback | CI synthétique, staging à valider |
| C14 | Activation Énergie contrôlée eau/chauffage, unités vérifiées, rollback et conservation des sources tiers | CI synthétique, staging à valider |
| C15 | Tarifs sur deux exercices EF/ECS/CET, défaut et dérogation, édition sans JSON, persistance et absence de tarif inventé | CI partielle, réel à tester |
| C16 | Coûts historiques estimés exacts par année, provenance, unités et tarifs absents non inventés | CI partielle, réel à tester |
| C17 | API indisponible, données invalides, réauthentification, logs sans secrets, messages actionnables | Recette à faire |
| C18 | Reload, redémarrage et mise à jour depuis 0.2.0b17 sans perte d'historiques/options/décisions | Staging à valider |
| C19 | Sauvegarde couvrant Recorder vérifiable, restauration testée avant toute mutation sur instance réelle | Validation séparée requise |
| C20 | Toutes les CI obligatoires sur SHA exact PR **et main**, Python 3.13/3.14, HA runtime, HACS, hassfest, sécurité, Recorder | À constater sur SHA final |

## Protocole de vérification visuelle

1. Installer la branche candidate sur une **instance Home Assistant isolée**, sauvegardée et réversible, jamais sur la production sur la seule base de cette liste.
2. Capturer les sept menus Options avant/après et vérifier leurs parcours en français et en anglais.
3. Tester bureau et mobile, clavier, contraste, focus et lecteur d'écran. Relever chaque libellé encore français en anglais comme anomalie.
4. Tester EF, ECS, CET, compteur déposé et inconnu, unités, zéros, baisses, longues périodes et changement d'heure. Vérifier les index et dates réels sans les réécrire.
5. Comparer les consommations reconstituées et les totaux par compteur/logement. Garder les actions de simulation en lecture seule ; toute opération sur staging requiert sa propre validation et un retour arrière.
6. Rechercher les usages des entités anciennes dans Énergie, Recorder, tableaux de bord, automatisations et YAML. Une absence de référence dans un seul emplacement ne suffit pas pour supprimer.
7. Collecter pour chaque critère : preuve de test/capture, résultat, SHA, version HA, environnement et validateur. Retirer adresses, identifiants, secrets et informations privées avant toute publication dans GitHub.

## Passage à la release

**Publication interdite** si un critère bloquant n'est pas attesté. Après recette complète seulement : fusion des PR, contrôle vert du SHA final sur main, mise à jour du manifeste en 0.3.0b1, rédaction des notes exactes puis tag/release sur le même commit. La CI et les cases cochées dans GitHub ne valent jamais accord de publication ni validation visuelle.

**Aucune installation, migration ou suppression sur la production ne résulte automatiquement de cette matrice.**
