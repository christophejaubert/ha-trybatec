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

## FR — Complément du 13 novembre 2026 : branche expérimentale #88

Le scan historique Gitleaks de #149, #150, #151 et de #147 réexécutée sur le **même SHA** retrouve une nouvelle occurrence `generic-api-key` sur l'historique accessible, tandis que la détection incrémentale reste verte. Le mode historique sans plage explicite inclut les références distantes téléchargées ; ses résultats peuvent donc évoluer sans modification du SHA du HEAD contrôlé.

Le diagnostic temporaire de la PR #152 a identifié **uniquement** la référence `5de2f7291555ba0e6a058f6265498876ee562fd4`, `custom_components/trybatec/energy_bulk_native_port_l7.py`, ligne **55**, catégorie `generic-api-key`, héritée de la branche expérimentale `feat/88-native-energy-evidence-20261113`. La chaîne de 24 caractères sert à former une **clé d'indexation locale du Store Home Assistant**, assemblée avec un digest d'identifiant d'entrée ; aucune preuve d'usage pour authentification ou API extérieure. La variante de travail plus récente, dans #151, utilise un identifiant différent. **La valeur littérale n'est reproduite nulle part dans cette qualification.**

Une **deuxième empreinte exacte** est ajoutée à `.gitleaksignore` pour ce faux positif historique ; l'exception précédemment qualifiée de l'UUID de test reste inchangée. Aucun chemin, règle, catégorie, branche entière ou SHA générique n'est autorisé. Le job conserve sa détection incrémentale et son analyse historique bloquante. Un contrôle autonome crée dans un dépôt Git temporaire une signature de clé AWS fictive, jamais enregistrée sur GitHub, puis exige que Gitleaks la refuse (exit 2) ; la fixture et tout secret synthétique sont supprimés à la fin du job.

Limite : une empreinte ciblée n'exonère ni le contenu courant de #88 ni tout autre secret. Les contrôles doivent encore être réussis sur la PR #152 et sur la candidate composée, pour des SHA exacts ; le scheduled scan doit conserver son périmètre et rester bloquant.

## EN — November 13, 2026: earlier #88 experimental branch

The incremental Gitleaks scan passes, while the unbounded reachable-history scan fails even when re-running #147 on its **unchanged SHA**. Full-history scanning reads fetched remote refs, so the result can change when unrelated branches become reachable.

Temporary, metadata-only PR #152 diagnostics isolated one `generic-api-key` finding: commit `5de2f7291555ba0e6a058f6265498876ee562fd4`, `custom_components/trybatec/energy_bulk_native_port_l7.py`, line **55**, in the earlier `feat/88-native-energy-evidence-20261113` branch. The 24-character constant forms a **local Home Assistant Store index key** together with an entry digest; it is not used as an API or authentication credential. The later #151 candidate uses a different name. The matched value is deliberately never reproduced.

An exact, commit/path/rule/line fingerprint is added to the existing one-fixture exception. No scanning ranges, rule families, paths or branches are excluded. Incremental and historical scans remain blocking; a transient Git repository containing a freshly generated fictional AWS-shaped key must be rejected with exit status 2, without uploading artifacts or logging the value.

This is a classification of one particular historical finding, not a claim that reachable history or current branches can never contain other secrets. Exact-SHA CI on #152 and the final integrated candidate is still required.
