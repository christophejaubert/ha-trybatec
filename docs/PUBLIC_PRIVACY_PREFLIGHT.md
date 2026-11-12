# Contrôle prépublication de confidentialité / Public privacy preflight

## FR — Objectif et portée

Le nouveau contrôle public-privacy-preflight examine les **nouveaux commits et les lignes ajoutées dans une PR**, sans recopier dans les journaux les valeurs trouvées. Il vérifie aussi les adresses d'auteur et de committer Git. L'analyse n'a aucun accès à Home Assistant, n'écrit aucun contenu externe et s'exécute avec permissions GitHub vides et identifiants Git non persistants.

**Bloquant :** signature manifeste de secret, chemin personnel absolu, nom de machine local ou identité Git de type nom de machine local ; toute impossibilité d'examiner le diff ou les commits entraîne également un échec.

**Avertissement :** adresse d'auteur Git non anonymisée, adresse électronique non fictive dans des lignes ajoutées, adresse IP privée ou identifiant d'installation potentiel. Ces avertissements sont délibérément non bloquants pour ne pas rendre les PR existantes inutilisables avant reconfiguration des auteurs ; ils nécessitent une revue humaine avant fusion.

Le scanner ignore certains exemples synthétiques documentés (notamment les noms de fichiers d'icônes et quelques noms d'hôtes fictifs). Il ne contient ni valeur d'installation ni identifiant personnel réel.

**Limites :** le nouveau job n'appartient pas aux contrôles obligatoires des rulesets. Le code candidat provenant d'une PR n'est pas une source de confiance, d'où l'absence de secrets et les permissions minimales ; ce contrôle ne peut pas garantir l'absence de contournement intentionnel. Il ne couvre pas tous les commits historiques, les objets Git orphelins, les journaux/actions antérieurs, les archives ni les contenus externes. Maintenir Gitleaks, les protections de branche et l'inspection humaine des contributions. Aucune réécriture historique n'est entreprise.

**Remédiation distincte requérant approbation :** configurer l'identité de signature/commit des outils et du compte GitHub avec une adresse noreply vérifiée, puis envisager le blocage des adresses d'auteur réelles après vérification des PR ouvertes. La réécriture de l'historique et la modification des paramètres du compte sont expressément exclues de cette PR.

## EN — Purpose and scope

The new public-privacy-preflight job inspects **candidate PR commits and newly added lines**, including Git author/committer identity, without printing matched values. It runs without production secrets or Home Assistant access, using empty GitHub permissions and non-persistent checkout credentials.

**Blocking:** high-confidence credential signatures, absolute personal paths, local machine hostnames or local Git identities, and inability to inspect the Git range.

**Warning:** non-noreply Git authors, non-fixture email addresses in added content, private-network addresses and possible installation identifiers. These warnings intentionally remain non-blocking until the existing commit-writing systems can use an approved noreply identity, and must be reviewed privately before merging.

**Limits:** the status is not currently a required ruleset check. A PR-supplied script is untrusted; this job receives no repository secret and is not a hostile-PR security boundary. It does not inspect all old commits, orphaned objects, historical CI logs/artifacts or remote systems. Keep Gitleaks, protected branches and human review. No account-settings change, Git history rewrite, deletion, merge, release or Home Assistant change is included.
