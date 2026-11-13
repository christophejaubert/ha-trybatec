# 🤖 #37 — Sélection historique bornée / Bounded user-selected history

**Décision métier / Business-owner ruling — 13 November 2026.** L'utilisateur contrôle les écarts entre le portail Web Trybatec et les observations API, et contacte le fournisseur si nécessaire. L'intégration signale les anomalies, lacunes et sources sans affirmer une exhaustivité historique globale. / The user owns portal-vs-API discrepancy checks and provider escalation. The integration reports known anomalies, gaps and provenance without asserting all-time supplier completeness.

**Interfaces:** #37 [PR #160](https://github.com/christophejaubert/ha-trybatec/pull/160), #36 [issue](https://github.com/christophejaubert/ha-trybatec/issues/36), C11 [PR #162](https://github.com/christophejaubert/ha-trybatec/pull/162), #88 [issue](https://github.com/christophejaubert/ha-trybatec/issues/88), [convergence #164](https://github.com/christophejaubert/ha-trybatec/pull/164).

## FR — Inventaire probatoire réellement accessible

| Contrat | Fait observé | Ce qu'il ne prouve pas |
| --- | --- | --- |
| `/indexes` (API utilisée) | Identité de lot, fluide, série, index horodatés, indicateur de dépose si présent, sur les fenêtres consultées | L'existence de toutes les générations non renvoyées ; dates exactes de remplacement ; index absents ; exhaustive comparaison portail |
| `/device?id=UUID` | Métadonnées du seul appareil correspondant, si identité confirmée | Inventaire complet ni preuve de toute la période de service |
| `/devices?dealId=...` exploratoire | Répertoire éventuellement accessible ; résultat incertain | Garantie de présence, exhaustivité ou stabilité de ce répertoire |
| C11 #162 | Collecte atomique validée dans son périmètre de compte, fenêtre et cache ; `complete` selon sa règle de couverture | Authenticité de toutes les générations historiques hors réponse ; continuité sans relevés ; dates de remplacement |
| #36 / #37 | Relevés sourcés, variantes, décisions candidates, estimations, empreintes de révision | Approbation authentique jour par jour sans relecture du registre #36 ; état Recorder effectivement persisté |
| #81 / HA Energy | Identifiants techniques et références statistiques observées | Nouvelles générations physiques déduites de suffixes `_2`, suppression sûre d'entités ou unicité de source Energy |

Un justificatif de remplacement daté, un procès-verbal d'intervention ou un registre signé/confirmé par le fournisseur est un **apport facultatif** pour établir des périodes de service précises. Il ne constitue pas un préalable absolu à une **sélection de journées assumée par l'utilisateur**. Ne jamais inventer de date de pose/dépose ou d'index, ni calculer des différences entre deux compteurs physiques distincts.

## Contrat ciblé #37 → #88

Nouveau module purement fonctionnel : `lineage_selected_scope_37.py`.
- `selected_snapshot_37(account_key, preview, lot, fluid, start, end, serials)` calcule une empreinte déterministe d'un **périmètre sélectionné**, de l'état des sources physiques et des lignes journalières. Une empreinte est un contrôle de cohérence/obsolescence, **pas une signature d'authenticité**.
- `assess_selected_scope_37(account_key, preview, selections, verify_user_approval=..., verify_daily_decision_36=...)` produit `lineage_37_bounded_user_selection_v1` en **lecture seule**.
- Chaque sélection contient : `lot`, `fluid`, `serials` physiques distincts, `start/end` au format ISO, `expected_snapshot_fingerprint`, `decision_reference` et la **liste exacte** `accepted_missing_days`. Le compte est porté par le contexte backend ; aucune donnée privée du compte n'est sérialisée telle quelle.
- Les vérificateurs sont des interfaces du **backend de confiance** : l'un revalide l'utilisateur administrateur, le contexte et la décision enregistrée ; l'autre compare chaque estimation avec le **registre réel #36**, la journée, la série physique, la source, le montant mesuré/estimé et `revision_fingerprint`. Une paire de booléens envoyée par le navigateur, un simple hash ou le texte d'une décision globale **n'est jamais** une preuve indépendante.
- L'enveloppe rend `api_trybatec_attestation=non_atteste_par_api_trybatec` y compris lorsque l'utilisateur accepte explicitement la sélection. Une attestation fournisseur n'est pas inventée.
- `candidate_for_independent_88_admission_review=true` est permis sur une période même lorsque l'histoire complète du compte est inconnue **si** la décision utilisateur et toutes les estimations présentes sont rapprochées par les vérificateurs indépendants, les contributions sélectionnées sont cohérentes, aucun doublon ni source inconnue/contradictoire n'existe, et chaque journée absente est explicitement exclue/acceptée. Aucun jour absent n'est converti en consommation zéro ; la continuité vaut `false` si une lacune est acceptée.
- Ce candidat n'est **ni** `admissible`, **ni** une preuve de Recorder/Énergie, **ni** une autorisation de modifier l'installation. Les indicateurs `energy_activation_authorized=false`, `writes=false` restent **invariables**.

### Qualification par génération et fenêtre

