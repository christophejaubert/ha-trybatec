# 🤖 #155 — Matrice de qualification indépendante / Independent qualification matrix

**FR — Référence figée :** `main` `8d621da9703b40662800b4a7c286707e8a7f895f`. Développement concurrent #156 : SHA mobile, à recontrôler à la réconciliation. Tests ajoutés sur une branche **distincte** et limitée à `scripts/browser-ci/`. Aucune donnée réelle, aucune connexion fournisseur, aucun accès à Home Assistant, aucune écriture Recorder/Énergie. Une recette navigateur synthétique, même réussie, n'est **pas** une recette sur HA.

**EN — Fixed baseline:** `main` `8d621da9703b40662800b4a7c286707e8a7f895f`. Concurrent #156 head is moving and must be rechecked. This test-only branch modifies `scripts/browser-ci/`. No real meter data, vendor requests, HA connections, Recorder/Energy writes or production acceptance.

## Matrice / Coverage

| Critère | Contrat vérifié / Assertion | Exécutable ou preuve antérieure | Limite / Boundary | Propriétaire des corrections |
|---|---|---|---|---|
| **C1** | Entités indisponibles 0=succès, >0=alerte, inventaire inconnu=neutre ; icône + texte | `qualification_155_cross.cjs` dans 8 combinaisons ; `tests/test_panel_issue_155.py` sur #156 | Vérification synthétique, non lecteur d'écran réel | #155 UI (#156) |
| **C2** | Aucun scan lourd à l'ouverture des vues ; scan explicite global, lecture seule | `qualification_155_cross.cjs` C11 ; tests ciblés #156 | Exhaustivité fournisseur non prouvable dans navigateur ; pas de données réelles | #155 UI + C11 historique |
| **C3** | Sélection clavier conserve la clé physique et révèle la bonne fiche/focus | `qualification_155_cross.cjs` C3, `acceptance.cjs` existant | Focus visuel synthétique, non VoiceOver/TalkBack | #155 UI (#156) |
| **C4** | Aucun accès visuel à l'affirmation « données inventées/non inventées » ; provenance conservée | C4 sur sept vues + tests statiques #156 | Traductions natives hors navigateur couvertes par test ciblé #156 | #155 UI (#156) |
| **C5** | Ligne physique : état terminé/à vérifier/à traiter et pictogramme distinct du fluide ; absence de faux avertissement | `qualification_155_cross.cjs` C5-C6 ; contrôle de boutons Energy existant dans `acceptance.cjs` | Tous les boutons métiers ne sont pas simulés ; désactivation explicative à étendre | #155 UI (#156) |
| **C6** | Déposé avec dernier index historique **brut** distinct de l'index courant : ne pas qualifier automatiquement et ne pas exiger d'index courant | `qualification_155_cross.cjs` C5-C6, deux générations EF | Qualité/continuité physique dépend de #37 ; pas de preuve source réelle | #155 UI + #37 |
| **C7** | Absence de lien/bouton d'ancienne révision dans les **sept vues** | `qualification_155_cross.cjs` C7 | Les routes natives externes ne sont pas ouvertes ; absence de régression backend couverte ailleurs | #155 UI (#156) |
| **C8** | Contexte et jeton de fluide visibles, styles fluides et identités séparées | `qualification_155_cross.cjs` C8 ; `acceptance.cjs` et sonde a11y existantes | Comparaison chromatique exhaustive par fluide et lecteur d'écran réel restent à faire | #155 UI (#156) |
| **C9** | Bornes compte/compteur distinctes, indication **partielle**, inconnu=vide, date manuelle conservée, extension à aujourd'hui, aucune lecture déclenchée | `qualification_155_cross.cjs` C9, vérification Recorder par `acceptance.cjs` | Rechargement complet et concurrence réseau doivent être complétés ; pas d'import | #155 UI + #36 |
| **C10** | Origine initiale indéterminée ; confirmation de lissage bloquée sans motif ; texte d'aide | `qualification_155_cross.cjs` C10 | Persistance de décision approuvée testée dans les tests backend #36, non écrite par navigateur | #155 UI + #36 |
| **C11** | Échec → non-complet, saisie tarifaire possible, réessai explicite, cache, absence de relance par navigation, annulation et absence de mutation | `qualification_155_cross.cjs` C11 ; `tests/test_panel_issue_155.py` C2 | La reprise partielle sûre, fenêtres vérifiées et catégories d'erreur nécessitent contrat backend C11 ; un cache n'est pas une preuve d'exhaustivité | C11 historique + #155 UI |

