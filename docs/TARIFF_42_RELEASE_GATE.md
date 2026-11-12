# 🤖 Tarifs #42 — Contrat de livraison / Tariffs #42 — Release gate

**Cible / Target:** `0.3.4b1` (issue #45, D2–D6); **PR:** #118, brouillon / draft.  
**Coordination:** #120 (comptes neufs / new-account identities), #82 (migration historique exclue), #35 (parcours natifs déjà suivi).  
**Données / Data:** exclusivement fictives dans les tests ; aucune connexion ou installation de production.

## FR — État réel des critères de #42

| Critère | État technique démontré | Réserve avant recette métier |
| --- | --- | --- |
| TAR-01 sans JSON | Panneau #118 sans saisie JSON | **Ouvert** : `config_flow.py` conserve un champ JSON obligatoire ; lot natif coordonné avec #120 |
| TAR-02 exercices | Années libres 2000–2100, y compris sans relevé, années historiques et futures ; tests de l'éditeur | Recette utilisateur HA réelle |
| TAR-03 EF/ECS/CET | Formulaire et tests pour les trois fluides ; EUR/m³, EUR/m³, EUR/kWh | Recette réelle |
| TAR-04 dérogation physique | Clé opaque lot/fluide/numéro ; tarif effectif et origine ; calcul historique par compteur | **Ouvert sur les capteurs YTD** jusqu'au branchement de `tariff_ytd.py` dans `sensor.py` |
| TAR-05 édition | Ajout, modification, suppression, annulation locale et retour serveur ; tests synthétiques | Recette ergonomique réelle |
| TAR-06 statut | `provisional` et `approved` ; mentions « coût estimé ≠ facture » | Recette réelle |
| TAR-07 calculs | Historique par exercice et compteur ; **prévisualiseur YTD pur** avec contrôle des quantités et unités | **Ouvert** : preview YTD non branchée sur les capteurs |
| TAR-08 années exactes | Historique refuse le repli interannuel ; YTD pur marque explicitement tout repli antérieur | **Ouvert** : vérification du comportement YTD intégré |
| TAR-09 compatibilité | Préserve les anciens nombres nus et champs supplémentaires lorsqu'ils sont inchangés ; aucun changement du texte JSON lors d'une édition de dérogation | Test de persistance après véritable redémarrage/mise à jour HA |
| TAR-10 ergonomie | Tests Node et navigateur synthétiques FR/EN, bureau/mobile, clair/sombre | Recette HA réelle, clavier et accessibilité |
| TAR-11 accès | Panneau et commandes WebSocket protégés par `require_admin` ; tests d'intégration synthétiques | Tests compte non-admin en HA réel |
| TAR-12 effets indirects | Écriture ciblée d'options uniquement ; calculateur YTD strictement en lecture seule | Recette HA réelle / audit des effets sur capteurs |

Les critères sont **développés/testés** dans les limites indiquées ; aucune case de l'issue #42 ou #45 n'est automatiquement validée. Les anciennes valeurs restent dans la clé `annual_tariffs` ; les dérogations restent dans `annual_meter_tariffs`. Il n'existe pas de migration obligatoire des données tarifaires.

### Lot N — Options natives sans saisie JSON (non autorisé à être publié dans #118)

**Fichiers actuellement sous responsabilité #120 :** `config_flow.py`, `coordinator.py`, `panel_api.py`, `sensor.py` ; ne pas les modifier depuis #118. #35 a des parcours conservés sur `main` à ne pas perturber.

1. **Coordonner avec #120 et la MOE**, puis créer un lot distinct fondé sur le SHA intégré approprié. Préserver tous les chemins natifs existants, ainsi que les clés/options et les tarifs historiques.
2. Conserver le menu `settings` natif et fournir une voie **sans saisie JSON** vers le panneau administrateur de tarifs ; une alternative native graphique doit être étudiée si le panneau est indisponible. Ne jamais effacer les tarifs enregistrés lors d'une modification de synchronisation.
3. La règle **COMPAT-01 de #45 interdit de supprimer/rendre inaccessible un ancien champ**, alors que TAR-01/UI-10 interdit d'exiger la saisie JSON. Résoudre explicitement cette coexistence (par exemple un parcours graphique principal et un accès de compatibilité contrôlé) avant de modifier `config_flow.py` ; ne pas décider unilatéralement de supprimer le champ.
4. Tests d'options native FR/EN : ouvrir/retourner/annuler, saisir deux exercices EF/ECS/CET sans JSON, tarif et dérogation, non-admin, options préexistantes intactes, absence d'écriture au simple affichage et lors de l'annulation.

### Lot Y — Activation des estimations YTD (dépendance #120, non branché)

Le module pur `custom_components/trybatec/tariff_ytd.py` et les tests `tests/test_tariff_ytd_42.py` sont développés sur #118 **sans changer `sensor.py`**. Il rapproche chaque consommation fournisseur et son unité vérifiée de la consommation annuelle du même fluide, applique les tarifs spécifiques par compteur et les tarifs communs, et masque toute estimation non réconciliable. Un tarif antérieur YTD éventuel a un `source_year` et un drapeau `fallback_from_prior_year` ; le calcul historique refuse toujours ce repli.

L'intégration ultérieure, après coordination avec #120, devra :

- Réutiliser **les identifiants des entités annuelles existants**, sans création/migration d'entité et sans modifier les compteurs physiques ;
- Brancher le capteur `cost` sur `estimated_cost` et le capteur `price` sur `effective_unit_price` (qui devient indisponible pour un mélange de tarifs) ; afficher `source_year`, `fallback`, `coverage_warning`, `billing_status` en attributs ;
- Ne pas multiplier `annual.value` par un tarif commun lorsque les dérogations existent. Ne pas répartir un total agrégé arbitrairement ;
- Évaluer la neutralité sur les comptes historiques et la future modalité d'identités neuves ; aucune modification du Recorder, d'Énergie ni de l'unité source ;
- Tester l'actualisation des capteurs après une modification tarifaire, les redémarrages synthétiques, les compteurs remplacés, l'unité inconnue, les tarifs manquants et un mélange provisoire/approuvé.

**Risque résiduel immédiat :** tant que ce lot n'est pas intégré, le capteur YTD existant utilise un tarif commun et peut ignorer une dérogation physique. Il ne doit pas être présenté comme une estimation fiable dans ce scénario.

### Pré-requis d'intégration `0.3.4b1`

PR #118 et PR #120 : fusion **séparément autorisée** après vérification de toutes les CI sur leurs SHA exacts et coordination des lots N/Y ; conserver le verrou de migration historique #82. Exiger la réussite des contrôles obligatoires sur le `main` final, puis la recette réelle et l'autorisation de publication distincte. Une CI verte ne vaut pas recette.

---

## EN — Acceptance boundaries and dependent work

**Delivered in draft PR #118:** existing graphical editor (civil years 2000–2100, EF/ECS/CET in EUR/m³ or EUR/kWh, shared rates and optional physical-meter overrides, saved-rate prefill, edits, deletion, discard, provisional/approved, explicit estimates); no silent cross-year fallback in historical costs; preservation of untouched legacy numeric records and raw JSON when editing only meter overrides; synthetic FR/EN, validation, authorization and browser tests. No real HA or vendor data used.

**Not yet complete:**
- **TAR-01 / UI-10:** native `config_flow.py` still exposes a JSON options field. This is owned by #120 and must be changed only in a separately coordinated lot, respecting #45 COMPAT-01's preservation rule, #35's native navigation and existing saved options.
- **TAR-04 / TAR-07 / TAR-08 YTD:** existing `sensor.py` applies one default fluid rate. Pure `tariff_ytd.py` computes exact per-meter costs with fail-closed source/units/quantity reconciliation, but has not been connected to sensors because #120 owns that file.
- **TAR-09–TAR-12:** real Home Assistant browser, restart persistence, non-admin, accessibility, mobile and end-to-end operational acceptance remain pending.

**Next independent package N:** retain native OptionsFlow, add a no-JSON tariff journey and honor preserved legacy routes; obtain a documented decision where full native backward compatibility and a zero-JSON final interface conflict. Validate user navigation, old stored tariffs, no unintended writes and FR/EN.

**Next coordinated package Y:** on top of the accepted #120 sensor baseline, connect the tested read-only calculator to existing YTD sensor IDs; never apply the common rate to all physical meters when an exception is present, and never fabricate an effective single unit price when rates differ. Include explicit provenance and missing-data statuses.

**Release gate:** `0.3.4b1` is approved as a target version, **not authorized for merge, release or deployment**. Require separately approved merges, exact-SHA CI, final-main CI, independent real HA user acceptance, and a specific release authorization. Keep #42 open until all criteria are proven; never close automatically.
