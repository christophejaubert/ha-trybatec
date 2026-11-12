# Vérification locale L3 / L3 local validation

## Français

**État : prêt pour revue locale, non publié.** Référence initiale du développement : `main` à `6ebbd7245cbb5bff90c3fb98084a9a78fc47b4b6`. Réconciliation de fin de travail : `main` à `a21906bada0b01a9a069afc2a1b84235b2590cc7`, PR #82 en brouillon à `5fc1d126c7a31a2da1d9769948d05a1fbb3070cb`. L'évolution de `main` porte sur `history_plan_b15.py`, `history_reconstruction.py`, `history_review.py`, `tests/test_l2_history_safety.py` ; aucun chevauchement direct avec les quatre fichiers L3. Ce constat ne remplace pas la vérification future au moment de publier.

- **Exécution locale** : Python 3.13.5, `pytest` et `pytest-cov` disponibles ; 44 tests synthétiques réussis.
- **Couverture de branches locale** : 82 % sur les deux modules L3 ; module de diagnostic 90 %, adaptateur HA 71 %.
- **Barrière de lecture seule** : analyse syntaxique de l'absence d'appels de mutation, tests sur fichiers JSON présents / corrompus / anciens / trop volumineux, contrôle que leurs octets ne changent pas. Pas d'appel au fournisseur ni à une instance HA de production.
- **Intégration synthétique** : les doubles locaux de `energy_switch.py` et `energy_bulk_plan.py` servent à éviter une dépendance à HA et au dépôt distant pendant l'exécution hors ligne. Cela **ne valide pas l'exécution complète du moteur réel #92**. Dans GitHub, les imports cibleront les vrais modules, déjà présents dans `main`, et la CI devra exécuter les nouveaux tests sur l'arbre réel.
- **Non vérifiés** : Python 3.14, Ruff, totalité de la CI GitHub, HA runtime, intégration native, restauration, recette métier, performance en production et exhaustive continuité historique.

Pour relancer sur une copie du dépôt après insertion des fichiers :

```shell
python -m pytest -q tests/test_energy_bulk_evidence.py
python -m compileall -q custom_components/trybatec
```

Ne pas déployer ce lot dans Home Assistant à ce stade : aucun point d'entrée ne l'appelle. Aucun bouton Énergie, chemin d'écriture ou mécanisme de migration n'est créé.

## English

**Local review package only; not published.** Initial baseline `6ebbd7245cbb5bff90c3fb98084a9a78fc47b4b6`; latest reconciled `main` `a21906bada0b01a9a069afc2a1b84235b2590cc7`. PR #82 remains draft at `5fc1d126c7a31a2da1d9769948d05a1fbb3070cb`. Four changed `main` files do not overlap the new L3 files; publication-time rebasing still needs validation.

Local Python 3.13.5 run: **44 synthetic tests passed**, **82% branch coverage** for new modules (90% pure assessor; 71% native adapter). Synthetic Home Assistant/Recorder mocks and isolated storage JSON fixtures only. The test isolation uses reduced local stand-ins for existing #92 modules and **does not count as an actual #92 integration test**. GitHub CI on the real repository tree, Python 3.14, Ruff, Home Assistant runtime testing and real business acceptance remain **not performed**.

Read-only proof: static forbidden-call guard and real synthetic files checked for byte-for-byte preservation on malformed, incompatible and over-limit storage; no provider, Recorder mutation, or Energy preference write. The module is not registered at startup or in a websocket handler. Re-run tests in the actual repository using the commands above before any publication.
