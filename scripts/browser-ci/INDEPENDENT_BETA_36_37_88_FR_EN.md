# 🤖 Recette indépendante de la candidate / Independent beta acceptance

**Dépôt / Repo:** \`christophejaubert/ha-trybatec\`.  
**Périmètre / Scope:** #155 C1–C11, #36 Recorder, #37 physical lineage, #88 L6/L7, convergence PR #164, independent test PRs #165–#167.  
**Règle / Rule:** no real vendor account, real meter identifiers, private installation data, HA production writes, merges or releases.

## 1. Provenance des résultats / Exact SHA evidence

- Dernière **composition réellement qualifiée**, avant la consolidation des tests dans #164 : checkout GitHub \`6814646b5c282bd3db514c5ee8bc3f4428ac2815\`, parent fonctionnel #164 \`f5bb2478d5fa80cf02f0d81cb1bdcb34a88f57be\`, tests #167 \`d79ecaad70d7b1cae9109090eae0eba96aa23c0b\`.
- [CI compatibilité / Compatibility CI 43503646197](https://github.com/christophejaubert/ha-trybatec/actions/runs/43503646197): **1 215/1 215 tests Python réussis** sous Python 3.13 et 3.14, **53 subtests**, **79,24 % de couverture** (seuil 75 %). Inclut les trois fichiers indépendants ci-dessous.
- [CI navigateur / Browser 43503647266](https://github.com/christophejaubert/ha-trybatec/actions/runs/43503647266): **96/96 contrôles transversaux + 58/58 C11 PASS** et sept vues sur huit matrices FR/EN, desktop/mobile, light/dark ; navigateur synthétique uniquement.
- La convergence #164 a ensuite intégré ces **trois fichiers de tests**. Une CI réussie sur un SHA antérieur ne qualifie pas automatiquement le HEAD ultérieur. Le présent ajout de recette sur #167 doit être évalué à nouveau sur son checkout exact.
- **EN:** The above is an observed SHA-specific historical green, not an automatic qualification of subsequent HEADs. The convergence incorporated the same three independent tests after this run. Requalify any later composition.

## 2. Matrice de recette / Acceptance matrix

Statuts / status: **PASS-SYN** = executable synthetic proof; **STATIC** = source/contract reviewed; **NO-PROD** = cannot attest real production; **BLOCKED** = deliberately non-admitted; **PENDING** = must rerun on new exact head.

| Critère métier / Business criterion | Méthode indépendante / Independent method | Résultat et limites / Outcome and limits |
|---|---|---|
| #36 identité immuable | Known Recorder, Energy, legacy ID collisions; prior quarantined tombstone and attempt token; same-revision source mutation | **PASS-SYN** rejects collisions/stale revisions. No atomic cross-writer ID reservation proven **NO-PROD** |
| #36 reprise/crash | Missing, partial, complete persisted readback, quiescent queue and ambiguous late enqueue | **PASS-SYN** safe retry never inferred from preflight; durable cross-writer fencing **NO-PROD** |
| #37 deux générations, compteurs déposés | Register levels OLD 900 and NEW 200, actual bridge daily 2 + 4, separate contributor serials | **PASS-SYN** 6 consumption, not negative cross-meter register delta |
| #37 provenance, décisions | Selected bounded interval, approved missing day without invented 0, changed source revision, overlapping generation/double count, unknown status | **PASS-SYN** partial user-reviewed candidate, revoked on contradictions; no global supplier exhaustiveness claimed |
| #88 L6 admission positive | New v2 three observed dates plus **one absent date with exact explicit approval**, partial scope and independent #36/#37/HA-fingerprint specimens | **PASS-SYN** \`eligible_for_scoped_review\`, **never** authorization to write |
| #88 L6 refus | 19 counterfactuals: stale reference, unpersisted, wrong unit, duplicate, contradictory amount/day, missing/revised approval, selected competing Energy statistic, unclassified external ref, changed live/disk, external writer barrier absent | **PASS-SYN**, each blocks and writes remain false |
| #88 L7 moteur transactionnel | Spy adapter records admin, exclusive lock, collect, plan digest, backup, verify, prepared journal, write, disk flush/readback, verified journal; backup/journal failure; partial write rollback; third-party race; idempotence | **PASS-SYN** on fake port. Native HA backup/rollback after restart **NO-PROD** |
| #88 Entrées serveur natives | Direct actual websocket body (without decorators in isolated test), real admin service and read-only port auth method, poisoned I/O | **PENDING** added independent tests. Native mutation route deliberately **BLOCKED** by hard-coded gate; no production write |
| #88 CET chauffage kWh | Native scoped validator must reject mapping CET to an unqualified HA gas source | **PASS-SYN BLOCKED** gas shortcut; true heat-category compatibility to be recettée **after** installation, not misrepresented as gas |
| C1–C10, C11 | Actual panel DOM and status WS with synthetic fixtures, navigation/date accessibility and 7 states; FR/EN desktop/mobile dark/light | **PASS-SYN** on recorded SHA; not a screen-reader or live HA qualification |
| Pas de lectures/écritures implicites | Existing C11 status cache test and new native-route poison; no supplier calls or Recorder/Energy mutations from navigation | **PASS-SYN + STATIC**; lack of live HA monitoring **NO-PROD** |
| Fusion, release, installation | GitHub main SHA, PR merged fields, release/tag separately verified | The candidate has **not** been fused, released or installed by this qualification |

## 3. Critères de refus / Fail-closed acceptance principles

1. **FR:** Relevé API absent ≠ index zéro ; une journée manquante reste absente si elle est explicitement acceptée, jamais artificiellement mesurée. **EN:** Missing vendor reading is not a zero index.
2. **FR:** Les index de générations physiques distinctes ne sont pas soustraits. Seules les consommations calculées dans chaque génération sont additionnables. **EN:** Never subtract different physical meters' cumulative indexes.
3. **FR:** L'utilisateur peut approuver un périmètre partiel sans attester toute l'histoire du fournisseur. Provenance, contradictions, révisions et limites demeurent visibles ; ce choix ne contourne pas #36, #37 ou L6. **EN:** Scoped user acceptance never bypasses native evidence.
4. **FR:** Un résultat synthétique \`eligible_for_scoped_review\` n'est ni l'admission native effective ni une autorisation d'exécuter L7. **EN:** A synthetic L6 admission is not an executable native write permit.
5. **FR:** L7 natif requiert preuves indépendantes de non-concurrence, sauvegarde restaurable vérifiée, journal durable et recette HA autorisée séparément ; aucun bouton ou statut CI ne peut lever les verrous. **EN:** Native HA safety remains an independent release gate.
6. **FR:** Le CET en kWh décrit du chauffage. Une source \`gas\` native Home Assistant ne peut être présumée correcte par une simple équivalence d'unités. **EN:** kWh is not proof of a gas category.

## 4. Méthodologie et frontières / Method and boundaries

- **Code applicatif réellement invoqué** par les tests indépendants : \`history_quarantine_design_36\`, \`history_recorder_recovery_l2\`, \`lineage_selected_scope_37\`, \`lineage_history_bridge_37\`, \`energy_bulk_scoped_l6_88\`, \`energy_bulk_transaction\` et les fonctions natives en lecture/refus ; nous ne comparons pas uniquement des chaînes de code.
- **Aucune fiction d'exhaustivité globale** : les fixtures positives attestent seulement des périodes et décisions choisies ; les contradictions ne sont jamais rendues admissibles par un simple drapeau client.
- **Le port de test L7 n'est pas le port HA**. Le test du chemin natif ne déclenche jamais de vraie sauvegarde, journalisation ou écriture.
- **Tests développés ≠ tests passés ≠ recette réelle**. Chaque nouvelle composition requiert sa propre CI. Les PR #165 (ancien main) et #166 (#156 sans backend #162) conservent leurs échecs attendus.
- **EN:** Real business code is exercised, while all data sources and I/O adapters remain synthetic. Native HA restoration and live-user acceptance are deliberately not claimed. Merge/release/installation are independent user decisions.
