# Issue #35 — Qualification installation et accès / Setup & access qualification

**Baseline / Référence historique :** merged PR #119, prior to subsequent #35 fixes.  
**Superseded for current behavior / État actuel à lire :** [ISSUE_35_FUNCTIONAL_FIXES.md](ISSUE_35_FUNCTIONAL_FIXES.md). The two strict xfails below describe the *historical #119 baseline*, not this corrective branch's acceptance result. CI on the corrective SHA is required.

**Date / Date:** 2026-11-12  
**Scope:** synthetic testing and documentation only; production portal and Home Assistant are excluded.  
**Coordination:** PR #82 reserves `custom_components/trybatec/config_flow.py`, `coordinator.py`, and `__init__.py`.

## FR — Réconciliation fonctionnelle

Cette PR ne redéveloppe pas les parcours déjà présents sur main. Le code existant assure :

- `api.py` : authentification en mémoire, `GET /housings` avec Bearer, résolution prudente d'un seul `dealUid` UUID, validation du JSON, délais et tailles bornés, reprises limitées pour 429/5xx, 401/403 traités explicitement.
- `config_flow.py` : identifiant/mot de passe, vérification d'accès `/indexes`, saisie de secours de l'URL complète, réauthentification Home Assistant et mise à jour de l'entrée actuelle sans recréation.
- `coordinator.py` : `ConfigEntryAuthFailed`, `UpdateFailed`, notification persistante après trois erreurs de connexion consécutives ou dès l'erreur d'authentification, ID de notification stable par entrée.
- `sensor.py` : aucune substitution explicite de consommation nulle dans les chemins inspectés ; l'état d'indisponibilité lors d'un échec de rafraîchissement doit rester testé en HA.
- `translations/fr.json` et `translations/en.json` : formulaires localisés ; texte des notifications du coordinateur actuellement seulement en français.

**Documentation actualisée :** le cas nominal utilise uniquement identifiant et mot de passe. Le repli attend l'URL HTTPS complète de la page Index ; pas un UUID arbitraire. Plusieurs copropriétés par compte ne sont pas annoncées comme prises en charge.

### Matrice de conformité

| Critère | Déjà présent dans le code | Qualification ajoutée | Solde métier |
|---|---|---|---|
| Identifiant/mot de passe, logement unique | Oui | Découverte Bearer + flux HA existant | Recette HA réelle |
| `dealUid` valide/canonique | Oui | UUID valide, absent, invalide, majuscules | API réelle évolutive |
| Réponse vide, 204, JSON incorrect | Rejet prudent | Tests synthétiques | Aucune |
| Ambiguïté, logements multiples | Aucun choix automatique | Tests refus ; URL contrôlée | Multi-copropriétés hors périmètre |
| URL de repli | HTTPS, hôte et UUID contrôlés | Hôte étranger, query, HTTP, succès | UX réelle |
| Authentification 401/403 | Oui | Tests 401/403, renouvellement de Bearer | Vérification en HA |
| 5xx, panne réseau, timeout | Gestion bornée | Tests d'erreurs et de tentatives | Reprise longue réelle |
| Réauthentification HA | Oui | Test même compte, mot de passe, options, ID | Recette réelle non effectuée |
| Notifications : seuil et déduplication | Oui, dans une instance | Tests 3/4 erreurs, auth, reprise | Persistance inter-redémarrage |
| Ne pas afficher des zéros fictifs | Code conçu ainsi | À compléter en environnement HA | Contrôle des entités |
| Confidentialité | Exceptions assainies | Vérifications synthétiques partielles | Audit logs restant |
| FR/EN | Champs localisés | Documentation FR/EN | Notifications FR seulement |

### Écarts historiques de la PR #119 — corrigés dans la branche candidate, à qualifier par CI

1. **Notification après recréation du coordinateur :** une notification produite avant un redémarrage peut ne pas être clôturée après la première actualisation réussie. L'indicateur `_access_notification_active` est initialisé à False sur le nouvel objet. Correction à coordonner dans `coordinator.py` (PR #82).
2. **Refus spécifique du deal découvert :** `TrybatecAuthError` issu de `/indexes` ramène au formulaire `invalid_auth` sans repli URL. Distinguer le refus de l'identité et l'absence d'accès à cette copropriété avant de modifier le comportement. Correction et arbitrage avec PR #82.

**Historique :** ces marqueurs ont été retirés de la branche corrective et remplacés par des scénarios normaux. Une CI réussie sur le SHA correctif est nécessaire ; l'issue reste ouverte sans recette réelle.

### Exécution demandée

```bash
python -m pytest -q tests/test_issue35_discovery.py
python -m pytest -q integration_tests/test_issue35_qualification.py
```

Les fichiers source sont synthétiques, utilisent un compte inventé en `example.invalid`, et ne contiennent ni jeton réel, ni identifiant de compteur réel. Le second appel doit tourner avec les dépendances officielles `pytest-homeassistant` du projet. Ne pas présenter une simple compilation comme une exécution.

### Conditions de clôture

- CI sur le SHA final, contrôles de sécurité, vérification des tests attendus.
- Correction qualifiée ou décision métier documentée sur les deux écarts.
- Validation des traductions et des notifications en français et en anglais.
- Recette séparée sur une instance de test Home Assistant, sans modifier le compte utilisateur de production.
- Maintien des `entity_id`, `unique_id`, options, historique Recorder et préférences Énergie.
- Aucune fusion, mise en production ni publication de release par cette PR.

## EN — Handoff

The existing integration already implements credentials-only setup for an unambiguous housing, authenticated housing discovery, verified Indexes access, controlled Indexes-page URL fallback, HA reauthentication, limited retries and persistent notifications. This PR adds independent synthetic tests and corrects the bilingual installation documentation.

At the PR #119 baseline, two intentionally strict expected failures remained: clearing an old persistent notification after coordinator recreation, and offering a controlled URL fallback after deal-specific Indexes authorization failure. The corrective branch replaces them with explicit assertions; confirm its exact-sha CI before claiming technical qualification.

No real Trybatec credentials or network requests, Home Assistant production changes, Recorder writes, Energy preference changes, merge or release are authorized by this work. Functional fixes in the three reserved files require separate coordination with PR #82.

**Sources / Références :**
- https://github.com/christophejaubert/ha-trybatec/issues/35
- https://github.com/christophejaubert/ha-trybatec/pull/82
- https://github.com/christophejaubert/ha-trybatec/blob/main/custom_components/trybatec/api.py
- https://github.com/christophejaubert/ha-trybatec/blob/main/custom_components/trybatec/config_flow.py
- https://github.com/christophejaubert/ha-trybatec/blob/main/custom_components/trybatec/coordinator.py
