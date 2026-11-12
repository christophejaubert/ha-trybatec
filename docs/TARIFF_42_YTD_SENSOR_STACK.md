# 🤖 TAR-04/07/08 — Raccordement YTD / YTD sensor integration

## FR — Contribution dépendante de #118 et #120

**Branche source :** `feat/42-ytd-sensors-on-120` créée à partir du SHA `8eb4f10c694da34afda4333adff0087c52f17d90` de #120.  
**Branche cible de la PR :** `feat/81-greenfield-safe` (#120).  
**Autre prérequis :** PR #118, qui contient déjà exactement le même module pur `tariff_ytd.py` et `tests/test_tariff_ytd_42.py`.

### Garanties

- Aucun changement aux identifiants uniques ni aux `entity_id` des capteurs YTD ; conserver la protection des comptes existants et les nouvelles identités stables propres à #120.
- Coût YTD : somme des coûts par compteur, tarif commun sauf dérogation exacte année + compteur ; jamais `total_agrégé × tarif_commun` lorsque des dérogations existent.
- Prix unitaire YTD : `unavailable` si les compteurs ont des tarifs ou statuts/origines incompatibles. Pas de prix fictif « moyen ».
- Rejet conservateur des unités non vérifiées, quantités inconciliables, doublons, tarifs manquants ; état et année de repli indiqués quand une estimation YTD emploie un tarif antérieur.
- Historique : aucune modification du calcul par exercice exact. Recorder, Énergie et portail : aucune écriture ni appel supplémentaire, aucune migration d'identité.
- Deux assertions strictement attendues en échec sur #118 deviennent des tests normaux lorsque `TrybatecAnnualSensor._ytd_tariff_estimate` est présent.

### Conditions de fusion ultérieure

1. **Ne pas fusionner ni activer** avant les autorisations distinctes nécessaires.
2. Après approbation de #118 et #120, réconcilier l'ajout du module/test identiques par contenu (aucune seconde implémentation en production), revoir le diff de `sensor.py` contre le SHA définitif de #120.
3. Exiger tests HA synthétiques, tests de rechargement/redémarrage, unités EF/ECS/CET, compteur déposé, scénarios provisoire/approuvé, année future et CI exacte.
4. Maintenir #42 ouvert jusqu'à la recette réelle et au parcours natif sans JSON.
5. Publier la preuve de branche, résultat CI, absence de changement HA et anomalies résiduelles dans #118/#45.

## EN — Stack and acceptance conditions

This draft depends on #120's **nonmigrating** greenfield entity model and #118's **identical** pure YTD calculator. The stack is based on #120 to avoid modifying its owned files in place. No second calculation subsystem is introduced: the duplicated tracked files must be reconciled as identical content when bringing both drafts together.

Existing YTD entity unique IDs are unchanged. Annual cost is estimated from verified physical quantities and exact meter-specific overrides, and a blended unit price is unavailable rather than fabricated. Prior-year YTD fallback, if used, is explicit in state attributes; historical exact-year costs are unchanged. Invalid units, missing rates and irreconcilable quantities fail closed. No real Home Assistant, vendor, Recorder or Energy changes are made.

Before merge: reconcile onto the final #120 and #118 SHA, re-run all required checks, verify no migration or duplicate entities, and perform a separately authorized real HA acceptance. Neither a green CI nor this PR authorizes merging or release.
