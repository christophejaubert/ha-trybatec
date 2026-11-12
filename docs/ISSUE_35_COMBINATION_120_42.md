# 🤖 Intégration #35 / #120 / #42 — Reconciliation contract

**Préparation cible / Target:** `0.3.4b1`. **Date:** 2026-11-12.  
**Do not merge / Ne pas fusionner:** this is a coordination specification, not approval.

## FR — Inventaire des bases vérifiées

| Source | Rôle | SHA observé lors de l'analyse |
|---|---|---|
| `main` | Base de #132 | `a1bd6d8558c8fe1cc13cadeb1ff4aaa20528dc53` |
| PR #132 | #35 installation, auth, notifications | Voir le SHA de la PR lors de la réconciliation finale |
| PR #120 | #81 identités stables **nouveaux comptes uniquement**, sans migration | `9df0183d436e56a1847d4e7721f830f8a253895c` |
| PR #118 | #42 tarifs, éditeur et préparation YTD | `8d5aab1343aaf2bf33d57accb92aa7e935c53011` |

**SHA mouvants :** une mise à jour des branches invalide ces références ; relire les patches et rejouer les tests au moment de l'intégration.

### Fichiers partagés : règles de reprise ciblée

1. `config_flow.py` : #120 ajoute `CONF_STABLE_METER_IDENTITIES` à l'import de `const` et `CONF_STABLE_METER_IDENTITIES: True` **uniquement** dans `_create_account_entry`. #132 ajoute les exceptions `TrybatecAccessDeniedError` et `TrybatecDiscoveryAmbiguousError` dans les branches de `async_step_user`, `async_step_manual_url` et `async_step_reauth_confirm`. **Les deux ensembles de modifications doivent coexister.** Le test #35 de réauthentification avec `stable_meter_identities=True` et options tarifaires est un contrat de conservation, pas une validation du runtime stable de #120.
2. `coordinator.py` : #120 ajoute `StableUnitGuard`, son initialisation conditionnelle et `await stable_unit_guard.async_prepare(data)` **avant** la mise à jour des états, aussi bien dans `_async_update_data` que pour les unités sauvegardées. #132 ajoute le texte et le cycle de vie des notifications, plus l'exception 403 spécialisée. **Ne jamais déplacer `async_prepare` après `_clear_access_issue` :** un état refusé/incorrect n'est pas une récupération validée. Conserver les garde-fous d'unités.
3. `__init__.py` : #120 charge le registre durable d'unité avant les capteurs. #132 ne modifie pas ce fichier ; conserver intégralement le chargement #120 si celui-ci est intégré.
4. `const.py`, `meter_identity.py`, `stable_identity_runtime.py`, `sensor.py` : appartiennent au contrat #120. #132 ne doit pas réécrire leurs modifications.
5. `panel/trybatec-panel.js`, `panel_tariffs.py`, `tariff_validation.py`, `tariff_ytd.py` : périmètre #118, sans collision actuelle avec les fichiers de production modifiés dans #132.
6. **Futur formulaire natif des tarifs #42 :** préserver `entry.options` intégralement lors de la réauthentification, notamment `annual_tariffs`, `annual_meter_tariffs` et les options de lot. Ne pas imposer une migration JSON, un changement de représentation, de valeur ou d'arrondi à la connexion ; le projet de retrait de la saisie JSON obligatoire relève de #42.

### Protocole d'intégration sans fusion automatique

- Relire `main` et les deux SHA de tête. Refuser toute réconciliation basée sur une ancienne branche non vérifiée.
- Sur **une branche de recette isolée** et après arbitrage de l'ordre, combiner les patches en conservant tous les ajouts #120 listés ci-dessus ; ne jamais réutiliser les anciennes versions complètes des fichiers partagés.
- Vérifier la compatibilité des nouveaux compteurs G01–G10 : ancien compte inchangé, nouvelle entrée avec flag, unité sûre, collisions refusées, absence de migration, aucune identité dupliquée et précautions de rétrogradation.
- Tests #35 obligatoires : découverte sans UUID, erreurs 401/403/429/5xx/JSON, repli autorisé seulement après ambiguïté, vérification de l'URL, réauthentification de compte, conservation intégrale des identités et options, notifications persistantes FR/EN après reload, zéro donnée de production.
- Tests #42 obligatoires : options tarifaires intactes après reauth, édition tarifaire réservée au parcours autorisé, absence de changement YTD implicitement causé par #35.
- Rejouer toutes les CI obligatoires sur le **SHA exact du code combiné** ; qualifier les résultats HA synthétiques, les tests de persistance et Recorder ; documenter échecs/annulations/pending.
- Maintenir #35, #81 et #42 ouverts tant que leurs critères métier distincts ne sont pas recettés. Ne pas fusionner sur la seule réussite CI.

### Critères non couverts par les tests de #132 seuls

- Runtime réel de la combinaison #120/#132/#118 et reprise d'un registre d'identités stable.
- Retour à une ancienne version pour un nouveau compte stable (limite documentée #120).
- Environnement Home Assistant réel avec un compte Trybatec de production.
- Formulaire natif futur #42 non livré à la date du présent audit.
- Complétude des utilisateurs tiers de Recorder/Énergie et restauration réelle.

## EN — Compatibility handoff

PR #132 owns 401/403 classification, URL-fallback safety, native reauthentication, and persistent-notification lifecycle. PR #120 owns newly created account identity flags, persistent source-unit guards and early startup loading. Their changes in `config_flow.py` and `coordinator.py` are separate **semantically**, but both must be preserved in the eventual combined diff. The new account stable flag must survive reauthentication and must not be silently added to old entries; `StableUnitGuard.async_prepare` must precede reporting a successful poll and notification dismissal.

PR #118 currently owns tariff editing and year-to-date cost preparations. Future native tariff forms must not be reset by reauthentication, rounded, rewritten or silently migrated by #35. The standalone #132 tests exercise preservation of synthetic stable-account and tariff options; **they do not constitute a full combined-branch qualification**.

Re-run full synthetic HA and identity G01–G10 tests, Recorder/persistence and all mandatory checks on the exact *combined* SHA. Never infer production acceptance from CI, and do not merge, publish, migrate, delete identities or install without separately authorized decisions.

**References:** [#35](https://github.com/christophejaubert/ha-trybatec/issues/35), [#132](https://github.com/christophejaubert/ha-trybatec/pull/132), [#120](https://github.com/christophejaubert/ha-trybatec/pull/120), [#118](https://github.com/christophejaubert/ha-trybatec/pull/118), [#45](https://github.com/christophejaubert/ha-trybatec/issues/45).
