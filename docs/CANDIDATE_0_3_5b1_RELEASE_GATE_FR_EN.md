# 🤖 0.3.5b1 — Dossier de candidate / Candidate delivery gate

**État au 14 novembre 2026 / State as of 14 November 2026.** Dépôt `christophejaubert/ha-trybatec`. Branche propriétaire de convergence : PR #164. Cette préparation ne constitue ni fusion, ni release, ni installation. / This draft is not a merge, release or deployment.

## FR — Périmètre effectivement qualifié

- **Cible :** `0.3.5b1`, depuis `main` `8d621da9703b40662800b4a7c286707e8a7f895f` et release `0.3.4b1`; le manifeste de la branche candidate est mis à `0.3.5b1`, **sans publication**.
- **Éléments à livrer (code présent, tests synthétiques) :** panneau C1–C11, mutualisation des données historiques, accès/notifications, identité physique et filiation, saisie native des tarifs, accessibilité/navigation, réservations et journalisation Recorder, contrôles de sélection L6 et moteur L7 testé isolément.
- **Preuve native de bout en bout :** `integration_tests/test_ha_native_36_37_l6_l7_single_transaction.py` vérifie dans une transaction les producteurs #36/#37 et le collecteur L6 **sans substituer des reçus fictifs** ; sauvegarde native puis écriture/readback L7 isolée. La CI [#43580386393](https://github.com/christophejaubert/ha-trybatec/actions/runs/43580386393) a validé **328 tests HA** au SHA code `17015db41eaa74119deff28c330c929391aea1fa`, y compris le refus d'un écrivain Recorder tardif. Les tests de restauration, interruption, concurrence, rollback et archive corrompue sont inclus.
- **Contrats de sécurité :** identifiants propres Trybatec, conservation par génération physique, absence de faux zéro, contrôle de dérive et quarantaine. Les API HA ne garantissent pas l'exclusion de tous les écrivains privilégiés futurs ; pas de réparation destructive automatique.
- **Limite fonctionnelle explicite :** **l'ajout groupé dans Energy L7 est désactivé en production** : `NATIVE_ENERGY_BULK_WRITES_ENABLED_88=False`, refus de confirmation WebSocket et service admin. Il est inexact de présenter la version comme un ajout groupé opérationnel. Recorder, migrations des identités et restaurations réelles ne sont pas activés automatiquement.
- **Recette à effectuer séparément après autorisations :** ergonomie réelle, compteurs déposés, historique et unités, CET en kWh sur l'Énergie de l'installation réelle. La CI ne certifie ni fonctionnalité métier déployée, ni absence de bugs.
- **Compatibilité approuvée par le propriétaire :** HA Core **`2026.11.0` suffit pour `0.3.5b1`**. Aux cycles suivants, démarrer sur la **dernière version stable officielle HA**, reconstruire les verrous SHA-256 et tests ; conserver les anciennes versions en non-régression si pertinent.

## EN — Verified scope and bounded risks

- Candidate `0.3.5b1`, derived from `main 8d621da` (published `0.3.4b1`). Manifest and bilingual notes prepared on PR #164, **not published**.
- Integrated code includes panel C1–C11, shared account history evidence, access and identity safeguards, annual tariff UI, Recorder versioned durable attempts, physical lineage, native L6 selection and a guarded L7 transaction engine.
- **True isolated HA Core `2026.11.0` test** invokes actual #36 Recorder SQL, #37 physical lineage, authenticated L6 collector and one L7 backup/commit/readback. It uses fictional supplier data but **does not replace the native L6 producer with synthetic proofs**. [Exact-SHA CI #43580386393](https://github.com/christophejaubert/ha-trybatec/actions/runs/43580386393) passed 328 HA integration tests, including a late Recorder SQL writer refusal. Additional native backup/restore and recovery tests passed.
- **Deliberate exclusion:** live Energy L7 bulk enrollment is still **off** in the product (`NATIVE_ENERGY_BULK_WRITES_ENABLED_88=False`, WebSocket/admin confirmation refused). Do not claim a fully operational bulk-enrollment beta. The bounded contract detects external drift but cannot prevent every future privileged external edit.
- Live acceptance, historical identifier migration, supplier-side actions, Recorder/Energy writes and Home Assistant installation/restoration require distinct user approval. CET real dashboard acceptance is post-publication/post-installation, not a synthetic CI claim.
- The owner accepts `2026.11.0` for this candidate; future compatibility cycles begin with the latest officially released **stable** Home Assistant, with updated hash-locked dependencies and native regression evidence.

