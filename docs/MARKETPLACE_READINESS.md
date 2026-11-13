# 🤖 #39 — Préparation au référencement Marketplace / HACS catalog readiness

**Audit au 13 novembre 2026 / Audit as of 13 November 2026** — base `main` : `8d621da9703b40662800b4a7c286707e8a7f895f`, manifeste `0.3.4b1`. [Préversion publiée 0.3.4b1](https://github.com/christophejaubert/ha-trybatec/releases/tag/0.3.4b1) (13 novembre 2026, **pre-release**). **Aucune version stable ni candidature au catalogue n'est validée.** / No stable release or public-catalog submission is approved.

**Références** : [issue #39](https://github.com/christophejaubert/ha-trybatec/issues/39), [pilotage MOE #45](https://github.com/christophejaubert/ha-trybatec/issues/45), [guide utilisateur bilingue](MARKETPLACE_INSTALLATION_FR_EN.md), [SECURITY.md](../SECURITY.md), [README](../README.md). L'[ancienne PR #40](https://github.com/christophejaubert/ha-trybatec/pull/40) se fonde sur une base antérieure : ne pas appliquer son diff sans réconciliation.

**Périmètre de cette contribution / Scope:** documentation de distribution et tests statiques ; aucune modification de `hacs.json`, `manifest.json`, marque, traductions, interface, Recorder, Énergie, workflows ou numéro de version. Les PR #150/#151/#152/#153/#154/#156 touchent des fichiers partagés ; les vérifier et réconcilier avant toute modification ultérieure. / Distribution documentation and static tests only; no shared functional or release edits.

## FR — Checklist de qualification et preuves

**États** : **Vérifié (statique)** = présence/structure contrôlée dans le dépôt, pas conformité certifiée ; **À tester (SHA)** = contrôler en CI sur le SHA exact ; **Bloqué** = dépendance fonctionnelle ou décision utilisateur ; **À confirmer** = résultat absent, compatibilité ou droit non vérifié. Une case de #39 ne se coche qu'avec sa preuve datée et le SHA/la version concernés.

| Critères #39 | Contrôle et constat au 13/11/2026 | État / prochaine preuve |
|---|---|---|
| M01–M06 | GitHub public, non archivé, description, topics et issues actifs ; `README.md` et `hacs.json` à la racine ; un sous-dossier `custom_components/trybatec` | **Vérifié (statique)** sur `main` ; confirmer absence de conflit de domaine avec Home Assistant Core sur la candidate |
| M07–M08 | Manifeste : `domain=trybatec`, nom, version `0.3.4b1`, documentation, issue tracker, code owner, `config_flow=true`, `hub`, `cloud_polling`, `requirements=[]`, `dependencies=[]`, `after_dependencies` déclarées. Catégories `water.meters_leak_detection` et `energy.meters_monitoring`, présentes dans la taxonomie officielle du 20/10/2026 | **Vérifié (statique)** ; HACS/hassfest et dépendances d'exécution **à tester sur SHA candidat** |
| M09–M10, M16 | `hacs.json` : `name=Trybatec (Unofficial Beta)` et `render_readme=true`. Nom cohérent avec le manifeste ; conserver Beta jusqu'à décision stable. **Aucun minimum HA déclaré/validé** : ne pas inventer `homeassistant`. Les options `country`, `persistent_directory`, `hide_default_branch`, `zip_release`/`filename` ne sont pas activées sans besoin vérifié. `render_readme` est présent dans l'historique mais absent de la liste des clés documentées par le Marketplace 2026.11 : vérifier comportement HACS avant suppression | **À confirmer** : versions HA testées, fichiers à conserver entre mises à jour, validation metadata sur SHA |
| M11 | `translations/en.json` et `fr.json`, `config_flow` et étape de réauthentification présentes ; les PR UI peuvent encore changer ces fichiers | **Vérifié (présence)** ; cohérence des chaînes, traduction complète et rendu FR/EN **à tester**, sans écraser #156 |
| M12, M15 | `brand/icon.png` (256×256) et `brand/icon@2x.png` (512×512), déjà audités avec tests dédiés ; pas de nouvel emblème créé | **Vérifié (présence/dimensions)** ; contrôle humain, droits de marque et affichage clair/sombre **à confirmer** (#70) |
| M13–M14 | Format de distribution à source unique, fichiers requis sous `custom_components/trybatec`. Limites officielles Marketplace : taille décompressée ≤100 MiB, 50 000 fichiers. Les données `.storage` et Recorder ne sont pas situées dans le dossier de l'intégration | **À tester (SHA)** : paquetage exact, mises à jour, persistance, reprise, désinstallation |
| M17–M18, D01–D23 | Le README d'origine contient de longues sections historiques et des exemples d'anciennes versions. Le nouveau [guide FR/EN](MARKETPLACE_INSTALLATION_FR_EN.md) explique les chemins Marketplace/HACS/manuels, authentification, réauthentification, unités, limites, coûts, sécurité et retrait. Il est accessible depuis ce document déjà lié au README | **Guide préparé** ; relecture et simplification du README global **à coordonner** avec PR qui le modifient, bouton My HA de dépôt personnalisé à tester avant ajout |
| T01–T03, T19 | Les jobs `hacs` (category `integration`, sans paramètre `ignore`) et `hassfest` existent déjà dans `.github/workflows/ci.yml` : aucun doublon à créer | **À tester (SHA)** : liens des runs et conclusions réussies pour les deux, sans dérogation |
| T04–T05, T15–T18 | `pytest`, Ruff, scanner secrets et contrôles de confidentialité déjà présents ; nouveaux tests statiques de paquetage/documentation dans `tests/test_marketplace_package_39.py` | **À tester (SHA)** et conserver preuve d'exécution ; les vérifications statiques ne certifient ni secrets historiques absents ni runtime HA |
| T06–T14 | Test d'intégration réelle, HA OS/Container/Supervised, architectures, dernières versions HA, migration, réauthentification, retrait et restauration | **À confirmer** : matrice de compatibilité et recette sur environnement(s) autorisé(s) |
| F01–F20, #81 | Multi-comptes/multi-copropriétés, unités, identité physique/technique, collisions et migration | **Bloqué / à qualifier** : scénario complet et tests de régression sur SHA cible |
| F21–F32, #36 | Provenance, lacunes, lissage, reprises Recorder, idempotence, absence d'écritures tardives concurrentes | **Bloqué** : quiescence indépendante du writer, tests d'injection de fautes synthétiques et recette contrôlée |
| F33–F42, #37 | Filiation actifs/déposés, remplacement, générations physiques, consolidation sans addition d'index | **Bloqué** : preuves d'identité et de continuité physique, pont historique validé |
| F33–F42, #88 | Prévisualisation/activation du tableau Énergie ; sources concurrentes, L6 admission et L7 transaction | **Bloqué** : preuve indépendante de l'éligibilité, verrou exclusivité, sauvegarde, rollback et tests réels |
| F43–F62, #42/#155 | Contrôles d'accès, migrations, formulaires tarifaires, UI FR/EN, clavier/mobile, états et navigation | **À qualifier** : tests synthétiques et parcours réels ; aucune fonction expérimentale ne devient disponible par simple CI |
| S01–S16 | API fournisseur non documentée, périmètre HTTPS, secrets en entrées de config/sauvegardes, mainteneur sans affiliation, licence MIT et politique sécurité | **Partiel** : tests de confidentialité, vérification juridique des conditions d'API et droits d'identité visuelle **à confirmer avant diffusion large** |
| R01–R14, C01–C14 | Préversion publiée, **pas de stable validée** ; pas de preuve de succès HACS/hassfest sur la future candidate stable ; pas de PR `hacs/default` autorisée | **Bloqué** : périmètre stable décidé, recette, contrôles SHA, publication stable séparément autorisée, ensuite candidature distinctement autorisée |
| P01–P10, J01–J08 | Maintenance, incidents, compatibilité future, politique de fin de vie, acceptation risques et suivi catalogue | **À confirmer** : engagement de maintenance et décisions explicites du propriétaire |

### Risques de documentation identifiés

1. **Statut** : séparer les notes des versions historiques du comportement de la release réellement téléchargée ; ne pas transférer dans le guide public les capacités non recettées de #36/#37/#88.
2. **Données** : les tests publics et tous les exemples du présent lot utilisent uniquement des éléments génériques, des chemins de code et des URL de documentation. Pas de numéro de lot, index, consommation, login, token, réponse fournisseur ou capture réelle.
3. **Installation** : vérifier que les documents ne présentent pas la présence d'un fichier, une CI verte ou une release bêta comme une garantie de compatibilité/sécurité. Les opérations sur Recorder et Énergie exigent une validation et un acte distincts.
4. **Concurrence** : `README.md`, manifeste, `brand/` et traductions sont présents dans des PR concurrentes ; leur modification finale nécessite réconciliation des branches. Le nom Beta et la version ne changent pas dans ce lot.
5. **Domaine et droit** : confirmer qu'aucune intégration Core future ne revendique `trybatec`, examiner les conditions du portail et vérifier la licence/propriété de l'emblème avant la candidature.
6. **Déploiement** : le Marketplace peut assurer l'installation depuis un dépôt personnalisé, **pas la validation métier** de l'import Recorder ni le référencement automatique au catalogue.

### Préparation de la candidature — jalons sans soumission

- [x] Audit structurel et sources officielles actualisés au 13/11/2026 sur base `8d621da`.
- [x] Guide d'installation, sécurité et limitations **FR/EN** rédigé, sans données de production.
- [ ] Exécuter les **nouveaux tests** sur le SHA de cette PR et conserver leurs résultats.
- [ ] Valider HACS Action **sans `ignore`** et hassfest sur le même SHA futur de candidate stable.
- [ ] Examiner CI secrets/historique, tests, dimensions PNG et alignement des traductions sans fuite ni nouvelle dette.
- [ ] Fixer, **par tests réels**, les versions HA/Python, modes d'installation et architectures pris en charge avant toute valeur `homeassistant` dans `hacs.json`.
- [ ] Qualifier #36, #37, #88 et #81 ou exclure explicitement les capacités non qualifiées du périmètre stable, sans laisser d'écriture dangereuse accessible.
- [ ] Requalifier le README général au SHA retenu, simplifier ses instructions historiques et ajouter les liens My Home Assistant (préférer `hacs_repository` si compatibilité pré-2026.11 recherchée).
- [ ] Valider conditions d'utilisation de l'API non publiée, marque, support et procédure de sécurité.
- [ ] Préciser la conservation `.storage`/Recorder/Énergie et tester mise à jour, désinstallation, réinstallation et récupération.
- [ ] Obtenir décision distincte sur fusion, puis sur release stable (tag, SHA, notes FR/EN) ; **aucune permission implicite**.
- [ ] Envisager ultérieurement une PR dans `hacs/default` **après autorisation spécifique**. Le modèle HACS exige une GitHub Release complète et les URLs des runs HACS/hassfest satisfaisants.
- [ ] Valider ensuite le référencement effectif et le cycle de maintenance ; garder #39 ouverte jusque-là.

## EN — Independent catalog-readiness gate

**Static evidence is not full compliance.** On `main` at `8d621da`, the repository is public with description, topics, issues, one `custom_components/trybatec` integration, `README.md`, `hacs.json`, a `0.3.4b1` custom manifest, recognized water/energy categories, FR/EN translation files, and existing 256/512px local icons. The manifest and HACS name still say **Unofficial Beta**, appropriately so at the experimental stage. `0.3.4b1` is a published **pre-release**, not a stable catalog candidate.

**Do not infer:** minimum supported HA version, runtime support across HA OS/Container/Supervised, ARM64/AMD64 compatibility, complete translation coverage, safe updates/uninstall, complete vendor history, production-safe Recorder writes, consolidated physical lineage or bulk Energy adoption. `hacs.json` deliberately retains its current keys until documented compatibility is established. HACS and hassfest are already in CI and must pass on the **exact candidate SHA without skips**; no duplicate workflows.

**Outstanding gates:** verify packaging and exact-SHA tests; complete the #36 writer-concurrency and Recorder verification proof; #37 physical lineage; #88 independent L6 admission and guarded L7 rollback; #81 identity/migration safeguards; security/privacy checks and public-API legal/trademark review; real Home Assistant installation/update/removal/restore and accessibility tests; publish an authorized stable GitHub Release only when qualified. A separate owner decision is required **before** submitting a PR to `hacs/default`. Neither this documentation PR nor a successful CI authorizes a merge, release, submission or Home Assistant change.

**Conflict avoidance:** #150/#151/#152/#153/#154/#156 already touch shared README/manifest/brand/translations and functional code. This lot only edits the existing readiness guide and adds distribution documentation and focused tests; reconcile any future shared-file change against current branches.

## Sources officielles revérifiées / Official references rechecked (13 November 2026)

- [Marketplace — Repository structure](https://contributors.home-assistant.io/marketplace/reference/repository-structure/)
- [Marketplace — hacs.json](https://contributors.home-assistant.io/marketplace/reference/hacs-json/)
- [Marketplace — Validation checks](https://contributors.home-assistant.io/marketplace/reference/validation/)
- [Marketplace — Custom integrations](https://contributors.home-assistant.io/marketplace/guides/integrations/)
- [Marketplace — Releases](https://contributors.home-assistant.io/marketplace/guides/releases/)
- [Marketplace — Public catalog procedure](https://contributors.home-assistant.io/marketplace/guides/catalog/)
- [Home Assistant — Integration categories](https://contributors.home-assistant.io/core/integrations/categories/)
- [Home Assistant — Local brand images](https://contributors.home-assistant.io/core/integrations/brands/)
- [Home Assistant — Manifest](https://contributors.home-assistant.io/core/integrations/manifest/)