| Statut | Définition locale |
| --- | --- |
| **Attestée** | Un document externe facultatif vérifié par un processus indépendant confirme explicitement la portée physique concernée ; le module documentaire séparé `qualify_physical_periods_37` ne certifie lui-même aucune signature |
| **Partielle** | Sources et contributions journalières sélectionnées observées/rapprochées, avec limites documentées ; c'est le statut normal d'une sélection volontaire sans attestation fournisseur |
| **Inconnue** | Aucun relevé fiable ou aucune preuve de la journée/période sélectionnée ; une absence de relevé n'établit ni consommation nulle ni absence de compteur |
| **Contradictoire** | Conflit effectivement détecté : variations d'index incohérentes, statut/source incompatible, double attribution non justifiée, total physique incompatible ou décision #36 non concordante |

**Catégories différentes, à conserver séparément :**
- **Lacune acceptée** : une journée absente explicitement sélectionnée dans `accepted_missing_days` ; elle reste manquante et non attestée, sans index ni volume fabriqués. Le backend #88 doit disposer d'une représentation qui **n'importe pas de zéros fictifs** dans Recorder.
- **Contradiction** : incohérence positive vérifiée. L'utilisateur ne peut pas annuler un conflit réel par simple acceptation.
- **Double comptage** : deux générations le même jour, une date répétée, plusieurs statistiques candidates simultanément sélectionnées, ou des sources Recorder/Énergie concurrentes ; examen #88 obligatoire.
- **Provenance inconnue** : source, numéro physique ou décision journalière non attribuable. Une décision globale ne devient jamais une approbation par journée.

### Seuils d'admission #88 / obligations toujours actives

L6/L7 doit évoluer **dans le mandat distinct #88**, sur sélection explicite, et non à partir d'un drapeau générique `physical_inventory_complete`. Pour un **périmètre borné** :
1. Authentifier et tracer l'administrateur, le compte/lot/fluide/série, les journées, exclusions, version et empreinte de l'instantané au moment de la prévisualisation **puis à nouveau avant l'opération**.
2. Vérifier indépendamment les décisions #36 par jour, par révision exacte et par montant. Une approbation globale non attribuée, une révision périmée ou un décalage de source interdit la candidature.
3. Démontrer avec Recorder natif que **les données réellement importées** correspondent aux quantités quotidiennes sélectionnées, sans écrivain tardif ni reprise concurrente ; un test synthétique réussi ne vaut pas une preuve d'exploitation.
4. Inventorier les anciennes statistiques, les sélections existantes et les sources Energy concurrentes **sur la même fenêtre** ; assurer l'absence d'activation simultanée et de double comptage.
5. Respecter les refus pour conflit réel, double comptage, source inconnue ou jours non acceptés, et conserver un retour en arrière transactionnel. Une lacune acceptée ne doit pas être représentée comme une série quotidienne continue de zéros.
6. En cas d'incertitude sur l'origine de la sélection, le registre réel des décisions, l'état Recorder ou les préférences Energy, **refuser l'écriture** ; l'absence d'inventaire exhaustif du logement **hors fenêtre** n'est en revanche pas, à elle seule, un refus.

**Le code #88 actuel continue de refuser l'admission**, y compris sur sélection bornée : la nouvelle décision métier est un **contrat de modification à évaluer séparément**, pas un déverrouillage réalisé par #37.

### C11 / #162 — observations et intervention utilisateur

C11 peut fournir une fenêtre effectivement consultée et des compteurs observés, mais ne doit pas annoncer les appareils non renvoyés comme inexistants. L'interface devra montrer les bornes, les erreurs et les réserves ; la vérification avec le portail et le signalement à Trybatec relèvent de l'utilisateur. Un statut de collecte complète ne certifie pas les dates de mise en service. L'interface existante n'est pas modifiée par #160.

### Tests et limites

Les tests synthétiques couvrent : deux générations sans date de remplacement inventée, lacune explicitement acceptée, lacune non acceptée, aucun relevé, double contribution journalière, source physique étrangère, conflit d'index signalé, décision absente, mauvaise révision, montant et empreinte de fenêtre corrigés, décision utilisateur absente/non authentifiée. Aucun test ne simule une attestation de fournisseur réel ou l'autorisation d'une écriture HA.

## EN — Scope-limited, provenance-preserving business decision

The user is responsible for comparing the integration's API observations with the Trybatec website and escalating discrepancies. The integration must show known anomalies, source boundaries and provenance but **must not require impossible all-time supplier completeness** to review explicitly selected periods. Physical meter IDs are account/lot/fluid/serial scopes; HA suffixes are technical and never establish replacement generations. Neither unknown dates nor missing indexes are manufactured; indexes belonging to different physical meters are never subtracted.

The optional documentary attestation model remains useful for verified service/installation windows, but **not mandatory** for a scoped user selection. The new bounded read-only contract carries exact physical sources, days, missing-day acceptances, revision-specific estimated contributions and an immutable snapshot fingerprint. Both administrator consent and every approved estimation require **independent trusted-backend matching**. In the absence of independent verification or in the presence of contradictions, duplicates, unknown provenance or unaccepted missing days, fail closed. Accepted gaps stay absent and are never zero-filled; possible scoped review is **not** the same as declaring a complete uninterrupted series.

The output always states `non_atteste_par_api_trybatec`, `global_history_exhaustiveness_proven=false`, `energy_activation_authorized=false` and `writes=false`. A positive read-only `candidate_for_independent_88_admission_review` means only that #88 may examine that *exact window*, after independently rechecking administrator approval, revision-specific #36 decisions, native Recorder readback/late-writer barriers, concurrent Energy statistics and transactional L6/L7 rollback. #88's existing hard veto stays in place until its owners independently adapt and qualify the targeted admission path. No HA operation, identifier migration, merge, release or deletion is part of #160.
