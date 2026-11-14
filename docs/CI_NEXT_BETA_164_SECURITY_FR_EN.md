# 🤖 Qualification sécurité de convergence #164 / Convergence security qualification #164

**Date / Date:** 2026-11-13  
**Repository / Dépôt:** `christophejaubert/ha-trybatec`  
**Production main:** `8d621da9703b40662800b4a7c286707e8a7f895f` (`0.3.4b1`)  
**Reference heads at audit / SHA observés:** #157 `c0cf7a71e51cbd4255b474758b61d3296f80c74b` (initial qualified evidence); #158 `4d1f2eef34637957bbea97369482ebe6c2ceaa8e`; #164 `59ca822cbe8590151d32fc1db9061d4a79d19870`. Refresh SHAs before any decision; #157 receives additional changes after its initial proven head.

## FR — Faits, limitations et conditions de qualification

### Gitleaks #158 / #164
- [CI #158](https://github.com/christophejaubert/ha-trybatec/actions/runs/43419404815), SHA `4d1f2eef…`: `Detect accidentally committed secrets` **succès**, 8 commits analysés par le scanner différentiel ; `Recheck reachable Git history (schedule parity)` **échec**, une détection, code sortie 2. Aucun détail ni valeur de détection publiés. La CI de la PR empilée est un échec réel ; le contrôle `trusted-workflow-integrity` est ignoré puisque sa base n'est pas `main`.
- [CI #164](https://github.com/christophejaubert/ha-trybatec/actions/runs/43422474401), SHA `59ca822c…`: les deux étapes Gitleaks et le contrôle synthétique (#157) sont **réussis**. #164 reprend les fichiers utiles sans transporter l'ensemble des commits historiques de #153.
- `.gitleaksignore` de #158 conserve une seule empreinte, contrairement aux **deux empreintes ciblées** de `main`/#164. L'absence de la deuxième est une hypothèse plausible de la détection historique ; l'identité exacte de l'occurrence n'est **pas vérifiée** par les journaux expurgés disponibles. Ne pas ajouter d'exclusion ou altérer le scan sans preuve spécifique (règle, commit, chemin, ligne, revue humaine, sans valeur divulguée).
- Le scan historique volontairement bloquant sur les refs disponibles et le scanner différentiel doivent tous deux rester actifs ; ne jamais déduire la qualification d'un SHA de la réussite d'un autre. Les tests #157 utilisent une histoire saine (sortie 0), puis une clé **synthétique en mémoire**, effacée de HEAD par un commit ultérieur mais refusée sur toute l'histoire (sortie 2), avec journaux masqués.

### Confidentialité
- Avant intégration des nouveaux changements #157, le workflow `public-privacy-preflight` de `main` est `pull_request_target` **limité aux PR visant main** ; les PR empilées comme #158 ne sont pas couvertes par ce check de confiance. C'est une lacune de couverture, pas une réussite implicite.
- Le durcissement proposé sur #157 supprime ce filtre de branche **sans modifier les permissions** : `contents: read`, code de scanner chargé exclusivement depuis `main`, aucun checkout ni exécution du contenu de PR, objets Git collectés comme données, validation stricte du SHA d'événement, erreurs en mode bloquant. Il interdit par défaut les blobs binaires dont le contenu ne peut pas être inspecté. Les tests de régression vérifient l'absence de filtre silencieux et le refus d'un binaire synthétique.
- Les avertissements de réseau privé, identifiants potentiels et courriels Git ordinaires restent à examiner : une réussite n'est **pas une garantie d'absence de données personnelles**. Le contrôle intervient **après publication des commits dans un dépôt public** ; la prépublication de données réelles est interdite. Vérification manuelle expurgée obligatoire avant tout push, même avec checks verts.
- Pour rendre le contrôle obligatoire dans le ruleset #26796600 : **(1)** intégrer le workflow/scan de confiance après revue sur un SHA qualifié ; **(2)** constater son exécution sur PR main et PR empilée sans exécution du code candidat ; **(3)** vérifier les permissions et la politique GitHub Actions d'événement `pull_request_target`, notamment le changement annoncé au 2 décembre 2026 ; **(4)** vérifier que le contexte `public-privacy-preflight` est stable et non ignoré ; **(5)** obtenir une autorisation utilisateur **spécifique** pour modifier le ruleset ; **(6)** requalifier un SHA combiné après changement. Aucun changement de règle n'est inclus ici.
- Référence de sécurité : [GitHub Docs – Securely using pull_request_target](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target).

### Matrice candidate intégrée, à réévaluer pour chaque nouveau SHA

| Classe | Contextes | Règle main | Résultat sur #164 `59ca822c…` |
| --- | --- | --- | --- |
| Obligatoire | Python 3.13/3.14, Ruff, HACS, Hassfest, Gitleaks, HA runtime/storage, HA import récent, persistance gate, trusted workflow integrity | 10/10 obligatoires | 10/10 succès sur SHA observé |
| Sécurité complémentaire | CodeQL Python/Actions/JS, supply-chain, privacy preflight | Pas dans les 10 contexts | succès observé sur #164 ; privacy non obligatoire |
| IHM | Navigateur synthétique FR/EN desktop/mobile et accessibilité synthétique | Pas dans les 10 contexts | succès sur SHA observé ; **pas une recette HA réelle** |
| Publication | `publish-experimental.yml` : `workflow_dispatch`, acteur propriétaire, `main` SHA exact approuvé, notes FR/EN, CI `push` post-fusion, absence de tag/release existants | Manuel uniquement | Aucune publication autorisée ni réalisée |
| Métier | #155/C1–C11, #36 Recorder, #37 filiation, #88 Énergie/L6–L7 | Preuves indépendantes requises | Non acquises par réussite CI, vérifier blocages MOE |
| Production | Fusion / release / installation / migration / écritures Recorder/Énergie / restauration | Autorisations distinctes | Non autorisées |

**Le verdict de sécurité sur la candidate change dès que sa tête change.** Retester sur le **SHA combiné final** les 10 statuts obligatoires + sécurité complémentaire + navigateur/a11y + contrats fonctionnels. Ne jamais fusionner la PR de preuve #154.

## EN — Findings, limitations and acceptance gates

- [#158 CI](https://github.com/christophejaubert/ha-trybatec/actions/runs/43419404815) passed Gitleaks' incremental PR step (8 commits), but its reachable-history step reported exactly one finding and exited 2. Its old `.gitleaksignore` contains one narrowly scoped fingerprint, whereas main/#164 contains two. The missing fingerprint may explain the finding, **but the sanitized available logs do not establish the exact fingerprint**. Do not suppress, allowlist, rewrite or bypass the result without isolated evidence and review.
- [#164 CI](https://github.com/christophejaubert/ha-trybatec/actions/runs/43422474401) passed both Gitleaks steps on its own composed head, and includes #157's negative clean-history / positive previously-removed synthetic-secret checks. These are distinct commit ancestries and results; #158 is not retroactively green.
- The current trusted privacy preflight on main only handles PRs targeting main, not stacked #158. The proposed #157 changes extend a **trusted main-only, read-only** `pull_request_target` scanner to all PR base branches and fail closed for opaque binary diffs. No candidate code is executed. CI on #157 alone cannot prove that GitHub has deployed the widened trusted trigger: it must first be merged **with separate approval**, then observed on actual stacked PRs.
- Privacy scanning is necessarily post-push; a public commit has already been exposed before a CI result. Ambiguous private-network/identifier warnings remain advisory, and manual pre-publication sanitization is indispensable.
- Promotion to mandatory branch protection needs a verified trusted workflow on main, real check visibility on PRs (including stacked), an event-policy review for `pull_request_target` before GitHub's announced 2026-12-02 enforcement, confirmed stable context identity, and **separate user authorization to edit ruleset #26796600**.
- The 10 mandatory main checks, CodeQL, supply-chain, privacy, browser/a11y and synthetic Recorder/Energy tests must all be evaluated against **the exact future combined head SHA**. Browser tests do not demonstrate live Home Assistant acceptance; application/transactional evidence remains owned by #36/#37/#88/#155. No merge, tag, release, branch-rule change or HA operation is authorized by this document.

**Sources:** GitHub ruleset #26796600, PRs #157/#158/#164, workflow runs above, and [Gitleaks documentation (Git log scanning and fingerprint exemptions)](https://github.com/gitleaks/gitleaks).
