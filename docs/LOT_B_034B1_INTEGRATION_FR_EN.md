# 🤖 0.3.4b1 — Lot B intégré / Integrated batch B

## FR — Inventaire et niveau de preuve

**Base figée :** `main` `a1bd6d8558c8fe1cc13cadeb1ff4aaa20528dc53`.
**Sources :** #127 `f0f74f2`, #128 `ba7e25c`, #125 `60a571f`, #129 `299d913`, #130 `407f994`.
**Contribution :** PR #145 (brouillon), aucun merge. Les 44 chemins des cinq PR spécialisées sont disjoints ; leurs blobs sont composés sur la même base. Les deux nouveaux modules sont le pont pur `energy_bulk_lot_b_bridge.py` et son test transversal. Les contrôles du SHA intégré doivent être examinés indépendamment de ceux des PR sources.

Le pont appelle effectivement `make_b15_plan` (#36), `variants_preview`, `prepare_physical_continuity_37` et `prepare_energy_lineage_handoff_37` (#37), puis `reconcile_draft_provenance_l6` (#88). Il ne demande aucune écriture à Recorder, Énergie, à un portail ni à l'entité HA. Il n'est pas exposé comme endpoint ni enregistré à l'initialisation HA. Ses entrées ne doivent provenir que d'un backend natif authentifié, **jamais du navigateur**. Les empreintes attestent l'intégrité des enveloppes, pas leur exhaustivité.

### Matrice de preuves et conditions d'activation

| Domaine | Preuve disponible en code | Manque / preuve indispensable |
|---|---|---|
| Historique #36 | Relevés sources préservés, variantes mesurées/estimées/mixtes, bornes civiles et empreintes | Exhaustivité depuis le premier compteur de chaque logement/fluide, intervalles non mesurés décidés, ruptures et valeurs réelles auditées |
| Filiation #37 | Identités physiques, actifs/déposés/inconnus, montants physiques conservés, conflit de chevauchement refusé | Inventaire historique indépendant des générations, fenêtres de remplacement sans double compte, concordance avec #120 |
| Recorder L2 | Journal B15, relecture des buckets, classification des sur-échantillons et transactions incomplètes | Métadonnées et **toutes** les fenêtres persistées relues par backend ; vrai crash/redémarrage et restauration isolée ; quiescence writer indépendante avant reprise sélective |
| L6 | Contrats d'audit des sources, versions et préférences ; contradictions bloquées | Historique exhaustif, source consolidée unique, propriétés Recorder, exclusion complète des variantes V1/V2/V3 et des sources concurrentes/tiers |
| L7 | Prévisualisation, automate transactionnel abstrait, empreintes, journal préalable, refus en cas d'état mixte | Port HA natif **écrivant** audité, sauvegarde native vérifiée, reprise après vrai redémarrage et rollback sûr ; aucune écriture sans nouvelle autorisation |
| Énergie CET | Identité technique CET, attendu `kWh` ; compatibilité conditionnelle avec catégorie `gas` | Schéma exact de la version HA cible, compatibilité des métadonnées statistiques, accord explicite sur l'affichage « chauffage » dans une catégorie nommée « gaz » |
| Tarifs/coûts | Contrats du lot A non modifiés | Tarifs facultatifs pour les consommations ; coûts historiques impossibles sans source statistique et méthode validée |
| UI | Vue L7 autonome non branchée au panneau partagé | Parcours FR/EN, non-admin, mobile/bureau, accessibilité, aperçu/confirmation unifiée et retour vers assistant |
| Production | Aucun changement | Recette réelle sur une instance HA de test puis autorisations distinctes pour fusion, installation, écriture, migration éventuelle ou release |

**État courant :** `L6.admissible=False`, `L6.complete=False` ; L7 native port deny-all ; `Recorder.writer_quiescent` non prouvé ; `#88` reste **inclus comme obligation** de `0.3.4b1` et bloque la release tant qu'il n'est pas qualifié. La migration #82 et l'effacement des anciennes identités sont exclus.

### Règles de refus obligatoires

1. Inconnu ≠ absence constatée. Une enveloppe de lecture seule ou une couverture `qualified_bounds_no_gaps` ne prouve pas l'inventaire global.
2. Un index de compteur déposé ne peut jamais être ajouté à celui d'un nouveau compteur ; seules des consommations qualifiées sont agrégées.
3. Les jours civils sont évalués par les buckets statistiques et fuseau de la série, en testant les jours de 23 h et 25 h.
4. Aucune sélection Énergie tant qu'une version concurrente, une statistique tierce, un échantillon Recorder supplémentaire ou une unité inconnue subsiste sans preuve.
5. Un ancien journal L7 non terminal interdit une nouvelle transaction ; prévisualisation et empreintes doivent être relues sous verrou.
6. Sans preuve indépendante d'exclusivité du writer Recorder, **aucun rejeu sélectif** ; une réinstanciation du `Store` n'est pas une restauration HA.
7. L'ajout initial et le remplacement historique sont des opérations distinctes ; pas de réécriture des anciens IDs pour les faire passer pour de nouveaux.

### Chemin critique minimal pour #88

1. Fournir un collecteur de preuve historique côté backend à partir de sources bornées : générations actives/déposées depuis l'origine, empreintes et décisions de lacunes (sans données client dans GitHub).
2. Valider la métadonnée, `sum` et la totalité des buckets Recorder de la série consolidée retenue, puis l'absence de version/série concurrente et des références tierces.
3. Certifier par tests versionnés le schéma HA (EF et ECS = deux sources `water` nommées, CET = `kWh` avec catégorie thermique explicitement acceptée, sans conversion arbitraire).
4. Développer le port natif transactionnel L7 en module séparé et interdit à l'exécution hors environnement d'essai ; tester journal durable, sauvegarde/restauration, verrou, concurrence, rollback, idempotence et redémarrage HA réel isolé.
5. Brancher le parcours UI validé sur une **prévisualisation sans écriture** ; ne proposer la confirmation administrateur qu'après levée de tous les verrous et recette HA autorisée.
6. Rebaser/coordonner avec le lot A et la MOE #45, vérifier CI au SHA exact de la candidate réunifiée ; demander autorisations distinctes pour fusion puis release.

### Scénarios de recette non réputés exécutés

Énergie vide ; déjà configurée ; partiellement configurée ; source tierce ; deux versions V1/V2/V3 ; remplacement avec deux compteurs historiques ; période annuelle sparse ; saut d'heure ; unité CET invalide ; même série sous deux références ; préférences modifiées après aperçu ; crash entre écriture et journal ; écriture partielle ; absence du fichier de sauvegarde ; restauration SQLite isolée ; non-admin ; navigateur FR/EN mobile/bureau. Ces scénarios nécessitent une instance HA de test et les autorisations correspondantes. **Aucun résultat simulé ne vaut autorisation d'écriture de production.**

---

## EN — Evidence and delivery contract

PR #145 composes the non-overlapping source files of #127/#128/#125/#129/#130 over a verified `main` baseline without merging them. A new pure bridge invokes the existing #36 B15 plan, #37 physical lineage and #88 L6 diagnostics. It neither registers a Home Assistant endpoint nor writes Recorder, Energy, provider data or entity registries; only an authenticated trusted backend may prepare its inputs.

**Still unproven:** complete lifetime inventory of retired and active meter generations, reviewed measured/estimated/mixed gaps and overlaps, all Recorder statistic buckets and metadata, independent Recorder writer quiescence, V1/V2/V3 exclusivity, third-party sources, native Home Assistant backup/restore, a version-certified CET thermal-to-gas-category mapping, an audited native L7 writable adapter, and real Home Assistant/UI acceptance.

**Strict gates:** unknown is not absence; source fingerprints are integrity evidence only; a complete bounded date interval is not exhaustive provenance; no selective Recorder replay without writer quiescence; no initial Energy insertion through the replacement route; no combined physical indexes; no historical costs inferred from current prices. A nonterminal durable L7 journal blocks further transactions. Native L7 still denies every mutation and L6 remains `admissible=False`.

**Shortest qualification path:** native trusted historical inventory collector → exhaustive Recorder/readback and competing-version proofs → target-version Energy schema validation, including water and conditional thermal kWh → audited native transactional port and isolated real HA restart/backup/rollback tests → accessible single-preview/single-confirmation UI → final lot-A/lot-B reconciliation and exact-SHA CI → separate approvals for merge, production operations and release.

**Release policy:** #88 remains a required feature of 0.3.4b1, not silently dropped; failure to qualify it blocks the integrated release candidate. Historical migration #82 and legacy ID cleanup remain excluded. All observed consumption on this branch's tests must be synthetic.