## Contrôles de livraison / Delivery checklist

| Check / Contrôle | Status / Statut |
|---|---|
| Converged tests #36→#37→L6→L7 | PASS on SHA `17015db4`, HA isolated |
| Source owner #158 native transaction and rollback | PASS `3040e935`, HA isolated |
| CI #164 before version/docs bump | PASS at `14b53508f4879a4feb0cf78beb93883d193d036a` : [compatibility](https://github.com/christophejaubert/ha-trybatec/actions/runs/43580662758), [browser](https://github.com/christophejaubert/ha-trybatec/actions/runs/43580662756), [accessibility](https://github.com/christophejaubert/ha-trybatec/actions/runs/43580662763), [security](https://github.com/christophejaubert/ha-trybatec/actions/runs/43580662793) |
| **CI new manifest/release-note SHA** | **Pending — mandatory exact-SHA recheck after this preparatory commit** |
| Manifest `0.3.5b1` + FR/EN notes | Prepared on #164, pending CI |
| Public privacy review | Manual check of scope and incremental changes required before merge |
| Branch protections and post-merge `main` CI | To verify on approved merge only |
| Live Home Assistant business acceptance | Not performed — requires separate installation authorization |
| Real Energy L7 bulk-enrollment operation | **Disabled; not qualified for user deployment** |
| Merge / Publish / Install | **Not authorized by preparation; each requires separate explicit decision** |

## Issues encore ouvertes / Open issues — 13

