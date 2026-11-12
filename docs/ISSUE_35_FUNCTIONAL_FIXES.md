# Issue #35 — Correctifs fonctionnels / Functional setup & access fixes

**Cible / Target:** candidate `0.3.4b1` — no approved merge, release or installation.  
**Source:** [issue #35](https://github.com/christophejaubert/ha-trybatec/issues/35), [merged tests #119](https://github.com/christophejaubert/ha-trybatec/pull/119).  
**Concurrent work / Travaux concurrents:** [draft #120](https://github.com/christophejaubert/ha-trybatec/pull/120), issue #81, stable identities for **new** accounts only.

## FR — Contrats fonctionnels

### A. Identification du logement et gestion des erreurs

| Événement | Contrat de configuration | Contrat d'exécution |
|---|---|---|
| Authentification HTTP 401 | Renouveler le Bearer une fois, puis `invalid_auth` si le refus persiste | `ConfigEntryAuthFailed` et notification de réauthentification |
| Autorisation HTTP 403 sur `/housings` ou `/indexes` | `access_denied`, **aucun repli URL** ; aucune création d'entrée | `UpdateFailed` et notification de droits insuffisants, sans erreur de mot de passe présumée |
| Réponse `/housings` liste de longueur différente de 1 | Aucun choix arbitraire ; repli par URL HTTPS complète **avec vérification `/indexes`** | Sans objet |
| Panne 429/5xx/timeout/réseau | `cannot_connect`, aucune création d'entrée ni repli URL | Réessais bornés, notification après trois erreurs de connexion consécutives |
| Structure de réponse/JSON invalide | `invalid_response`, aucune création d'entrée ni repli URL | `UpdateFailed`, sans publication de mesures nulles |
| Réauthentification réussie | Identifiants vérifiés avant remplacement ; même compte, même `entry_id`, `unique_id` et options | Reprise par l'entrée existante |

La règle d'une seule ligne `housings` correspond au contrat actuellement qualifié, **pas** à une garantie de prise en charge des comptes multi-copropriétés. Cette limitation reste en vigueur.

### B. Cycle de vie d'une notification persistante

- Identifiant stable, dérivé exclusivement de l'identifiant d'entrée HA ; pas d'UUID de fournisseur dans le titre/message.
- Première erreur d'authentification ou 403 confirmé : notification immédiate.
- Erreur réseau/données : une notification après trois échecs de rafraîchissement consécutifs.
- Même type d'incident : pas de duplication. Un incident d'authentification/de droits n'est pas abaissé à « réseau » sans reprise démontrée.
- Nouveau coordinateur : au **premier rafraîchissement réussi**, supprimer aussi une notification héritée du précédent coordinateur ; éviter les suppressions inutiles aux rafraîchissements suivants.
- Texte statique FR/EN suivant la langue configurée de l'instance HA ; anglais en repli. Aucune interpolation de mot de passe, jeton, UUID, relevé ou corps HTTP.

### C. Qualification et preuves

La PR transforme les deux tests `xfail(strict=True)` de #119 en tests exécutables normalement. Le scénario « repli après 403 » est **requalifié** : le comportement sûr attendu est l'absence de repli et une erreur `access_denied`, non la possibilité de forcer une URL.

Tests supplémentaires : matrice des erreurs du flux HA, validation obligatoire de l'URL ambiguë par `/indexes`, préservation de l'entrée/options en cas de 403, classification 401/403 avec renouvellement borné du Bearer, absence de fuites dans messages/logs et absence de dégradation d'un incident d'autorisation vers la connectivité.

**Limites :** CI synthétique et contrôle structurel ne prouvent pas une recette métier. Aucune connexion effective au portail utilisateur, installation sur HA, migration historique, purge d'identifiants, écriture Recorder ou modification de préférences Énergie.

## EN — Acceptance and delivery

HTTP **401** indicates authentication failure after at most one Bearer refresh; HTTP **403** indicates authenticated resource permission denial and **must never activate a manual-URL bypass**. Only ambiguous single-housing discovery can open a strictly validated HTTPS URL fallback, which still verifies the requested `dealId` through `/indexes`. Transport failures and malformed responses do not create entries or turn into fallback.

One notification per HA configuration entry is created or updated using a stable ID, kept while the incident remains active, and dismissed only after a successful meter refresh — even when a new coordinator inherits an older notification. Messages use static English/French content and never interpolate vendor-private data. Reauthentication preserves the same account, HA entry and historical options.

**Review constraints:** PR #120 currently modifies `config_flow.py`, `coordinator.py` and `__init__.py`. #35 must not modify #120's branch, merge on a stale shared-file diff, or alter stable IDs. Keep #35 a draft; integrate/reconcile #120 first **only after separately authorized merge**, then rebase/replay #35 selectively, inspect the final diff and rerun all mandatory CI. If integration order changes, reconcile both heads and dependencies first.

## Conditions de sortie / Exit gates

- [ ] Full mandatory CI successful on the final corrective SHA
- [ ] Two previous strict xfails converted and passing, no accidental skip
- [ ] HA synthetic initialization, config flow, reauth, notifications, diagnostics and stable-identity regressions
- [ ] No secrets, real account information, or device identifiers in public artifacts/logs
- [ ] #120 shared-file conflicts resolved **without** migration or identity cleanup
- [ ] Separate real-world acceptance with documented environment and explicit user approval
- [ ] Separate merge decision, separate release decision, separate HA installation decision

**Reconciliation:** record branch SHA, PR, CI run, job conclusions and remaining risks in the PR itself. Issue #35 stays open pending business acceptance.
