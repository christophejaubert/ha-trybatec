# 🤖 Contrat de qualification par version / Per-version delivery qualification contract

## Principes / Rules

**FR :** chaque préversion ou stable est jugée **sur le code effectivement inclus, activé et annoncé**, et sur les effets que ce code peut produire. Une exigence non livrée, correctement désactivée et non annoncée, **ne bloque pas** une bêta. Le code inactif ne doit pas pouvoir exercer d'effets dangereux. Les critères de première stable [#39](https://github.com/christophejaubert/ha-trybatec/issues/39) ne deviennent pas automatiquement des critères des préversions. Phase 2 [#175](https://github.com/christophejaubert/ha-trybatec/issues/175) et incubateur [#176](https://github.com/christophejaubert/ha-trybatec/issues/176) ne constituent aucun jalon actif.

**EN:** assess each prerelease/stable against its **actually included, enabled and advertised** code and possible side effects. Deferred/disabled, unadvertised functionality is **not a prerelease gate**, provided it cannot create unsafe effects. First-stable criteria (#39) are not automatically inherited by prereleases. Deferred phase 2 (#175) and the incubator (#176) are outside active delivery gates.

### A. Permanents / Always mandatory

- **Sécurité, confidentialité, droits et intégrité / Security, privacy, server authorization and data integrity:** no secret leakage, fabricated observations, destructive effects or unauthorized writes.
- **Non-régression du périmètre annoncé / Non-regression in declared support scope**, including upgrades and disabled feature boundaries.
- **Tests obligatoires et CI sur SHA exact / Mandatory CI and testing on the exact candidate SHA**: no missing, cancelled or failed required check silently treated as success.
- **Identité de livraison / Delivery identity:** exact SHA, manifest/version, release notes, evidenced limitations; separate owner consent for **merge, publish, install**.
- **Recorder/Énergie / Recorder/Energy:** no unverified units, cross-meter deltas, misleading coverage or overlapping consumption; disabled features must fail closed.

### B. Conditionnels / Conditional on actual inclusion, activation or exposure

- **Migration**: read-only plan/diff, dependency inventory, separate approval, recoverable backup and demonstrated restoration whenever necessary, concurrency/rollback safety.
- **Recorder/Energy writes**: exact-scope evidence and isolation, durable versioning/journal, idempotence, concurrency and late-writer tests, safe refusal/quarantine, confirmed admin transaction, readback and rollback; **never enable unsafe writes**.
- **Purge, reset, uninstall cleanup**: only if actually delivered; preview, explicitly authorized scope, irreversible-impact warning, verified protection.
- **Multiple dwellings, advanced provenance/replacements**: only when explicitly taken out of incubator and delivered. Residual stable integrity guards always apply.
- **Compatibility**: test platforms, architectures and HA versions **actually declared supported**. Prospective/unsupported platforms are tracked as risks, not invented release obligations.
- **Upgrade path**: test migrations that the release really performs or can trigger; do not require unrelated historical migration paths.
- **Actual user installation acceptance** belongs to the owner; not an automatic prerequisite for beta publication when isolated synthetic testing and shipped safety gates have qualified.

### C. Première stable / First stable only

First-stable standalone F01/F04–F09, F11, F12, F54 and **F55 under #42** are tracked via #39 and the [F matrix](./REQUIREMENTS_F01_F62_FR_EN.md). Stable packaging, metadata, HACS/hassfest, released version, documentation, security and explicit publication approval remain #39. Do not claim a stable release until verified.

### D. Phase 2 only / Phase 2 exclusively

C01–C14, P01–P10 and J07–J08 belong to [#175](https://github.com/christophejaubert/ha-trybatec/issues/175). No automatic HACS catalog submission or maintenance initiative.

## Modèle court de livraison / Compact release dossier template

| Champ / Field | Valeur attendue / Expected content |
|---|---|
| Version et SHA / Version and SHA | Tag candidat et commit exact / Exact candidate commit |
| Périmètre livré / Delivered scope | Fonctions nouvelles/corrigées et issues propriétaires / New/fixed features and owner issues |
| Désactivé / Disabled | Features disabled, reason, verified non-effect and outward communication |
| Tests / Testing | Mandatory jobs, workflow run URLs, SHA, isolated positive & negative paths |
| Preuves et limites / Evidence and limits | Developed / tested / actually accepted / merged / published / installed — each separately |
| Bloquants réels / Actual blockers | Proven safety/integrity/required-CI or included-feature failures only |
| Non-bloquants / Non-blockers | Known limitations, prospective checks, first-stable-only and deferred features |
| Décisions / Decisions | Explicit merge, release, installation, migration/activation approvals separately |

**FR — Critères R05/T09 :** ne qualifier que les chemins de migration inclus ou déclenchables. **R04/J04 :** recette réelle distincte, sans blocage générique des bêtas. **T11–T14 :** matrice de compatibilité publiée et support déclaré. **D13/D14 :** documenter correctement les effets réels sans imposer une purge hors périmètre. **R01/J01 :** cadrage des F déjà arbitré le 14/11/2026, ne pas redemander la même décision.

**EN — R05/T09:** only delivered/triggerable migration paths. **R04/J04:** real acceptance separately controlled, not a blanket beta gate. **T11–T14:** declared supported environment matrix. **D13/D14:** document actual behavior without requiring a deferred full purge. **R01/J01:** F scope already decided on 14 November 2026; do not reopen without new owner decision.