## Exécution / Execution

```bash
npm ci --prefix scripts/browser-ci --ignore-scripts --no-audit --fund=false
node scripts/browser-ci/acceptance.cjs
```

L'exécution appelle `qualification_155_cross.cjs` **en plus** des parcours existants : 2 langues × 2 tailles × 2 thèmes × 7 vues = **56 observations de navigation conservées**. Les assertions métier supplémentaires sont indépendantes et produisent des résultats `PASS` / `FAIL` par combinaison dans la sortie standard. Une assertion échouée entraîne un code de sortie non nul : **aucun test attendu échoué n'est converti en réussite**. Le workflow existant `browser-acceptance.yml` lance le script principal à chaque PR modifiant `scripts/browser-ci/` ; aucun workflow n'est modifié ici.

The existing workflow executes the same primary script automatically on PRs modifying browser tests. Its original 56 view observations remain intact; the new cross-module checks emit per-matrix PASS/FAIL results and fail the run on missing behavior. Existing Playwright a11y evidence is a separate 56-screen **probe**, not a WCAG certification.

## Verdict et portes de qualification / Gates

- **Développé / Developed:** tests ajoutés, qualité à établir par la CI exacte.
- **Testé / Tested:** uniquement après contrôle d'une exécution **sur le SHA exact** de la PR de qualification. La CI de #156 sur un autre SHA n'est pas transférable.
- **Recetté / Live accepted:** **non** — aucune installation réelle.
- **Fusionné / Merged:** **non**.
- **Publié / Released:** **non**.
- **Installé / Installed:** **non**.

**Blocages à attribuer / Owners:** UI C5–C10 à #156 ; mutualisation, reprise partielle et diagnostics C11 au chantier historique ; preuve d'identité inter-générations à #37 ; validation Recorder à #36 ; admission et absence d'écriture Énergie sans accord à #88. Un échec navigateur prouve l'écart du scénario synthétique, pas automatiquement sa cause ; conserver logs expurgés et SHA précis.

**Protection / Safety:** fixtures `SYNTH-*` et identifiants fictifs de test uniquement. Aucun jeton, compte, adresse réelle, historique réel, accès portail ou service distant.


## Extension indépendante C11 — découverte WebSocket / Independent C11 WebSocket probe

**Source backend examinée / Backend reference inspected:** `custom_components/trybatec/panel_history_jobs.py` et `panel_history_coverage.py` de la convergence #164, SHA observé `59ca822cbe8590151d32fc1db9061d4a79d19870`. Ce SHA n'est **pas** un SHA qualifié par la présente modification tant que sa CI n'est pas vérifiée.

**Nouvelle preuve testée / New independent probe:** `scripts/browser-ci/qualification_155_c11_contract.cjs`, exécuté depuis le lanceur `acceptance.cjs`. 7 états × 8 configurations FR/EN × desktop/mobile × clair/sombre = **56 scénarios de statut**, auxquels s'ajoutent les assertions de source et raccordement. Contrôle en navigateur de la commande réelle **`trybatec/panel_history_discovery_status`**, avec backend émulé d'après **son schéma vérifié** (aucun Home Assistant réel) ; lecture dans les vues Compteurs, Historique et Tarifs. Les résultats `FAIL` provoquent une CI rouge, jamais un succès attendu.

