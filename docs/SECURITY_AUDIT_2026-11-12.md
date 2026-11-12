# Audit du 12 novembre 2026 / Security and quality audit — 12 November 2026

Périmètre / Scope: configuration publique du dépôt, workflows, consignes et métadonnées GitHub. This is **not** an exhaustive code audit or a Home Assistant production acceptance.

## FR — Éléments vérifiés

- Base observée : main @ c9babb6379213e7585d74ab63872f20f54f1a3c1 ; PR #82 en brouillon sur feat/81-stable-physical-identity au moment de l'audit.
- Ruleset 26796600 actif pour la branche par défaut : PR obligatoire, conversations résolues, vérifications à jour (strictes), fusion squash, suppression et non-fast-forward interdits, aucun acteur autorisé à contourner.
- Dix noms de contrôles obligatoires : pure-tests (Python 3.13), pure-tests (Python 3.14), ruff-essential, hacs, gitleaks, ha-runtime-and-storage, latest-homeassistant-import, hassfest, decision-persistence-gate et trusted-workflow-integrity.
- Ruleset 26800141 actif : gel des modifications, suppressions et réécritures de security/trusted-ci-resolver-20261108.
- Actions épinglées à un SHA, secrets scanning avec Gitleaks, tests de persistance/Recorder, pipeline de publication expérimentale uniquement sous workflow_dispatch explicite.
- CodeQL a signalé des analyses réussies sur le SHA de main observé ; le navigateur synthétique a aussi produit une conclusion de succès. Leur réussite n'est pas une recette métier.
- docs/CI.md mentionnait neuf contrôles et une ancienne branche de résolution ; corrections documentaires proposées dans le présent chantier.

## FR — Lacunes ouvertes et décisions

1. Le fichier CONTRIBUTING ne documentait pas de Definition of Done complète ni de modèle PR ; combler dans la PR gouvernance.
2. Ruff général et formatage sont indicatifs ; mesurer la dette puis imposer une règle progressive sans casser les PR fonctionnelles.
3. Aucun seuil de couverture total bloquant ; établir d'abord les chiffres, éviter les fausses preuves et les tests ignorés.
4. La reproductibilité n'est pas totale : dépendances transitives et image ubuntu-latest non figées.
5. Les validations navigateur et CodeQL ne figurent pas dans la liste des dix contrôles requis. Ne pas ajouter de statut obligatoire sans modification administrative vérifiée des rulesets.
6. La revue humaine de CI détenue par le propriétaire reste nécessaire : trusted-workflow-integrity vérifie la provenance des fichiers sensibles mais ne certifie pas leur sûreté.
7. Aucun audit de restauration sur production ni recette métier complète ne sont attestés par ces contrôles ; aucune action production autorisée dans ce chantier.

## EN — Verified baseline and remaining gaps

Main SHA c9babb6379213e7585d74ab63872f20f54f1a3c1; PR #82 was an unrelated functional draft. Active ruleset 26796600 enforces PRs, current required checks, squash merges, resolved conversations, no deletion, no force push and no bypass actors. Its **ten** required statuses are pure-tests (Python 3.13), pure-tests (Python 3.14), ruff-essential, hacs, gitleaks, ha-runtime-and-storage, latest-homeassistant-import, hassfest, decision-persistence-gate, and trusted-workflow-integrity. Ruleset 26800141 protects the trusted resolver reference.

Existing controls include pinned Actions, Gitleaks, isolated Recorder/persistence CI, synthetic browser checks, and successful CodeQL checks seen on the observed main SHA. Those results neither certify all vulnerabilities absent nor establish production acceptance.

Open work: introduce a shared DoD and PR template; measure comprehensive lint, formatting and coverage debt before tightening; improve lock/reproducibility and workflow analysis without duplicate tools; review CI workflow changes manually; confirm status ruleset migrations before introducing new mandatory status names; separately test real backup/restore and Home Assistant acceptance under explicit authorization. No Home Assistant change, tag or release is authorized by this audit.
