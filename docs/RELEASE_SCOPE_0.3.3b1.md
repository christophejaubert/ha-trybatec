# 0.3.3b1 — Consolidation post-recette : périmètre et preuves attendues

**Statut :** préparation sur branche dédiée, non fusionnée, non publiée. Base de référence : `0.3.2b1`, SHA `6f9bf04147fcddb48cfcb8781c557c76193ce0d8`. Les constats locaux de recette ne sont pas des données destinées au dépôt public.

## Contexte

La recette technique en lecture seule de 0.3.2b1 ne constitue pas une recette exhaustive des opérations d'écriture, du rendu graphique réel et des migrations. L'objectif de cette branche est de corriger des écarts **reproduisibles sans toucher aux installations**, de préserver les avancées déjà fusionnées et de documenter sans ambiguïté les travaux encore ouverts.

Une issue GitHub ouverte n'implique pas que toute sa fonctionnalité manque ; une PR ancienne encore ouverte n'est pas forcément un correctif à fusionner.

## Réconciliation des PR historiques

| PR | Présence sur `main` 0.3.2b1 | Disposition retenue |
|---|---|---|
| [#72](https://github.com/christophejaubert/ha-trybatec/pull/72) | Spécification A01–A31 identique (reprise lors de #73) | Ne pas recopier ni fusionner en doublon |
| [#46](https://github.com/christophejaubert/ha-trybatec/pull/46) | Menus et accès au lissage repris, notamment dans #64 avec appariement plus strict | Conserver la version récente ; ne pas réintroduire le diff ancien |
| [#71](https://github.com/christophejaubert/ha-trybatec/pull/71) | Palette et tests repris puis améliorés avec #73 ; ancien logo remplacé | Préserver le logo approuvé et contrôler l'accessibilité restante |
| [#40](https://github.com/christophejaubert/ha-trybatec/pull/40) | Certains passages du README déjà modernisés ; audit Marketplace manquant | Nouvelle version du document `docs/MARKETPLACE_READINESS.md` basée sur 0.3.2b1 |

Ces anciennes PR restent inchangées par la présente contribution. Leur éventuelle clôture demande une action distincte.

## Changements réellement candidats dans cette PR

- [#35](https://github.com/christophejaubert/ha-trybatec/issues/35) : mise à niveau **sans doublon** d'une notification de perte de connexion vers une notification explicite d'authentification si un refus avéré survient ensuite ; pas de rétrogradation avant une actualisation réussie. Tests synthétiques de déduplication, d'escalade et de résolution. Cela ne prétend pas couvrir à lui seul tous les scénarios de réauthentification.
- [#39](https://github.com/christophejaubert/ha-trybatec/issues/39) : audit documentaire actualisé, sans candidature officielle à HACS/Marketplace.
- Traçabilité [#45](https://github.com/christophejaubert/ha-trybatec/issues/45), [#70](https://github.com/christophejaubert/ha-trybatec/issues/70), [#42](https://github.com/christophejaubert/ha-trybatec/issues/42), [#36](https://github.com/christophejaubert/ha-trybatec/issues/36) et [#37](https://github.com/christophejaubert/ha-trybatec/issues/37) : conservation des fonctions présentes et identification des tests et acceptations encore requis.

## Critères non encore attestés sur Home Assistant réel

- IHM : sept pages, navigation PC/mobile, FR/EN, thèmes clair/sombre dynamiques, clavier/focus, contraste, zoom 200 %, 320 px et aide technique. Les tests synthétiques ne constituent pas un audit WCAG complet.
- Tarifs : persistance et migration des tarifs historiques, dérogations de compteur, années exactes, droits administrateur, calculs et erreurs.
- Historique : qualification des zéros, provenance des estimations, lissage du seul solde, conflits, changements d'heure et conservation des totaux.
- Recorder / Énergie : écriture après confirmation, vérification après persistance, idempotence, versions, repli, aucun double comptage et préservation des sources préexistantes.
- Authentification : refus d'accès 401/403, indisponibilité réseau/5xx, recours contrôlé à une URL, retour à la normale et absence de fuite d'identifiants.
- Limites ressources : les budgets candidats 120 s / 24 HTTP (standard) et 600 s / 80 HTTP (exhaustif), pause proposée 500 ms, restent **inactifs**. Les protections de secours effectives sont 1 800 s / 512 tentatives HTTP. Ne pas activer de seuil inférieur sans essais représentatifs.

## Travaux exclus de cette candidate tant qu'ils ne sont pas prouvés sûrs

- [#34](https://github.com/christophejaubert/ha-trybatec/issues/34) : pondération par degrés-jours, volontairement différée.
- Désinstallation, réinitialisation et purge **A01–A31** : spécification déjà présente dans le dépôt, mais 14 questions techniques et 40 scénarios automatisés conditionnent une future implémentation sûre. Ne publier aucun bouton destructeur partiel ; aucune écriture sur le portail fournisseur.
- EVO-007 : sauvegarde d'une version d'intégration via Marketplace, différée.
- Référencement officiel HACS/Marketplace ou déclaration d'une version stable.
- Reprise brute des quatre anciennes PR et changement du logo validé.

## Porte de qualification de la PR

1. CI du **même SHA candidat** : Python 3.13/3.14, Ruff essentiel, tests HA, Recorder, persistance, hassfest, HACS, sécurité et navigateur synthétique ; aucun contrôle obligatoire absent, en cours ou en échec.
2. Revue des changements réels et absence d'informations spécifiques à une installation privée.
3. Tests nouveaux exécutés sur la classe de notification réelle, en environnement purement synthétique.
4. Résultat documenté des limites : ce qui est testé en lecture seule, ce qui n'est pas testé, et ce qui nécessite une décision opérationnelle ultérieure.
5. Fusion, tag, publication et modifications d'une instance Home Assistant restent soumis à des autorisations spécifiques et sont **hors de la présente PR de préparation**.
