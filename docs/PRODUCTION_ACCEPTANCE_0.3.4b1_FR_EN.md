# 🤖 0.3.4b1 — Recette sur plateforme de production / Production acceptance

**Statut / Status: préparation, non exécutée / prepared, not executed.**
**Décision business owner confirmée le 13 novembre 2026 : la publication de la bêta précède obligatoirement la recette réelle, puisque Home Assistant de production est l'unique plateforme disponible pour cette recette. Toute règle imposant une recette réelle avant la publication est non validée et retirée.** La qualification du code, la sécurité, la CI du SHA exact et les tests synthétiques restent exigés avant toute décision de publication ; les opérations réelles de production viennent ensuite et requièrent chacune leur autorisation distincte. Ce document n'autorise ni sauvegarde, ni installation, ni écriture Recorder/Énergie, ni restauration, ni fusion, ni release.

**Business owner decision reconfirmed on 13 November 2026: beta publication MUST precede live acceptance, because production Home Assistant is the only available acceptance platform. Any requirement for live acceptance before publication is invalid and removed.** Complete code, security, exact-SHA CI and synthetic qualification first; separately authorized merge, publication and installation then enable live acceptance, with distinct authorization for each production operation. This checklist does **not** authorize backup, installation, Recorder/Energy changes, restoration, merging or publication.

## FR — Parcours contrôlé (publication AVANT recette réelle)

| Porte | Étape et preuve | Effet ou risque | Autorisation |
|---|---|---|---|
| G0 | Développement fonctionnel sécurisé, contrôle de confidentialité, CI et tests synthétiques sur SHA exact, notes FR/EN et risques documentés | Aucune modification HA ; aucune recette réelle prétendue | Mandat GitHub existant |
| G1 | Fusion du SHA candidat approuvé dans `main` puis vérification du SHA et des contrôles applicables à `main` | Change le dépôt public ; pas la production HA | **Autorisation distincte de fusion** |
| G2 | Publication de la release bêta et du tag sur le SHA approuvé, avec notes FR/EN et limites visibles, **avant toute recette réelle** | Publication publique ; rend la version installable | **Autorisation distincte de publication** |
| G3 | Audit préalable en lecture seule : version HA, comptes, entités/statistiques, unités, générations physiques, versions Recorder et sources Énergie tierces | Consultations seulement ; preuves privées non publiées | Lecture seule dans le mandat |
| G4 | Sauvegarde native complète avant installation, contrôle de fin, d'intégrité, de capacité et de possibilité de récupération | Charge disque/CPU, nouvelles données sauvegardées | **Autorisation distincte de sauvegarde** |
| G5 | Installation de la version publiée expressément validée puis contrôles de démarrage ; aucune migration ou import implicite | Modifie la production ; risques de disponibilité et de capteurs | **Autorisation distincte d'installation** |
| G6 | Recette réelle **en lecture seule après installation** : sept écrans, FR/EN, bureau/mobile, clair/sombre, authentification, unités, YTD, historiques, filiation, prévisualisations Recorder/Énergie | Certaines lectures peuvent charger HA ; aucun changement des données | Lecture autorisée dans le périmètre |
| G7 | Recette de chaque écriture fonctionnelle uniquement après validation de ses garanties : empreinte, confirmation admin, relecture avant/après, exclusivité et reprise sûre | Écritures durables dans Recorder ou Énergie | **Autorisations distinctes pour écriture Recorder et modification Énergie** |
| G8 | Constat des anomalies et plan de correction ; restauration éventuelle seulement après évaluation de son impact | Une restauration peut perdre les changements intervenus après sauvegarde | **Autorisation distincte de restauration** |
| G9 | Procès-verbal de recette sur production, résultats et risques résiduels ; décision d'acceptation et, si nécessaire, préparation d'une version corrective | N'autorise ni déploiement ni release correctrice automatique | Décision business owner documentée |

**La recette réelle G6–G9 n'est jamais un prérequis à G2.** Le périmètre fonctionnel approuvé n'est pas réduit : avant G2, les parcours doivent être développés, leurs garanties techniques démontrées autant que possible par tests indépendants et simulations, et les protections fail-closed maintenues. Une fonction non qualifiée ne doit pas être présentée comme active ; sa qualification réelle et toute levée de verrou attendent G7 et leurs autorisations spécifiques.

### Préconditions impératives avant G7 (écritures réelles)

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

**Binding sequence: release BEFORE live acceptance.** G0: complete development, safety, synthetic exact-SHA CI and FR/EN release notes; G1: separately authorized merge and post-merge checks; G2: separately authorized beta release/tag **before** live acceptance; G3: private read-only production inventory; G4: separately authorized native backup and recovery readiness check; G5: separately authorized installation; G6: non-mutating live acceptance after installation; G7: separately authorized Recorder and Energy writes **only after** independent lineage, writer-quiescence, transactional admission, durable recovery journal and appropriate safeguards are proved; G8: incident assessment and any separately authorized restoration; G9: business acceptance record and possible corrective-release proposal.

**G6–G9 must NEVER block G2 merely because production-only acceptance has not yet taken place.** Complete the approved functional code and independent synthetic safety qualification before publication without claiming real operations have been validated. Retain fail-closed protections while prerequisites remain unproven; a green CI never authorizes a live write. A corrective release requires a new explicit publication decision.

Preserve old identities, external Energy sources, verified versions and Recorder sums; fail closed on uncertain units, concurrency, incomplete history or backup failures. Do not run destructive fault injection on production. Keep all private observations out of GitHub. A green CI or a successful read-only visit cannot establish a fully working Energy bulk-write feature or proven backup restoration. There is **no requirement for live acceptance before the initial beta release**.
