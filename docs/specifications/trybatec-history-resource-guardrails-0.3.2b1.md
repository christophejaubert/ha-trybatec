# UI-004 / TECH-001–003 — Diagnostics et budgets de lecture historique (0.3.2b1)

Statut : **décisions de produit approuvées ; budgets chiffrés candidats, pas des garanties déjà actives**.
Périmètre : uniquement l'intégration Trybatec. Aucune action fournisseur en écriture, aucune modification Recorder ou Energy par le diagnostic.
Le panneau ne doit jamais présenter un seuil proposé comme une protection effectivement appliquée.

## 1. Deux catégories de traitements

| Catégorie | Période indicative | Budget global candidat | Appels HTTP réels candidats | Comportement |
| --- | --- | --- | --- | --- |
| Standard | Jusqu'à une année | 120 secondes | 24 | Prévisualisation interactive avec état et suivi |
| Exhaustive | Plusieurs années | 600 secondes | 80 | Tâche asynchrone suivie depuis le panneau, relance intégrale après interruption |
| Commun | Toutes les lectures historiques | Pause 500 ms entre appels | 1 analyse par compte | Taille par réponse d'index 16 Mio, inchangée |

Ces budgets candidats restent **inactifs** tant que des mesures de charge représentatives ne les ont pas validés. Le lecteur HTTP fragmenté a été corrigé en 0.3.1b3. Les 500 ms concernent uniquement la cadence de base ;
un HTTP 429 doit respecter Retry-After quand il est utilisable et une temporisation
exponentielle avec jitter lorsque la reprise est appropriée.
Ne pas modifier les cadences du rafraîchissement courant des index.

Le nombre d'appels est comptabilisé au moment du départ de **chaque tentative HTTP réelle**,
incluant authentifications/rafraîchissements d'authentification déclenchés par l'analyse,
réessais et subdivisions. Les appels de synchronisation courante restent hors de ce budget,
mais prioritaires pour la qualité de service. Une requête en cours ne peut pas être
interrompue rétroactivement ; la réservation du budget précède l'appel. Les pauses,
attentes du verrou par compte et durées d'appel doivent être incluses dans la durée
globale, avec horloge monotone et annulation coopérative.

## 2. Protections actuellement en vigueur : inventaire non éditable

Construire l'inventaire depuis les constantes et paramètres **effectifs du backend**, jamais à partir de nombres recopiés dans le JavaScript. La base minimale est désormais **0.3.1b3**, et non 0.3.1b2.

Protections constatées en recette 0.3.1b3 :
- durée globale maximale de chaque analyse historique : **1 800 secondes**, appliquée côté serveur ;
- au plus **512 tentatives HTTP réelles** par opération et garde sur les subdivisions ;
- réponse d'index limitée à **16 Mio**, métadonnées/authentification à **64 Kio** ;
- réception historique cumulée limitée à **64 Mio** ;
- limite de **120 000 points** et **20 000 lignes** par réponse ;
- délais HTTP par opération réseau : index 60 s, authentification 30 s, découverte logement 25 s, appareil 20 s ;
- temporisation entre sous-périodes historiques effectivement appliquée : **200 ms** ;
- retries transitoires, respect de `Retry-After` et backoff avec jitter ;
- sérialisation par compte, suivi d'opérations asynchrones et annulation ciblée ;
- diagnostics en mémoire : **20 opérations maximum** conservées **24 heures**.

Les limites effectives apparaissent sous `technical_limits.effective` ; les budgets candidats sous `technical_limits.proposed`, avec `enforced=false`. Pour les maxima globaux, les clés autorisées sont `max_global_duration_seconds` et `max_global_http_requests`. Les anciennes clés `historical_operation_timeout_seconds=null` et `historical_operation_max_http_requests=null` sont obsolètes.

L'interface doit distinguer les limites **en vigueur** et les budgets **proposés**, sans annoncer des budgets candidats comme actifs et sans exposer de données privées.

## 3. Correction HTTP livrée en 0.3.1b3 — exigences de non-régression

Le lecteur aiohttp ne doit pas interpréter le premier fragment de
`StreamReader.read(n)` comme l'intégralité du corps. Accumuler des fragments
bornés jusqu'à EOF (ou utiliser une primitive équivalente documentée) ;
limiter les octets décompressés effectivement reçus ; ne pas journaliser le
corps, jetons ou identifiants. Distinguer transfert tronqué, code HTTP,
JSON véritablement malformé, fenêtre rejetée, taille et cardinalité trop élevées.
Ne subdiviser que les erreurs dont la subdivision peut résoudre la cause ;
un problème de décodage ne déclenche pas automatiquement un arbre de requêtes.

