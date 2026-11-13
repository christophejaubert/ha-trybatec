# 🤖 Trybatec — guide d'installation et de sécurité / Installation and safety guide

**Périmètre / Scope :** intégration personnalisée **non officielle**, en bêta expérimentale. Vérifier la version effectivement publiée sur [GitHub Releases](https://github.com/christophejaubert/ha-trybatec/releases) ; le contenu de `main` et les PR ouvertes ne constituent pas une version installable et qualifiée. Aucune affiliation ni approbation par Trybatec, Home Assistant ou HACS. / Unofficial experimental custom integration; check the actual published version on GitHub Releases. The default branch and open PRs are not proof of a released or qualified feature. Not affiliated with or endorsed by Trybatec, Home Assistant or HACS.

**Statut / Status (13 novembre / November 2026) :** ce guide documente les parcours disponibles ou prévus ; il ne certifie pas un essai d'installation ni une compatibilité minimale. Les fonctionnalités #36 (historique/Recorder), #37 (filiation) et #88 (Énergie groupée) restent soumises à leur qualification indépendante. Ne pas interpréter leur présence partielle dans le code comme une fonction sûre en production. / This guide does not certify installation testing or a minimum supported Home Assistant version. #36, #37 and #88 require independent acceptance.

[Préparation Marketplace / Readiness checklist](MARKETPLACE_READINESS.md) · [Sécurité / Security](../SECURITY.md) · [Actions disponibles / Action definitions](../custom_components/trybatec/services.yaml)

## FR — Installation, configuration et utilisation

### Prérequis et mode de distribution

- Disposer d'un compte **personnel et autorisé** sur le portail Trybatec, d'un Home Assistant administré par vous et d'une **sauvegarde récupérable** de la configuration et de Recorder. Aucune API publique contractuelle Trybatec n'a été confirmée.
- Aucune **version minimale Home Assistant validée** n'est déclarée pour l'instant dans `hacs.json`. L'interface Marketplace existe depuis Home Assistant 2026.11 ; pour les versions antérieures, consulter HACS. Cela n'affirme pas la compatibilité de l'intégration avec ces versions.
- Le dépôt n'est **pas référencé** dans le catalogue public à la date du présent audit. Une installation depuis un dépôt personnalisé est distincte d'un référencement officiel.
- Les préversions peuvent nécessiter l'activation de l'option *Pre-release*. Vérifier l'étiquette et les notes de chaque GitHub Release avant toute installation ou mise à jour.

**Depuis Home Assistant 2026.11 (Marketplace)** : ouvrir *Paramètres → Marketplace*, ajouter le dépôt via un lien ou le menu des dépôts personnalisés, sélectionner la catégorie **Intégration**, puis `christophejaubert/ha-trybatec`. Vérifier la release choisie, activer les préversions si nécessaire, installer, puis suivre la demande de redémarrage ou de réparation indiquée par Home Assistant. La disponibilité exacte des commandes dépend de la version installée.

**Depuis HACS (versions antérieures)** : ouvrir HACS → dépôts personnalisés, saisir `https://github.com/christophejaubert/ha-trybatec` comme **Intégration**, sélectionner une release compatible si elle existe, installer et redémarrer si demandé. Une intégration absente de la liste des intégrations peut nécessiter une actualisation du navigateur.

**Installation manuelle** : copier **uniquement** le dossier `custom_components/trybatec/` de la release souhaitée dans `<CONFIG>/custom_components/trybatec/` et redémarrer Home Assistant. Ne pas mélanger des fichiers provenant de versions différentes. Une mise à jour ne doit pas être assimilée à une migration des statistiques.

### Première connexion, perte d'accès et réauthentification

1. Ouvrir *Paramètres → Appareils et services → Ajouter une intégration → Trybatec (Unofficial Beta)*, puis saisir l'identifiant et le mot de passe du compte autorisé. La connexion utilise le portail directement depuis l'hôte Home Assistant.
2. En cas d'un logement unique et identifiable sans ambiguïté, la découverte peut terminer la configuration. Si plusieurs possibilités sont détectées, un repli contrôlé peut demander l'URL HTTPS **complète** de la page *Indexes* du compte connecté. Ne pas transmettre cette URL dans une issue publique.
3. En cas d'erreur d'authentification, d'accès refusé, de réponse fournisseur incorrecte ou d'indisponibilité réseau, corriger la cause sans essayer de contourner les permissions du portail. Un compte multi-copropriétés n'est pas garanti par le parcours automatique actuel.
4. Si Home Assistant présente le parcours **Réauthentifier**, fournir les identifiants valides **du même compte**. Ne pas supprimer/recréer l'intégration comme première mesure : cela peut changer des références locales. Vérifier les options, unités et entités après reconnexion. La conservation complète dans tous les cas nécessite une recette.

### Compteurs, unités et relevés historiques

- Ouvrir les **options de l'intégration** et vérifier séparément l'unité de chaque compteur physique. EF (eau froide) et ECS (eau chaude sanitaire) peuvent être présentés en `m³` après validation d'une source compatible ; CET (chauffage) n'est en `kWh` que si **l'unité de l'index d'origine est vérifiée**. Un affichage de graphique en kWh ne prouve pas l'unité brute des index.
- Ne pas sélectionner deux anciennes/nouvelles entités représentant la **même** consommation. Un remplacement physique de compteur n'autorise pas à additionner des index cumulés, ni à supprimer une série ancienne.
- Les aperçus historiques sont **en lecture seule**. Les données disponibles peuvent comporter des lacunes, diminutions, chevauchements et périodes à relevés espacés. Les requêtes et réponses sont bornées ; une extraction partielle ne prouve pas l'exhaustivité du portail.
- Lissage et corrections sont des **propositions ou décisions explicitement attribuées** ; elles ne constituent pas de nouvelles mesures du fournisseur. Une date de relève annuelle ne devient pas une preuve de consommation quotidienne.
- Toute importation vers Recorder exige une **prévisualisation, une sauvegarde récupérable, une confirmation administrateur et une vérification de la persistance**. Une tâche mise en file n'est pas une série enregistrée. Ne jamais relancer automatiquement une opération en attente ou incertaine.
- La chaîne de consolidation #36/#37 et l'ajout groupé Énergie #88 ne sont **pas déclarés opérationnels pour une utilisation générale**. Conserver les sources Énergie préexistantes tant que l'identité, la continuité, les unités, les doublons et la restauration ne sont pas vérifiés.

### Tarifs, coûts et tableau Énergie

- Saisir les tarifs de **l'année civile exacte**, par fluide, en utilisant les formulaires disponibles dans la version installée ; les valeurs de démonstration ne sont pas des tarifs réels. Les tarifs d'eau sont exprimés en `EUR/m³`, ceux de chauffage en `EUR/kWh` **uniquement** si le compteur et la règle de facturation utilisent ces unités.
- Les coûts et consommations estimés ne sont pas des factures ou un relevé comptable certifié. Ne pas convertir une unité de répartition de chauffage en kWh sans justificatif.
- **Aucune importation Recorder, migration d'identité ou bascule du tableau Énergie ne doit être supposée automatique lors d'une mise à jour.** Avant toute activation manuelle, contrôler les sources concurrentes, les références existantes, la sauvegarde, le résultat de prévisualisation et les contrôles post-écriture. Les fonctions en cours de développement ne doivent pas être recommandées comme prêtes.

### Mise à jour, désinstallation, confidentialité

- **Avant la mise à jour :** sauvegarde complète et récupérable, inventaire privé des entités et statistiques sélectionnées, lecture des notes de la release, vérification de la version Home Assistant. **Après :** vérifier démarrage, unités, permissions, entités, références Énergie et statut Recorder avant tout import.
- **Désinstallation prudente :** retirer la configuration de l'intégration depuis *Appareils et services* si nécessaire, puis retirer les fichiers du dépôt via Marketplace/HACS ou manuellement selon la méthode d'installation. **Ne pas supposer** que les statistiques externes Recorder, les références Énergie, les décisions dans `.storage` ou les anciennes entités sont supprimées ou conservées intégralement ; contrôler leurs effets avec une procédure de sauvegarde/restauration distincte. Ne jamais purger des historiques sur la seule base d'un retrait de fichiers.
- Les identifiants sont stockés dans les entrées de configuration Home Assistant et peuvent se trouver dans les sauvegardes ; les sessions du portail et métadonnées de compteur sont sensibles. Les échanges avec le fournisseur utilisent **HTTPS vers `portail.trybatec.fr`**, sans relais tiers déclaré par l'intégration. Aucune fonctionnalité d'écriture distante dans le portail n'est revendiquée.
- Ne publier **aucun** mot de passe, jeton, URL de compte, identifiant de logement/compteur, relevé, facture, capture non anonymisée ou journal brut sur GitHub. Préférer des scénarios synthétiques. Signaler les vulnérabilités par un canal privé vérifié (voir [SECURITY.md](../SECURITY.md)).
- Le service est dépendant du portail cloud, dont les points d'accès ne sont pas documentés contractuellement. Les conditions d'utilisation, la légitimité des appels et l'utilisation de signes de marque sont à valider avant diffusion large. Support et maintenance non garantis.

### Dépannage rapide

| Situation | Vérification sûre |
|---|---|
| Intégration absente après installation | Contrôler dossier, release, redémarrage demandé et actualisation du navigateur |
| Identifiants rejetés ou accès refusé | Tester les droits sur le portail avec votre propre compte ; utiliser la réauthentification proposée |
| Plusieurs logements ou sélection ambiguë | Utiliser seulement le repli URL officiel proposé, sans choisir arbitrairement un lot |
| Unité inconnue ou incohérente | Vérifier l'échelle de l'index réel ; laisser la statistique indisponible tant que non confirmée |
| Historique lacunaire | Consulter l'aperçu et ses limites ; ne pas extrapoler la couverture absente |
| Sommes inattendues dans Énergie | Contrôler sources en double, générations de compteurs et versions Recorder ; ne pas effacer les anciennes données |

## EN — Installation, configuration and use

### Prerequisites and distribution

Use only your **authorized personal Trybatec portal account**, an administrator-controlled Home Assistant instance and a **recoverable backup**, including Recorder. The Trybatec endpoints are not backed by a confirmed public API contract. No tested **minimum Home Assistant version** is declared in `hacs.json`. The Marketplace interface is available from Home Assistant 2026.11; older systems may use HACS, **without any implied compatibility guarantee for this integration**.

This repository is not yet in the public catalog. For Home Assistant 2026.11+, go to *Settings → Marketplace*, choose the link/custom-repository flow, add `christophejaubert/ha-trybatec` as an **Integration**, and inspect the intended GitHub release. Enable **Pre-release** only if you intentionally want the experimental build. Install and follow any required restart/repair instructions. On earlier Home Assistant systems with HACS, use *Custom repositories*, paste `https://github.com/christophejaubert/ha-trybatec`, select **Integration**, install the selected release and restart if instructed. For manual installation, copy only the matching-release `custom_components/trybatec/` folder to `<CONFIG>/custom_components/trybatec/` and restart.

### Setup, authentication, reauthentication

1. Open *Settings → Devices & services → Add integration → Trybatec (Unofficial Beta)*. Enter the authorized portal username and password; traffic goes directly from Home Assistant to Trybatec.
2. Automatic discovery requires an unambiguous authorized housing. Only when discovery is ambiguous, a controlled fallback can ask for the full **HTTPS Indexes-page URL** already available inside your portal account. Do not share it publicly.
3. A rejected login, denied access, service outage or unexpected response should be addressed at the source. The current automatic workflow does not guarantee multi-property account support.
4. When Home Assistant offers **Reauthenticate**, enter credentials for the **same** portal account. Avoid deleting and recreating the entry before inspecting its stored options and entity references; full persistence across all failure modes still requires acceptance tests.

### Units, provenance, history

Verify the **raw index unit separately for each physical meter**. Cold and hot water may be normalized to `m³` after validating an appropriate source unit. Heating can be normalized to `kWh` **only when its raw index scale is verified**; a chart label alone is insufficient. Do not add cumulative indexes from different physical generations or select competing entities/statistics for the same consumption.

Historical previews are read-only, bounded, and may reveal gaps, declines, conflicts or sparse intervals; no query proves complete coverage of the undocumented vendor database. Smoothing or accounting attribution, where offered, is distinct from vendor-observed readings. Recorder imports must have a recoverable backup, non-destructive preview, explicit administrator confirmation and verified persisted statistics; queueing alone is not verification. #36/#37 historical consolidation and #88 bulk Energy configuration are **not endorsed as generally production-ready** until separately qualified.

### Prices and Energy

Enter civil-year-specific tariffs in the interface offered by the installed release. Water rates use `EUR/m³`; heating rates use `EUR/kWh` **only** for verified compatible metering and billing. Estimated consumption or costs do not establish audited charges. Existing Energy sources and Recorder generations must not be double-counted. Installation or upgrade does **not** constitute permission to migrate identities, write Recorder data, or change Energy preferences.

### Update, removal, security and troubleshooting

Back up Home Assistant, document privately the selected Energy/Recorder references, and read the release notes before each upgrade. Afterwards verify startup, account access, source units, sensors, and historical references. To remove the integration, delete its config entry through *Devices & services* when appropriate and remove the repository files using Marketplace/HACS or the manual procedure. **Do not assume** that external Recorder statistics, Energy preferences, persisted review choices or legacy entities are either purged or perfectly preserved. Evaluate their actual state before a separately approved cleanup.

Portal credentials can reside in Home Assistant config entries and backups; meter identifiers, readings, and portal links are sensitive. The integration uses HTTPS to `portail.trybatec.fr` and does not claim remote portal write operations. Never publish credentials, bearer tokens, account URLs, dwelling identifiers, meter serials, consumption values, raw logs or private screenshots. The provider API is undocumented; legal permission and trademark use must be reviewed before broad distribution. Maintenance and support are not guaranteed.

For missing integration: verify installed directory, the selected release, browser refresh and restart. For failed login: check permissions and use the reauthentication flow. For ambiguous housing: use only the controlled fallback. For unknown units: do not force a conversion. For incomplete histories: preserve gaps and inspect coverage. For unexpected Energy totals: inspect competing sources and legacy Recorder generations; do not delete historical records as a troubleshooting shortcut.

## Références officielles / Official references

- [Structure du dépôt / Repository structure](https://contributors.home-assistant.io/marketplace/reference/repository-structure/)
- [Intégrations personnalisées / Custom integrations](https://contributors.home-assistant.io/marketplace/guides/integrations/)
- [Installation et versions / Releases](https://contributors.home-assistant.io/marketplace/guides/releases/)
- [Lien de dépôt personnalisé / Custom repository link](https://contributors.home-assistant.io/marketplace/guides/catalog/)
