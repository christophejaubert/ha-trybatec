# 🤖 #42 — Options natives sans JSON / Native tariff options without mandatory JSON

## FR — Réalisation et dépendances

**Base de développement :** branche `feat/81-greenfield-safe` de #120 au SHA `8eb4f10c694da34afda4333adff0087c52f17d90`.  
**Dépendances :** PR #118 pour l'éditeur principal et la validation commune des montants, PR #120 pour les nouveaux comptes sans migration, PR #132 (#35) pour les parcours d'installation/accès. La PR #132 modifie `config_flow.py`, `strings.json` et les traductions : **réconcilier ces changements ultérieurement, ne pas les écraser**.

**Validation indépendante :** pour exécuter ce lot sur la branche #120 sans le code encore non fusionné de #118, les fichiers `panel_tariffs.py` et `tariff_validation.py` sont suivis sous une **copie binaire identique à #118**. Leur intégration doit conserver une seule version lors de la réconciliation ; aucune duplication fonctionnelle n'est prévue. Les deux copies garantissent le rejet de la précision excessive et la préservation exacte du JSON historique lorsque seule une dérogation est modifiée.

### Contrat COMPAT-01 / TAR-01

- Le menu natif « Options Trybatec » conserve ses sept entrées préexistantes, dans le même ordre, et ajoute « Tarifs annuels (éditeur graphique) » et « Avancé : anciens tarifs JSON (compatibilité) ».
- Les **réglages habituels ne demandent plus de JSON** : la valeur existante de `annual_tariffs` reste inchangée à l'enregistrement des autres options.
- Nouveau parcours Home Assistant **graphique autonome**, même si le panneau custom n'est pas disponible : sélection de l'exercice 2000–2100, EF/ECS/CET, tarif commun ou compteur identifié, préremplissage, statut, enregistrement/retrait/annulation, confirmation explicite avant écriture. L'accès à un ancien compteur exige un inventaire local reconnu ; pas d'identifiant arbitraire fourni par l'utilisateur.
- Le champ JSON historique n'est **ni supprimé ni obligatoire** : il est déplacé vers une rubrique « Avancé » clairement réservée à la compatibilité pour préserver COMPAT-01.
- Les écritures utilisent l'**unique commande métier existante** `change_tariff`, avec empreinte d'options et validation ; aucun second magasin, migration, import Recorder/Énergie ou redémarrage.

### Vérifications à exécuter

1. Parcours Home Assistant natif complet en FR/EN et options persistées : trois fluides, exercices sans relevés/futurs, création/modification/retrait, tarif commun et surcharge spécifique.
2. Tarifs antérieurs en nombres nus et objets avec métadonnées inchangées, réglages sans JSON inchangés, annulation et confirmation refusée sans écriture.
3. Vérification du contrôle d'administration côté serveur et des permissions natives HA, notamment test avec compte non administrateur sur instance de recette.
4. Recette réelle, bureau/mobile, clavier, redémarrage, options et panneau en parallèle, compatibilité de #35/#120/#132 ; aucun chemin préexistant supprimé.

**Risque de coordination :** #120 peut modifier les mêmes fichiers et #132 possède un correctif d'authentification dans `config_flow.py`. Ce lot est une PR **empilée et en brouillon**, distincte des deux, sans fusion automatique. Après leur fusion autorisée, reporter ce lot sur le SHA final et requalifier CI et parcours HA.

## EN — Native visual fallback and dependency contract

A separate stacked draft based on #120, not a direct edit of its branch. All seven original native options menu routes remain available; ordinary settings no longer require or overwrite `annual_tariffs` JSON. A native graphical year/fluid/meter editor handles shared and per-meter rates, status, prefill, save, remove, discard and a separate explicit confirmation. The old JSON field remains reachable under an **opt-in advanced compatibility route**, satisfying the no-mandatory-JSON TAR-01 goal while preserving COMPAT-01 legacy access.

The existing `change_tariff` backend is reused, with exact-snapshot concurrency protection. No second rate subsystem, data migration, production Home Assistant access, Recorder/Energy write, release or merge. #132 and #120 both own overlapping runtime/translation files; coordinate and reconcile before any separately authorized merge. CI is synthetic and never substitutes for real FR/EN mobile/desktop, non-admin and restart acceptance.

### Complément de coordination / Additional integration note

**FR :** les commits temporaires reprenant les deux fichiers backend sont strictement identiques aux blobs #118 ; ne pas fusionner deux implémentations divergentes. **EN:** The two backend copies use identical Git blobs to PR #118; reconcile them as one implementation after the separately approved merges.
