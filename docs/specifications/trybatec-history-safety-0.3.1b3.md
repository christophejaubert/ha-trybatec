# Trybatec 0.3.1b3 — limites et relance des lectures historiques

## Règles de sécurité effectivement appliquées

- Toute analyse historique déclenchée doit rester dans le compte et la période demandés.
- Une opération suivie est interrompue après 1 800 secondes, ou avant la
  513e tentative HTTP. Les appels de réauthentification et les tentatives
  transitoires sont comptabilisés par le client réseau.
- Une protection complémentaire arrête le découpage adaptatif après
  512 sous-périodes, y compris avec un adaptateur de test qui ne compte pas
  les tentatives réseau.
- Les réponses individuelles sont limitées à 16 Mio, l'accumulation historique
  à 64 Mio de données reçues ; la granularité des résultats reste bornée.
- Le dépassement d'une limite, la coupure du réseau, l'annulation et le JSON
  invalide ne produisent **jamais** un aperçu partiellement validé.
- Un historique invalide ne remplace pas le cache d'un aperçu complet déjà validé.

## Profils candidats non actifs

| Profil | Durée proposée | Tentatives HTTP proposées | Statut |
| --- | ---: | ---: | --- |
| Standard | 120 s | 24 | Non activé |
| Exhaustif | 600 s | 80 | Non activé |

La temporisation proposée de 500 ms par requête historique reste candidate ;
la temporisation courante est exposée à partir de la constante effective.

Un scénario de charge synthétique de sept compteurs sur plusieurs années
nécessite plus de 80 requêtes. Un plafond strict à 80 empêcherait donc la
complétude de ce scénario. Les valeurs candidates ne peuvent pas être
activées sans mesure représentative avec le fournisseur.

Les plafonds de secours ne démontrent pas qu'une analyse de toute durée et
tout volume puisse réussir : une analyse trop volumineuse s'arrête
explicitement. Cela protège Home Assistant, mais nécessite éventuellement
une demande sur une plage plus courte.

## Relance sûre après interruption

Le fournisseur ne fournit pas, à ce stade, de mécanisme vérifié de snapshot
historique immuable permettant de garantir que deux lectures espacées
observent exactement la même version de ses données. En conséquence :

1. Une annulation ou un échec ne publie ni n'enregistre de résultat partiel.
2. Le nouvel ordre d'analyse recommence **au début** de la période demandée.
3. Aucun contenu inachevé d'une exécution précédente n'est réutilisé.
4. Les choix de lissage et imports Recorder conservent leur validation
   indépendante et leur procédure explicite de confirmation.

Cette politique constitue une **relance intégrale sûre**, et non une
reprise incrémentale à partir d'un checkpoint. Une reprise incrémentale
exigerait une garantie fournisseur sur la version des données, ou une
revalidation complète de toutes les tranches reprises.

## Tests et limites des preuves

Tests synthétiques : historiques de sept compteurs sur plusieurs années
avec plus de 80 requêtes, plafond de secours atteint sans résultat partiel,
annulation puis relance intégrale, limites de temps et de tentatives,
absence de secrets dans les diagnostics, isolation des comptes et contrôles
Recorder et persistance.

Les tests CI synthétiques ne sont pas une mesure du débit réel du portail,
ni une recette utilisateur sur une instance Home Assistant de production.
Aucune écriture sur le fournisseur, Recorder ou Énergie n'est autorisée
par les lectures décrites ici.