## 4. Cycle de vie et cohérence

- Opération suivie par un identifiant éphémère opaque, créé après
  validation de la période et du compte.
- Une seule analyse active par compte ; une opération dupliquée rejoint
  l'opération en cours ou reçoit un message clair, sans nouveaux appels
  fournisseurs. Ne jamais bloquer le polling courant.
- Les données historiques restent « incomplètes » tant que toutes les
  sous-périodes ont été vérifiées. Les importations et changements Energy
  exigent une nouvelle prévisualisation complète et leur confirmation distincte.
- À budget expiré, annulation ou échec définitif : arrêter les tentatives
  suivantes, libérer les verrous, restituer un diagnostic et **ne pas**
  publier un cache de prévisualisation faussement exhaustif.
- Après interruption, relancer une analyse **intégrale** : pas de reprise incrémentale à partir de fragments non vérifiés ni de réutilisation d'une empreinte d'importation périmée.
- Ne jamais accumuler sans borne des réponses de 16 Mio : limiter
  explicitement la mémoire cumulée, privilégier des consolidations
  progressives contrôlées ou une persistance temporaire bornée.
- En cas de timeout WebSocket, assurer que la tâche serveur annule ou
  termine réellement son activité. Un timeout côté client n'est pas une
  preuve de terminaison côté serveur.

## 5. Présentation de la progression

- Après 3 secondes, afficher un état visible de traitement ; après
  30 secondes, une information « opération plus longue que prévu »
  non alarmante.
- Une progression n'est un pourcentage que lorsque son dénominateur
  est vérifiable (périodes calendaires validées). Les appels réalisés
  sur le budget d'appels ne constituent pas une progression métier.
- Montrer durée écoulée, requêtes HTTP engagées et budget restant
  (lorsque les budgets sont **effectivement actifs**), périodes
  définitivement validées et échecs, bouton d'annulation opérationnel.
- Si le suivi en arrière-plan, l'annulation ou la reprise ne sont pas
  encore implémentés, afficher explicitement « À développer » ; ne pas
  ajouter de contrôles inertes.
- FR/EN, bureau/mobile, thèmes clair/sombre et clavier. L'onglet
  Diagnostics montre les opérations, l'onglet Réglages leurs limites.

## 6. Diagnostics

Collecter le type d'opération, date/heure, statut, durée totale, nombre
d'appels HTTP effectivement effectués, réessais, subdivisions, volume reçu,
taille maximale observée, catégories de codes HTTP et cause d'arrêt.
Ne conserver en mémoire que les 20 dernières opérations et au maximum
24 heures, sans données source, indices de compteur, identifiants du
compte, en-têtes ou jetons d'authentification ; effacer au redémarrage.
La copie locale d'un rapport expurgé ne doit pas l'envoyer à un service.
Les entrées doivent signaler clairement les mesures indisponibles.

## 7. Validation obligatoire avant activation des budgets candidats

1. Tests de lecture HTTP fragmentée : 2, 3 et plusieurs dizaines de
   fragments ; lenteur, annulation, compression, UTF-8 réparti,
   transfert tronqué, taille supérieure à 16 Mio et vrai JSON invalide.
2. Tests d'erreurs : 429 avec Retry-After, 5xx, 408/413/414/422,
   absence de réseau, erreur d'authentification ; pas de subdivision
   excessive sur JSON invalide.
3. Scénarios « standard » et « exhaustif » avec volumes réalistes,
   nombreux compteurs et remplacements ; mesurer latence p50/p95,
   mémoire maximale, nombre d'appels et impact sur le polling.
4. Tests de fin de budget, d'annulation, de concurrence et de reprise
   (pas de données présentées comme exhaustives à tort).
5. Recette UI navigateur FR/EN, mobile/bureau, clair/sombre, progression
   réelle ; test d'intégration HA et CI verte sur SHA final.
6. Après résultats : décider de conserver, relever ou réduire les
   budgets candidats. Ne jamais les activer silencieusement.

Les titres et messages des contributions GitHub suivent la convention
de préfixe « 🤖 » ; les numéros de version et tags n'en portent pas.
