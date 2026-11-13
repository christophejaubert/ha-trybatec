# 🤖 Recette tarifs #42 / Annual tariff acceptance playbook

> **Recette réelle 0.3.4b1 / Real acceptance:** aucune plateforme HA de test n'est disponible. La recette en lecture seule et toute opération de production explicitement autorisée suivent [le protocole de production](PRODUCTION_ACCEPTANCE_0.3.4b1_FR_EN.md). Les scénarios de pannes, corruption, restauration destructrice ou concurrence artificielle décrits ci-dessous restent **réservés aux fixtures synthétiques**, sans toucher à l'installation réelle. / No HA staging system is available. Separately approved production acceptance follows the linked protocol; destructive fault, corruption and restore drills below remain synthetic-only. Aucun feu vert de release n'est déduit de ces tests. / This does not authorize release.


**Cible / Target:** `0.3.4b1`, TAR-01..TAR-12, UI-10 et COMPAT-01.  
**Statut / Status:** **À exécuter / Not executed**. Cette fiche n'est ni une autorisation d'installation, ni une validation de recette.  
**Références / References:** PR #118 (éditeur), PR #136 (YTD), PR #139 (options natives), PR #120 (identités neuves), PR #132 (installation/accès).

## FR — Préconditions et règles de preuve

1. **Aucune opération sur Home Assistant réel n'est autorisée par cette fiche.** Une décision distincte est nécessaire avant installation, sauvegarde/restauration, tests d'écriture dans l'instance ou toute mise à jour.
2. Constituer un compte de test fictif avec au moins deux compteurs EF, un ECS et un CET, dont un compteur déposé ; valeurs et dates entièrement **synthétiques**. Les identifiants et consommations réels ne doivent jamais être publiés.
3. Documenter l'environnement de recette : version HA, version intégration, commit SHA exact, rôle, thème, langue, appareil, date, et résultat `Non exécuté / Réussi / Échoué / Non applicable`.
4. Toute capture/trace déposée sur GitHub doit être expurgée des adresses, numéros de lot/compteur, `entity_id` privés, URL locales, noms d'utilisateur, secrets, consommations réelles et données réidentifiantes.

## FR — Parcours à valider

| Scénario | Manipulation ou contrôle | Attendu | Statut |
| --- | --- | --- | --- |
| N-01 | Options natives → Réglages, sans toucher aux tarifs | Aucun champ JSON obligatoire ; tarifs stockés inchangés | Non exécuté |
| N-02 | Options natives → Tarifs → exercice 2023, EF, commun | Champ numérique prérempli / création sans JSON | Non exécuté |
| N-03 | Même parcours pour ECS en EUR/m³, CET en EUR/kWh et exercice futur 2040 | Trois fluides indépendants ; unités affichées et persistées | Non exécuté |
| N-04 | Options natives → Avancé (ancien JSON) | Champ historique **toujours accessible**, jamais obligatoire | Non exécuté |
| N-05 | Modifier un montant sans cocher confirmation, puis annuler | Aucun changement d'options ni de capteurs | Non exécuté |
| N-06 | Enregistrer un tarif après confirmation explicite | Retour de confirmation ; valeur visible après navigation | Non exécuté |
| N-07 | Saisie négative, infini, NaN, 7 décimales, année 1999/2101 | Validation refusée, sans écriture | Non exécuté |
| N-08 | Dérogation EF sur un compteur physique, autre EF au tarif commun | Coût YTD pondéré par **quantité de chaque compteur**, pas par moyenne non vérifiée | Non exécuté |
| N-09 | Retirer la dérogation, consulter le même exercice | Tarif commun effectif ; aucune suppression d'identité | Non exécuté |
| N-10 | Deux tarifs physiques différents sur un même fluide | Prix unitaire YTD `unavailable` ; coût calculé si rapprochable | Non exécuté |
| N-11 | Écart entre somme physique et total fournisseur, unité CET non vérifiée | Coût indisponible + provenance/raison ; aucun montant inventé | Non exécuté |
| N-12 | Tarif d'année antérieure seulement | Historique sans repli interannuel ; YTD indique `source_year` et `fallback` | Non exécuté |
| N-13 | Tarifs provisoires vs approuvés | Aucune assimilation à une facture validée ; statuts compréhensibles FR/EN | Non exécuté |
| N-14 | Deux écrans concurrents, modification après empreinte périmée | Écriture rejetée ; aucun écrasement silencieux | Non exécuté |
| N-15 | Compte HA non administrateur : panneau et commande WebSocket tarifaires | Accès en écriture refusé **côté serveur**, même en contournant l'IHM | Non exécuté |
| N-16 | Rechargement de l'intégration puis redémarrage HA (environnement autorisé uniquement) | Tarifs anciens+nouvelles dérogations conservés, entités YTD non dupliquées | Non exécuté |
| N-17 | Comparer entités, Recorder, préférences Énergie avant/après tarifs | Pas d'import, suppression, réinitialisation ou redémarrage induit par une édition | Non exécuté |
| N-18 | Anciennes tables : nombre nu, métadonnées, années rares | Structure et données hors édition inchangées | Non exécuté |
| N-19 | Panneau personnalisé indisponible, options natives fonctionnelles | Éditeur de secours graphique opérationnel sans JSON | Non exécuté |
| N-20 | Interface native après fusion coordonnée de #120 et #132 | Installation/réauth inchangées, accès et notifications non régressés | Non exécuté |

### Matrice ergonomie

Exécuter **FR et EN**, **ordinateur et mobile**, **clair et sombre**, sur les **sept sections** du panneau et le parcours natif (au moins 8 configurations × 2 parcours). Tester tabulation, focus visible, zoom 200 %, reflow 320 px, lecture des messages de validation, annulation et confirmation, et liens de retour. Les captures synthétiques de la CI ne valent pas recette sur une instance HA authentique.

### Risques de migration et régression

- `annual_tariffs` et `annual_meter_tariffs` sont les seuls stockages tarifaires existants : aucune nouvelle migration ne doit être introduite.
- Vérifier les valeurs numériques anciennes et les métadonnées de tarifs non modifiés, le retrait d'une dérogation et les changements de réglages ordinaires.
- #120 peut introduire de nouveaux identifiants pour **comptes neufs**, mais ni ce lot ni la recette ne doivent migrer ou nettoyer les comptes historiques (#82 exclue).
- Tant que les PR ne sont pas intégrées et recettées, garder les scénarios ci-dessus **Non exécutés** et les issues ouvertes.

## EN — Test matrix and acceptance limits

**Status: NOT EXECUTED on a real Home Assistant installation.** Installation, backup, migration, Recorder/Energy writes and deployment require separate user approval. Use only fake accounts, synthetic meter keys and quantities in evidence that leaves the private test environment.

Perform N-01..N-20 above in FR/EN, desktop/mobile, light/dark, including normal settings without JSON, optional legacy compatibility, three utilities with correct EUR/m³ and EUR/kWh rate units, years with no source readings, saved common/physical overrides, remove/discard/explicit confirmation, invalid inputs, exact historical year and clearly labeled YTD fallback.

Verify that per-meter amounts reconcile with the verified aggregate; a blended price is unavailable for mixed rates. Ensure bad units, missing tariffs and inconsistent readings never produce fabricated costs. Reopen the options after an authorized reload and restart; compare saved options, existing entity identifiers and Recorder/Energy state. Test HA non-admin access **at the backend**.

The 8 synthetic browser variants and isolated HA CI are **technical evidence only**. Real user sign-off, separately authorized merges and the final exact-main CI are required before authorizing release `0.3.4b1`. Record failures as issues without disclosing any private meter/account/installation data.
