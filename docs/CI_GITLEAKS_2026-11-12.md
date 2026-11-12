# Gitleaks — historiques et parité CI / Historical coverage and CI parity

## FR — Constat du 12 novembre 2026

**Échec planifié :** [run #43254529863](https://github.com/christophejaubert/ha-trybatec/actions/runs/43254529863), événement `schedule`, SHA `a21906bada0b01a9a069afc2a1b84235b2590cc7`. Le seul job en échec était `gitleaks`. La commande `gitleaks detect --redact` a examiné **367 commits** et signalé une seule occurrence de `generic-api-key`. L'empreinte identifie le commit de test `5bb9d8d120c44693806117d4387760f447a3a328`, le fichier `integration_tests/test_panel_options_parity_b1.py`, la ligne 61.

**Comparaison :** [push #43273136693](https://github.com/christophejaubert/ha-trybatec/actions/runs/43273136693), SHA `a1bd6d8558c8fe1cc13cadeb1ff4aaa20528dc53`, `gitleaks` réussi : l'action imposait automatiquement `--log-opts=-1` et a examiné **un seul commit**. Sa version fixée est `gitleaks/gitleaks-action@e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e`, CLI Gitleaks 8.24.3. Le code de cette action applique une plage limitée aux événements push/PR, mais aucune plage explicite sur `schedule`. Le checkout possède `fetch-depth: 0`.

**Qualification :** la valeur détectée est un UUID constant d'un scénario de test d'options et de restauration d'un compteur, pas une clé d'authentification du fournisseur. Le fichier de test l'associe à `device_uuids` et vérifie sa restitution ; l'occurrence est classée **faux positif spécifique**. Cette qualification concerne uniquement ce motif, et ne démontre pas l'absence d'autres secrets historiques ou actuels. **Ne jamais reproduire la valeur** dans les journaux, les rapports ou les commentaires GitHub.

**Correction limitée :** `.gitleaksignore` contient uniquement l'empreinte précise `commit:fichier:règle:ligne` du constat historique ; aucun motif global, répertoire exclu ou désactivation de `gitleaks`. La même version CLI exécute après l'action un scan de l'historique accessible lors des PR et des pushes, avec `--redact`, afin de détecter avant fusion un problème que le prochain `schedule` découvrirait. Les tests de contrat refusent tout élargissement non revu.

**Portée réelle :** le scan Gitleaks par défaut lit l'historique Git atteignable depuis le checkout courant ; ce n'est ni une garantie d'analyse de tous les commits orphelins, ni une preuve de secret absent de sources non versionnées. Le `fetch-depth: 0` conserve l'historique nécessaire. Toute détection réelle exige qualification, révocation/rotation appropriée et traitement de l'incident, sans publication de la valeur. Aucune réécriture de Git n'est autorisée.

**Critères de recette :** PR : action différentielle + contrôle historique réussis sur un SHA exact ; `main` : contrôle historique et dix contrôles de protection vérifiés ; prochaine planification : nouvelle exécution complète sans nouvel avis. CI synthétique ≠ recette Home Assistant. Aucun effet sur la release ni la production.

Sources : [Gitleaks, .gitleaksignore](https://github.com/gitleaks/gitleaks#%EF%B8%8F-gitleaksignore), [action gitleaks version fixée](https://github.com/gitleaks/gitleaks-action/blob/e0c47f4f8be36e29cdc102c57e68cb5cbf0e8d1e/src/gitleaks.js), exécutions ci-dessus.

## EN — Findings and constraints

The [scheduled run #43254529863](https://github.com/christophejaubert/ha-trybatec/actions/runs/43254529863) on SHA `a21906ba` failed only the Gitleaks job: the full default Git history scan checked **367 commits** and flagged one `generic-api-key` rule match in a November 11 test fixture. The [push run #43273136693](https://github.com/christophejaubert/ha-trybatec/actions/runs/43273136693) on SHA `a1bd6d85` passed by scanning **one commit** via the action's built-in `--log-opts=-1`. This difference follows directly from the pinned action's event-specific scan logic.

The fixed UUID belongs to a test of saved device identifiers, not an API credential. Its **single reviewed fingerprint** is ignored through `.gitleaksignore`; **the detected value is never repeated**. No rule, path or entire history range is ignored. PR and push CI additionally run Gitleaks over reachable history using the binary installed by the pinned action, matching scheduled scan coverage; no secrets artifact is uploaded. Contract tests reject broadening the exception.

A default history scan covers Git commits reachable from the checked-out reference; this does not include every unreachable object or non-repository secret store. Genuine credentials require incident assessment and rotation without printing sensitive data. The PR and the next scheduled run must verify effectiveness independently. No history rewrite, workflow bypass, release or production HA changes.
