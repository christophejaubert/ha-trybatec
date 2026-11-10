# 0.3.1b1 — Périmètre de la première préversion et registre de reprise

**Décisions utilisateur :** 10 novembre 2026. **Statut :** développement candidat sur branche, pas autorisation de fusion ni de publication.

## Relation entre les versions et les PR

- Base publiée et immuable : `0.3.0b1` (`main`, SHA de départ `24712f11173ffdd80526ad6f6ce70496eb0d2d6c`).
- Nouvelle préversion proposée : `0.3.1b1` ; le document A01–A31 utilise historiquement `0.3.1b0`, mais **ne décide pas de la version finale du code**.
- [PR #72](https://github.com/christophejaubert/ha-trybatec/pull/72) : source détaillée des arbitrages A01–A31, copiée sans altération dans `docs/specifications/trybatec-cleanup-reset-purge-A01-A31.md`.
- [PR #71](https://github.com/christophejaubert/ha-trybatec/pull/71) : base des tokens visuels, réutilisée et corrigée ici ; les **anciens PNG de cette PR ne sont pas le nouveau logo approuvé**.
- [Issue #70](https://github.com/christophejaubert/ha-trybatec/issues/70) : palette/accessibilité ; [#42](https://github.com/christophejaubert/ha-trybatec/issues/42) : tarifs ; [#45](https://github.com/christophejaubert/ha-trybatec/issues/45) : ancienne préversion et non-régression.

## D1 — Préversion progressive : périmètre éligible en 0.3.1b1

**Inclure uniquement des fonctionnalités cohérentes et complètes** :
1. Sélecteur des exercices par compte/logement pris en charge, plage du premier relevé daté −1 au dernier +1, incluant les compteurs déposés ; toutes les années où des tarifs communs ou de compteur existent sont ajoutées *individuellement*, sans compléter artificiellement les trous.
2. Si aucun relevé daté : plage de secours [année civile courante −1, +1], clairement annoncée, plus les années tarifées existantes. Année courante sélectionnée par défaut si proposée ; sinon exercice admissible le plus récent. Pas de calcul de coûts fictifs ni de reprise d'un tarif d'un autre exercice.
3. Version présente dans l'en-tête du panneau sur toutes les pages, issue du manifeste réellement installé (valeur manquante = inconnue/bêta, jamais inventée), attention aux caches après mise à jour.
4. Fond et sélection des compteurs visibles, thème Home Assistant clair/sombre, pictogrammes de fluide distincts et palette officielle ; tests de contraste et de non-régression.
5. Logo **validé** : emblème sans texte, trois parties en rotation globalement circulaire ; goutte froide, goutte chaude à trois traits de chaleur, flamme de chauffage ; séparations blanches ; **aucun cercle vert extérieur**, seuls des accents verts internes. Utiliser les ressources réellement validées et tester sur fond clair/sombre à 24/32/64/256 px.

**Exclure de cette première préversion**, jusqu'à implémentation complète et réussite des tests T01–T40 : les boutons et API de désinstallation, réinitialisation et purge A01–A31. Il est interdit d'exposer au public une commande destructrice partiellement sûre sous prétexte de bêta. L'intégration préserve les options existantes. L'absence de ces fonctions doit être explicite dans les notes de version ; leur implémentation peut se poursuivre sur une autre branche après la validation de cette première tranche.

## D2 à D4 — Contraintes impératives du futur assistant d'administration

- **D2 / A16 :** dans les trois modes de l'assistant, sauvegarde toujours recherchée et proposée mais jamais automatiquement imposée, même en purge, après information et confirmation renforcée. Les **migrations distinctes touchant des historiques Recorder ou Énergie** requièrent un point de restauration technique fiable avant intervention ; elles ne doivent pas devenir une obligation de sauvegarde globale pour la purge A16. Pas de restauration globale automatique.
- **D3 / A07 et A24 :** séparer les journaux techniques réinitialisables et le **rapport d'intervention** non secret, portant les opérations demandées, réellement effectuées, refusées et non vérifiables. Annoncer explicitement toute trace persistante ; prévoir un accès au rapport après disparition éventuelle du panneau, sans persistance cachée.
- **D4 / A31 :** « volume indéterminé » est admissible avec motif, avertissement et confirmation si l'appartenance exclusive est *certainement* établie. Une propriété incertaine, partagée ou externe interdit la suppression, quel que soit le volume.
- **Invariant fournisseur :** ne jamais envoyer de commandes d'écriture/suppression au portail Trybatec ; **toutes les opérations destructrices concernent uniquement le stockage local de Home Assistant**.

## Sujets techniques encore ouverts, à ne pas masquer

Les **14 questions** de la section 10 du référentiel A01–A31 demeurent des travaux d'ingénierie à instruire pour les versions qui exposeront le nettoyage destructeur. Notamment la conservation sélective d'un `.storage` mixte, le statut des états Recorder non statistiques lors du reset, la preuve de propriété multi-compte, la reprise sûre, l'accès au rapport après retrait de configuration et les limites des API HA/Marketplace.

Une branche qui fait passer quelques tests de structure ne valide **pas** les 40 scénarios ni ne permet d'annoncer le nettoyage complet.

## Conditions de mise à disposition / fusion

- CI du SHA candidat **verte** sur tous les contrôles obligatoires (Python pris en charge, hassfest, HACS, qualité, sécurité, navigateur synthétique et tests ajoutés).
- Contrôles fonctionnels et visuels correspondant **au périmètre réellement livré** exécutés et explicitement documentés ; pas d'écriture sur une HA de production lors de la validation.
- Vérification que le manifeste est `0.3.1b1` et qu'aucun tag/release de même version n'existe avant éventuelle publication.
- Aucun changement d'identifiants techniques, Recorder, Énergie, données sources, paramètres existants ou credentials.
- Fusion dans `main` **et** publication de release soumises chacune à une autorisation explicite distincte ; aucune case GitHub/CI ne vaut accord.
- Aucune information propre à une installation particulière dans les fichiers GitHub ou les données de test.
