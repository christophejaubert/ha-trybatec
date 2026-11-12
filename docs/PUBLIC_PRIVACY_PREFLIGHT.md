# Contrôle prépublication / Public privacy preflight

## FR — Périmètre et arbitrages D1/D2/D3

Ce contrôle analyse tous les nouveaux commits, leurs messages, les noms de fichiers et lignes ajoutées à chaque étape d'une PR publique. Les données introduites puis supprimées avant le dernier commit restent contrôlées. Les valeurs détectées, extraits de diff, courriels, chemins et messages Git ne sont **jamais reproduits** dans les journaux du contrôle : seules les catégories et les quantités sont affichées.

**D1 (définitif) : identité Git inchangée.** Les adresses habituelles d'auteur et de commiteur sont **autorisées** ; elles peuvent produire un avertissement informatif, jamais un refus à elles seules. Aucune migration vers une adresse noreply ni changement de réglage Git n'est requis.

**D2 : protection GitHub obligatoire après qualification.** Le workflow de sécurité utilise pull_request_target sur main : GitHub charge la version approuvée depuis la branche par défaut. Il extrait uniquement des objets Git de la PR, vérifie l'identité exacte de son SHA, puis exécute **exclusivement le script provenant de main**. Il ne checkout ni n'exécute le code candidat. Le jeton du job ne dispose que de contents: read ; les credentials ne persistent pas. Aucune donnée de production, aucun secret et aucun accès Home Assistant ne sont injectés.

**D3 (définitif) : aucun nettoyage d'historique.** Le contrôle est incrémental ; les métadonnées et journaux historiquement publics ne sont ni supprimés ni réécrits.

**Refus (bloquant)** : signatures fortes de jetons ou clés, chemins personnels absolus, noms de machines locaux, identités Git de machine locale, références Git ambiguës/incomplètes, impossibilité d'inspecter entièrement les nouveaux commits ou le diff. **Avertissement (non bloquant)** : adresse Git habituelle, courriels non fictifs dans le contenu, IP privées, identifiants d'installation possibles, contenu binaire non inspecté. Les heuristiques peuvent produire des faux positifs et faux négatifs ; compléter par Gitleaks et revue manuelle. Un avertissement d'adresse Git habituelle n'est pas, en lui-même, une anomalie de conformité.

La plage Git commence à l'ancêtre commun entre base et tête de PR, pour ne pas attribuer à la PR les commits parallèles sur main. Les erreurs, sorties Git sensibles et correspondances ne sont pas rendues visibles. Les fichiers binaires et contenus historiques ne sont pas analysés exhaustivement.

### Ordre d'intégration sans blocage généralisé

1. Vérifier le diff, les tests synthétiques, les contrôles obligatoires et les garde-fous du workflow sur le SHA exact de #140.
2. Obtenir une **autorisation distincte de fusion de #140**. Tant que son workflow n'est pas sur main, il n'est pas une protection indépendante activable.
3. Après fusion autorisée, constater sur main l'exécution de public-privacy-preflight depuis une référence de confiance, son statut sur une PR légitime, les refus synthétiques et l'état de toutes les PR ouvertes.
4. **Seulement après ces preuves**, ajouter le contrôle de source GitHub Actions (integration_id 15368) au ruleset existant Protect main - CI/CD (ID 26796600), sans modifier ses dix contrôles, sa politique stricte ou ses protections de suppression/force-push. Vérifier l'application sur les PR ouvertes et les cas de refus.
5. Surveiller les règles GitHub Actions relatives à pull_request_target : un blocage de l'événement rendrait le contrôle indisponible et impose une solution approuvée avant l'activation obligatoire.

Le connecteur GitHub disponible peut lire le ruleset, mais **ne possède pas d'opération de modification des rulesets**. L'étape 4 est à réaliser dans l'interface GitHub, ou via une intégration d'administration distincte explicitement autorisée. Ne jamais marquer le contrôle comme obligatoire avant vérification réelle du ruleset.

### Procédure administrateur, lorsque toutes les conditions sont réunies

Ouvrir Repository → Settings → Rules → Rulesets → Protect main - CI/CD (ID 26796600) → Edit → Require status checks to pass → Add checks → sélectionner public-privacy-preflight (source GitHub Actions). Conserver les dix contrôles et l'option de branche à jour, enregistrer puis rouvrir le ruleset pour confirmer l'ajout. En cas de blocage anormal, désactiver uniquement ce nouveau contrôle tout en conservant les dix précédents ; investiguer avant réactivation.

## EN — Purpose, authority and activation gate

The trusted default-branch workflow inspects all newly reachable commits, including files and lines added and removed in intermediate commits, as well as Git metadata and commit messages. It never prints matched values or Git errors. It fetches PR commit objects strictly as data, verifies the expected head SHA, and executes only the trusted scanner checked out from main. No PR-supplied workflow, script or dependency is executed; token permission is contents: read only.

**D1:** existing personal Git author/committer addresses remain accepted; warnings are strictly advisory and never block merely because an ordinary address is used. No noreply requirement. **D3:** never rewrite, delete or clean historic Git objects. **D2:** make the status check mandatory only after the separately authorized merge, positive/negative tests on the main-sourced workflow, and review of ongoing PR impact. Existing rules remain unchanged.

High-confidence credentials, personal paths, local hostnames and unreadable/incomplete Git ranges fail closed. Private IPs, possible identifiers, non-fixture content email addresses and binary content yield warnings. Incremental static heuristics do not replace Gitleaks, manual review or non-destructive risk tracking. Synthetic tests never include actual installation data.

**Ruleset procedure:** once main contains and has successfully exercised the trusted job, add public-privacy-preflight from GitHub Actions (integration_id 15368) to existing ruleset Protect main - CI/CD (#26796600). Keep all ten required checks, strict enforcement and other rules intact. Reopen the saved ruleset and recheck active PRs; remove only the new check if unexpected blockers occur. The current connected GitHub tool supports ruleset reads only, not ruleset updates; no activation has occurred.

**Future compatibility:** GitHub's 2026 Actions event-policy changes can affect pull_request_target in public repositories. Before enforcing the required check, confirm the repository's Actions event policy permits the trusted workflow, and keep monitoring that prerequisite.
