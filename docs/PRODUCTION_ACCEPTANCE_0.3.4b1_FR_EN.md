# 🤖 0.3.4b1 — Recette sur plateforme de production / Production acceptance

**Statut / Status: préparation, non exécutée / prepared, not executed.**
L'utilisateur ne dispose pas d'une instance HA de test. Les vérifications réelles de la candidate se feront sur sa plateforme de production, avec **autorisations distinctes** pour chaque action externe. Ce document n'autorise ni sauvegarde, ni installation, ni écriture Recorder/Énergie, ni restauration, ni fusion, ni release.

The user has no separate HA test system. Real acceptance must run on production with separate authorization for each external action. This checklist does **not** authorize backup, installation, Recorder/Energy changes, restoration, merging or publication.

## FR — Parcours contrôlé

| Porte | Étape et preuve | Effet ou risque | Autorisation |
|---|---|---|---|
| G0 | Candidate GitHub, exact SHA, CI, tests synthétiques, revue secrets, notes FR/EN | Aucune modification HA | Mandat GitHub |
| G1 | Audit en lecture seule : version HA, intégration, comptes existants, entités/statistiques, unités, versions, compteurs déposés et sources Énergie tierces | Consultations seulement ; données privées à conserver hors GitHub | Lecture seule dans le mandat |
| G2 | Sauvegarde native complète comprenant configuration, journal et Recorder ; vérification fin, intégrité et récupération possible ; capacité disque | Charge disque/CPU et nouvelles données de sauvegarde | **Autorisation distincte de sauvegarde** |
| G3 | Installation du SHA expressément validé et contrôles immédiats de démarrage ; aucune migration historique ni import implicite | Modifie la production, disponibilité et capteurs possibles | **Autorisation distincte d'installation** |
| G4 | Recette non mutante : sept écrans, FR/EN, bureau/mobile, clair/sombre, auth, unités, YTD, lecture historiques, filiation, aperçus Recorder/Énergie | Lectures uniquement ; certaines peuvent charger HA | Lecture dans le périmètre autorisé |
| G5 | Validation d'une écriture fonctionnelle **seulement après levée des verrous** : un acte à la fois, empreinte, confirmation administrateur, relecture et comparaison avant/après | Écritures durables, risques statistiques et sources tierces | **Autorisation distincte d'écriture Recorder** et **autorisation distincte de modification Énergie** |
| G6 | Examiner anomalies, journal et risques ; restaurer seulement si nécessaire, après comparaison des données depuis sauvegarde | Restauration peut perdre des changements et interrompre HA | **Autorisation distincte de restauration** |
| G7 | Compiler procès-verbal de recette, CI finale sur `main`, SHA/tag/notes FR/EN et décider de la publication | Publication publique irréversible d'un tag/release | **Autorisation distincte de publication** |

### Préconditions impératives avant G5

- Reconstitution #36 fondée sur les mêmes compteurs et unités : chaque bucket Recorder cible doit être relu, persistant et sans doublon ni version concurrente. Une opération `enqueue` ou un délai n'atteste pas de la persistance ; la **quiescence indépendante du writer** doit être démontrée avant tout rejeu.
- Inventaire #37 complet des compteurs actifs/déposés, périodes admissibles et références tierces ; aucune addition d'index physiques de générations différentes.
- État Énergie #88 admissible **indépendamment** : L6 ne doit pas utiliser d'indicateur d'interface non fiable comme preuve ; L7 doit disposer d'un adaptateur natif éprouvé, d'un journal durable, d'une sauvegarde récupérable et d'un rollback vérifié. Tant que L6 refuse et L7 est en lecture seule, **ne jamais activer l'écriture**.
- Vérifier dans la version HA installée le schéma `water`/chauffage et les unités. Ne jamais présenter des kWh thermiques comme des m³ de gaz.
- Capturer avant/après les empreintes des préférences, les séries, les versions et les références tierces. Un autre utilisateur ou processus qui a modifié l'état annule le plan.
- Refuser toute opération si l'on ne peut vérifier sauvegarde, compatibilité, exclusivité des séries et possibilité de reprise. Aucune migration #82, aucun nettoyage des anciens identifiants.

### Stop et reprise

Arrêter la séquence en cas de différence d'entités historiques, série en double, unité inconnue, lecture Recorder incomplète, writer potentiellement actif, sauvegarde échouée, empreinte divergente, journal non durable ou impact HA. Ne jamais lancer automatiquement un rejeu, rollback, redémarrage ou restore. Préparer une proposition de récupération et obtenir l'accord distinct.

**Règle de preuve :** garder les sauvegardes, journaux, captures et valeurs de production hors du dépôt public. Sur GitHub ne conserver que des conclusions FR/EN expurgées, non réidentifiables, avec date, SHA, scénario, résultat et limite. Les 56 scénarios d'accessibilité synthétiques ne sont pas une recette humaine.

**Sans plateforme distincte, il est interdit de provoquer en production des corruptions, crashs, restorations destructrices ou conflits artificiels pour valider les scénarios de reprise.** Les fautes sont testées sur doubles et fixtures synthétiques. Une sauvegarde seulement créée n'est pas une restauration éprouvée. Le risque résiduel doit être signalé et accepté explicitement, jamais réputé résolu.

## EN — Production-only acceptance safeguards

G0: GitHub exact-SHA CI; G1: private read-only inventory; G2: separately approved native full backup; G3: separately approved install; G4: read-only live smoke tests; G5: separately approved targeted Recorder/Energy writes only after source lineage, writer quiescence, Energy admissibility, durable journal and restorable backup are proven; G6: separately approved restoration if necessary; G7: separately approved publication after final main CI and acceptance.

Preserve old identities, external Energy sources, verified versions and Recorder sums; fail closed on uncertain units, concurrency, incomplete history or backup failures. Do not run destructive fault injection on production. Keep all private observations out of GitHub. A green CI or a successful read-only visit cannot establish a fully working Energy bulk-write feature or proven backup restoration. If D3/D7 cannot be satisfied, publication remains blocked until the user explicitly changes the scope.
