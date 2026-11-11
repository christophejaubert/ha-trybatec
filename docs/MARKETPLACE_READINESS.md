# Préparation HACS / Home Assistant Marketplace — audit de travail

**Statut :** documentation préparatoire, mise à jour sur la base publique `0.3.2b1` (commit `6f9bf04147fcddb48cfcb8781c557c76193ce0d8`), le 11 novembre 2026. Ce document ne constitue ni une homologation du dépôt, ni une demande de référencement, ni une autorisation de publication.

Références : [issue #39](https://github.com/christophejaubert/ha-trybatec/issues/39), [ancienne PR #40](https://github.com/christophejaubert/ha-trybatec/pull/40). Les exigences officielles devront être revérifiées au moment d'une candidature stable.

## Constats à partir du dépôt

- Le dépôt est public, non archivé, et utilise `main` comme branche par défaut.
- Le manifeste réside dans `custom_components/trybatec/manifest.json` ; `README.md` et `hacs.json` sont à la racine.
- L'intégration est identifiée comme `Trybatec (Unofficial Beta)`. Ce nom expérimental ne doit pas être retiré avant le jalon stable.
- Le manifeste contient le domaine, la version, la documentation, le suivi des issues, les catégories, les métadonnées de configuration et l'auteur responsable.
- Les ressources visuelles `brand/icon.png` et `brand/icon@2x.png` sont présentes. **Ne pas rétablir les anciens logos de la PR #71** : une nouvelle identité a été intégrée après cette PR.
- Le workflow `.github/workflows/ci.yml` possède déjà les contrôles HACS et hassfest, ainsi que tests Python, sécurité et tests liés à Home Assistant. Leur présence n'atteste pas de leur réussite sur une future candidate.
- L'API fournisseur utilisée n'est pas contractuellement documentée, et l'intégration ne bénéficie pas d'un support officiel.
- Les décisions historiques persistantes et les données Recorder nécessitent une vérification des effets d'installation, mise à jour, désinstallation et restauration ; une absence de code de purge n'est pas une preuve de conservation complète dans tous les scénarios.

## Travaux à qualifier avant une version stable

| Domaine | Vérifications encore nécessaires | Preuve attendue |
|---|---|---|
| Manifeste/HACS | Champs requis, catégories, éventuelle version minimale, nom stable, packaging et compatibilité des options HACS | HACS Action et hassfest sur le SHA stable candidat |
| Installation | Dépôt personnalisé, installation initiale, mise à jour, réauthentification, erreurs, retrait et réinstallation | Tests reproductibles avec versions HA déclarées |
| Persistance | Options, identités de compteurs, imports, décisions, références Energy et statistiques Recorder | Recette isolée avant/après redémarrage et migration |
| Sécurité | Secrets et journaux assainis, droits des commandes sensibles, interdiction des écritures fournisseur | Tests de sécurité et revue de code |
| Présentation | Charte actuelle, traductions FR/EN, ordinateur, mobile, clair/sombre et critères WCAG visés | Recette réelle documentée, sans revendication générale prématurée |
| Documentation | Limites du service tiers, politique de support, sauvegarde/restauration, coût, historique, FAQ | Relecture FR/EN sur la version finale |
| Publication | Cohérence manifeste, notes, tag, release et SHA de CI ; contrôles bloquants validés | Autorisations distinctes de fusion/publication/candidature |

## Règles de non-régression

1. Conserver les jobs CI existants ; ne pas créer de doublon HACS/hassfest.
2. Ne pas introduire `homeassistant`, `country`, `hide_default_branch`, `persistent_directory`, ni d'option de packaging par supposition. Vérifier la documentation officielle et les migrations nécessaires.
3. Ne pas supprimer `render_readme` de `hacs.json` sans vérification de compatibilité.
4. Ne pas réutiliser tel quel le diff de la PR #40 : il cible une ancienne version et contient des affirmations de compatibilité à requalifier.
5. Aucune modification automatique des données Recorder, Energy ou du fournisseur à l'installation ou à la mise à jour.
6. Ne jamais publier de données, relevés, identifiants ou captures d'une installation particulière.

## Décision de publication

**Non qualifié pour une candidature officielle à ce stade.** La publication d'une préversion GitHub, même si sa CI réussit, ne valide pas la version stable ni le référencement. La candidature à un catalogue public reste hors du périmètre `0.3.3b1`.

Sources de vérification futures : [documentation Home Assistant](https://developers.home-assistant.io/), [documentation HACS](https://www.hacs.xyz/), [référentiel de l'issue #39](https://github.com/christophejaubert/ha-trybatec/issues/39).