| État C11 / State | Assertion exigée / Mandatory evidence |
|---|---|
| Non lancé / Not started | Consultation administrative explicite, état indéterminé, aucun scan fournisseur implicite |
| En cours / Running | Périodes vérifiées, compteur de requêtes, statut visible sur les trois vues, aucune publication partielle comme complète |
| Incomplet / Incomplete | Job techniquement `complete` mais couverture `bounded_period_only` de **92 jours** ; jamais interprétée comme `account_full` |
| Complet / Complete | Couverture `account_full` prouvée par le backend, cache réutilisé et bornes par identité physique |
| Erreur / Failed | Catégorie expurgée `network`, absence de message fournisseur privé, reprise depuis zéro expliquée, tarifs modifiables |
| Interrompu / Interrupted | Résultat non complet, nouveau scan uniquement après geste explicite, aucun ancien checkpoint prétendu sûr |
| Cache invalidé / Invalidated | `identity_changed`, ancien résultat non attribué à une nouvelle identité, explication de l'invalidation |
| Reprise / Explicit restart | Un seul `panel_history_job_start` après action utilisateur, périmètre du compte exact, aucun write Recorder/Énergie |

**Contrôle complémentaire C5/C8/C9 / Supplemental guardrails:** `qualification_155_cross.cjs` examine les raisons textuelles des contrôles désactivés, l'interdiction d'import Recorder sans plan/sauvegarde, le blocage de la bascule Énergie, les pictogrammes par fluide, le contraste mesuré (seuil 4,5:1), le focus clavier, les dates personnalisées lors du changement de compteur et d'onglet, et la conservation après actualisation du snapshot, sans requête fournisseur implicite.

**Frontière #36/#37/#88 / Module limits:** une absence d'appel WebSocket d'écriture dans le navigateur n'est pas la preuve de l'absence d'un writer Recorder tardif ou concurrent, de la continuité physique de toutes les générations ni de l'admissibilité L6 transactionnelle. Ces preuves indépendantes restent dues aux conversations propriétaires ; les tests frontend doivent refuser toute activation sans leurs attestations vérifiées. Les tests ciblés backend de #162 sont des preuves développeur distinctes, pas une qualification du raccordement UI.

**Signal d'intégration vérifiable / Detectable interface gap:** à l'audit initial de #164, `panel_history_discovery_status` est enregistré côté serveur, mais `trybatec-panel.js` ne contient aucune consommation de ce canal. Les nouveaux tests doivent donc **échouer** sur ce SHA jusqu'au raccordement fonctionnel effectif. Le vert historique de #166 (80/80 sur le parent #156) ne couvre pas C11.

**Catégories de preuve / Evidence classes:** comportement Playwright synthétique ; contrôle statique du contrat source ; intégration backend testée séparément par les tests #162 ; fonctions non encore exercées (délais, identité réseau, réécriture concurrente Recorder, sauvegarde/rollback Énergie, VoiceOver/TalkBack réels) ; recette réelle HA **non attestée**. Les workflows PR et CI qualifient uniquement le SHA exact qu'ils déclarent avoir réellement exécuté.

**EN — Scope notes:** The new status probe consumes a synthetic, contract-shaped read-only WebSocket response and observes the *actual* candidate panel across all relevant views. It must detect absence of frontend subscription, bad incomplete/full mappings, unsafe retry, dropped physical identity, cache invalidation, non-redacted errors and tariff editing blocked by a failed scan. Browser success never certifies real supplier completeness, native Recorder concurrency fencing, L6/L7 admission or production HA accessibility.


## Réconciliation CI intermédiaire #167 / Intermediate SHA-specific CI evidence