| # | Sujet / Subject | Qualification / Remaining gate |
|---|---|---|
| [#34](https://github.com/christophejaubert/ha-trybatec/issues/34) | DJU / future degree-day heating smoothing | Deferred; not part of the candidate |
| [#35](https://github.com/christophejaubert/ha-trybatec/issues/35) | Access, reauthentication and alerts | Code and CI; live acceptance pending |
| [#36](https://github.com/christophejaubert/ha-trybatec/issues/36) | Recorder history, revisions and guard | Isolated native Recorder tested; production writes not activated |
| [#37](https://github.com/christophejaubert/ha-trybatec/issues/37) | Physical lineage and replacements | Physical-generation/day code tested; no destructive identity migration |
| [#39](https://github.com/christophejaubert/ha-trybatec/issues/39) | HACS/Marketplace official listing | Preparation only, no official catalog submission |
| [#42](https://github.com/christophejaubert/ha-trybatec/issues/42) | Annual tariff UI | Code and synthetic UI tests; production acceptance pending |
| [#45](https://github.com/christophejaubert/ha-trybatec/issues/45) | MOE/release tracking | Release decision, publication, installation separate |
| [#70](https://github.com/christophejaubert/ha-trybatec/issues/70) | Brand and accessibility | Synthetic coverage passed; real UI acceptance pending |
| [#81](https://github.com/christophejaubert/ha-trybatec/issues/81) | Stable identities | New-account handling and safe preview; no production migration |
| [#83](https://github.com/christophejaubert/ha-trybatec/issues/83) | Guided setup UI | Synthesized browser tests; production acceptance pending |
| [#84](https://github.com/christophejaubert/ha-trybatec/issues/84) | Meter details UI | Synthetic UI checks; production acceptance pending |
| [#88](https://github.com/christophejaubert/ha-trybatec/issues/88) | Bulk Energy enrollment | Native E2E tested, but production route deliberately disabled |
| [#155](https://github.com/christophejaubert/ha-trybatec/issues/155) | Panel and history discovery C1–C11 | Converged and synthetic-qualified; real acceptance pending |

## PR encore ouvertes / Open pull requests — 35

GitHub a été rafraîchi à cette préparation. Sept PR historiques ont déjà été fermées sans fusion avec preuve dans #45 ; ne pas les réintroduire dans l'inventaire. / Seven earlier PRs were closed without merge; do not re-count them.

| Groupe / Group | PR actives / Active PRs | Nombre |
|---|---|---|
| Owner / convergence | [#158](https://github.com/christophejaubert/ha-trybatec/pull/158), [#159](https://github.com/christophejaubert/ha-trybatec/pull/159), [#160](https://github.com/christophejaubert/ha-trybatec/pull/160), [#164](https://github.com/christophejaubert/ha-trybatec/pull/164) | 4 |
| Functional in progress | [#156](https://github.com/christophejaubert/ha-trybatec/pull/156), [#162](https://github.com/christophejaubert/ha-trybatec/pull/162), [#163](https://github.com/christophejaubert/ha-trybatec/pull/163) | 3 |
| Independent acceptance and oversight | [#157](https://github.com/christophejaubert/ha-trybatec/pull/157), [#161](https://github.com/christophejaubert/ha-trybatec/pull/161), [#165](https://github.com/christophejaubert/ha-trybatec/pull/165), [#166](https://github.com/christophejaubert/ha-trybatec/pull/166), [#167](https://github.com/christophejaubert/ha-trybatec/pull/167) | 5 |
| Historical or stacked — require per-path comparison before any closure | [#82](https://github.com/christophejaubert/ha-trybatec/pull/82), [#118](https://github.com/christophejaubert/ha-trybatec/pull/118), [#120](https://github.com/christophejaubert/ha-trybatec/pull/120), [#124](https://github.com/christophejaubert/ha-trybatec/pull/124), [#125](https://github.com/christophejaubert/ha-trybatec/pull/125), [#127](https://github.com/christophejaubert/ha-trybatec/pull/127), [#128](https://github.com/christophejaubert/ha-trybatec/pull/128), [#130](https://github.com/christophejaubert/ha-trybatec/pull/130), [#132](https://github.com/christophejaubert/ha-trybatec/pull/132), [#133](https://github.com/christophejaubert/ha-trybatec/pull/133), [#136](https://github.com/christophejaubert/ha-trybatec/pull/136), [#137](https://github.com/christophejaubert/ha-trybatec/pull/137), [#139](https://github.com/christophejaubert/ha-trybatec/pull/139), [#143](https://github.com/christophejaubert/ha-trybatec/pull/143), [#144](https://github.com/christophejaubert/ha-trybatec/pull/144), [#145](https://github.com/christophejaubert/ha-trybatec/pull/145), [#146](https://github.com/christophejaubert/ha-trybatec/pull/146), [#149](https://github.com/christophejaubert/ha-trybatec/pull/149), [#150](https://github.com/christophejaubert/ha-trybatec/pull/150), [#151](https://github.com/christophejaubert/ha-trybatec/pull/151), [#152](https://github.com/christophejaubert/ha-trybatec/pull/152), [#153](https://github.com/christophejaubert/ha-trybatec/pull/153), [#154](https://github.com/christophejaubert/ha-trybatec/pull/154) | 23 |

**Contrôle de complétude / Completeness:** 35 PR ouvertes, 13 issues ouvertes. Pas de clôture sur la seule base d'une CI réussie. Avant chaque clôture : comparer les blobs Git, préserver les preuves et vérifier les travaux restant utiles. / Every closure requires evidence-based branch comparison and preservation of unique tests or unmerged work.

## Décisions restantes / Remaining release decisions

1. **FR :** l'utilisateur doit choisir explicitement entre publier une bêta **en sachant que L7 reste indisponible**, ou conserver cette candidate en attente d'une autorisation et qualification distinctes pour rendre L7 opérationnel dans une future version. Ne pas élargir implicitement les permissions.
2. **EN:** the owner must explicitly decide whether to ship the beta **with bulk Energy writes unavailable** or defer until separately scoped L7 production activation is developed and accepted.
3. La **fusion** de #164, la **release/tag** `0.3.5b1`, l'**installation** HA, la **migration** et la **restauration** sont des actions distinctes nécessitant chacune une autorisation appropriée. / Merge, tag/release, installation, migration and restore remain separately authorized actions.
4. La release utilise seulement le workflow manuel [publish-experimental.yml](../.github/workflows/publish-experimental.yml) à partir de `main` avec SHA exact et contrôles `push` post-fusion. Aucune publication automatique à partir de ce document. / The manual workflow rejects a non-main SHA, version mismatch or missing successful post-merge push CI.