- **Source fonctionnelle de la fusion de test :** #164 `d3d052f60adc34b551fceffce462b9a7a082a339` ; **head des tests :** `fc00588387d71cc66fd9814b71af540163631ff4`; **checkout effectif GitHub :** `6b05f7401b2177e4b822ec744f1886f8d2a44cff` ([exécution navigateur](https://github.com/christophejaubert/ha-trybatec/actions/runs/43427934945)).
- **C11 indépendant : 58 PASS / 0 FAIL** : 7 statuts × 8 configurations, plus vérification des signatures de contrat backend et consommation du statut frontend. L'incomplétude à 92 jours reste distincte de la couverture du compte entier.
- **Croisement C1–C11 : 104 PASS / 8 FAIL** sur 112 assertions. Échec unique par configuration, à la localisation de l'explication d'un `fieldset` Énergie désactivé : l'explication est dans la section parente, et non à l'intérieur du `fieldset`. Le harnais corrige cette localisation **sans assouplir le critère**. Il doit être réexécuté sur le SHA qui contient ce correctif.
- **Distinction historique :** l'absence du raccordement C11 au SHA de convergence `59ca822c...` a été corrigée ultérieurement dans #164 ; aucune conclusion négative sur l'absence de raccordement ne doit être reportée au SHA `d3d052f...`.
- **État de qualification :** les conclusions ci-dessus sont uniquement celles du checkout `6b05f740...`. Les nouveaux commits de tests et le dernier HEAD fonctionnel requièrent leurs propres exécutions et vérifications des SHA.

**EN:** On actual PR-merge checkout `6b05f740...`, the independent C11 UI/backend-contract probe passed 58/58; the wider cross-test set passed 104/112 with eight identical failures from a test probe looking *inside* a disabled fieldset rather than its containing section. The probe is corrected without weakening the disabled-reason requirement. These results do not transfer to later SHAs or to live HA; Recorder concurrency, physical lineage and Energy admission remain separate functional evidence gates.

## Rebase de #167 sur convergence récente / Reconciled test branch

**FR :** Les contrôles C11 à 7 états × 8 configurations, l'actualisation du statut uniquement en lecture et l'éviction du cache invalidé sont maintenant réunis dans `qualification_155_c11_contract.cjs`. Les deux anciens contrôles internes C11 qui utilisaient l'API obsolète `_discoveryStates` ne sont pas réintroduits tels quels : leurs **comportements vérifiés restent tous couverts** par le harnais WebSocket indépendant. La version de `qualification_155_cross.cjs` de #164 est conservée pour éviter d'écraser ses 12 scénarios C1–C11 actuels. Les sélecteurs Tarifs `data-tariff-years-retry` et Compteurs `data-historical-scan` sont distincts et le contrôle avant clic interdit tout démarrage fournisseur implicite. Le compte simulé possède `user.is_admin=true` pour tester la vraie barrière frontend ; l'exigence d'administration backend reste entière. Le backend réel ne s'exécute pas dans le navigateur fictif.

**EN:** The dedicated seven-state/eight-matrix probe supersedes obsolete direct `_discoveryStates` internals with stronger actual WebSocket/DOM observations; the current integration's 12 cross-module tests are retained. Explicit user scan start remains distinct from passive administrator-only status. This is synthetic verification only.

## Périmètre séparé #166 / Distinct #156-only scope

**FR — Réconciliation :** la branche #166 est issue du HEAD de la PR fonctionnelle #156, indépendamment de la convergence #164. Les tests C11 contractuels conservent leurs assertions **bloquantes** : puisque le backend C11 de #162 n'est pas intégré dans cette seule branche #156, ils peuvent échouer légitimement. Une réussite éventuelle des seules vues C1–C10 **n'autorise pas** à déclarer C11 couvert. Ne pas attribuer les anciens 80/80 au nouveau SHA. La composition complète reste qualifiée distinctement dans #167.

**EN:** #166 is retargeted to the current #156 application head. The full independent C11 contract is intentionally **not skipped or xfailed** even though #162's backend does not belong to #156. This branch must not be treated as a C11-ready integrated candidate; #167 owns the complete composition qualification.
