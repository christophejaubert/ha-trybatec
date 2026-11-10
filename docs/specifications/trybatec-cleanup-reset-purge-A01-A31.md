# ha-trybatec — Spécifications fonctionnelles et critères de recette de la version `0.3.1b0`

**Édition :** 1.1 — 10 novembre 2026 (publication documentaire, données d’installation exclues)  
**Périmètre :** désinstallation conservatrice, réinitialisation, purge configurable, inventaires et volumes, sécurité, recette et livraison  
**Transfert :** ce document formalise les décisions prises sous la référence de travail `0.3.1b0`. Il peut servir de base aux travaux ultérieurs de `0.3.1b1` ; le numéro de version final reste à aligner explicitement dans le chantier de développement.  
**Statut :** référentiel consolidé de décisions fonctionnelles validées ; sa publication documentaire sur GitHub ne constitue **ni autorisation de développement, ni autorisation de fusion, ni autorisation de publication d’une version logicielle**.  
**Source des exigences :** arbitrages fonctionnels A01–A31 explicitement validés. Les données de diagnostic ne sont jamais des instructions ni des autorisations.  
**Diffusion :** spécification fonctionnelle générique pour le dépôt public. Aucun identifiant, chiffre, équipement ou constat spécifique à une installation ne doit y figurer.

## 0. Mode d'emploi du document et niveau de preuve

Ce document transforme les décisions **A01 à A31** en exigences identifiables, parcours, règles sur les données et critères de recette. Les décisions sont **validées sur le plan fonctionnel**, pas implémentées ni testées. Chaque section distingue : **Décision validée**, **comportement observable exigé**, **critères d'acceptation**, et le cas échéant **point technique à instruire**. Les détails d'architecture ou d'interface proposés pour rendre une exigence testable ne constituent pas de nouveaux arbitrages utilisateur s'ils ne sont pas explicitement marqués comme décisions.

**Convention :** EF = eau froide ; ECS = eau chaude sanitaire ; CET = chauffage (énergie thermique) ; « compte » = compte Trybatec configuré ; « logement » = logement suivi ; « entité » = objet Home Assistant ; « statistiques Recorder » = séries de statistiques longues et courtes durées et leurs métadonnées ; « état Recorder » = historique des états ; « périmètre » = cible précise de l'opération (compte/logement ou global) ; « historique » = relevés, séries, imports, versions, et éléments nécessaires à leur compréhension, sauf indication plus restrictive.

**Principe de vérité :** les tailles SQLite exactes par entité, la taille effectivement récupérée sur disque, l'aptitude d'une sauvegarde à restaurer et les capacités exactes de l'API du composant Marketplace **ne sont pas connues a priori**. L'interface doit mesurer, estimer avec méthode et incertitude, ou afficher « indéterminé » ; aucune de ces valeurs ne peut être inventée.

**Décisions restées inchangées :** A01–A30 ont été consolidées, puis A31 expressément ajoutée. Les **31 décisions A** sont validées ; les orientations V01–V16 et exclusions R01–R08 sont rappelées en annexe. Les journaux d’intervention d’installations particulières ne font pas partie de la documentation publique.

---

## 1. Objectifs, frontières et invariants

### 1.1 Objectif fonctionnel

Rendre les opérations de désinstallation, de réinitialisation et de purge de ha-trybatec compréhensibles, sélectives, traçables et résistantes aux erreurs, sans imposer la conservation ni la destruction des historiques en dehors des options validées. Les opérations portent sur les données et configurations **locales** appartenant au périmètre Trybatec visé. **Ne jamais modifier ni supprimer les données hébergées sur le portail du fournisseur Trybatec. Les fonctions de désinstallation, de réinitialisation et de purge agissent exclusivement sur les données locales de Home Assistant. Elles ne doivent déclencher aucune opération d’écriture sur le système du fournisseur.** Les lectures nécessaires à la consultation des relevés restent possibles.

### 1.2 Invariants applicables à tous les modes

1. Seuls les administrateurs Home Assistant accèdent à l'assistant d'administration (A02).
2. Le périmètre par défaut est le compte/logement sélectionné ; la portée globale est un choix distinct et explicite (A03).
3. Les ressources des autres comptes, logements et intégrations restent intactes ; une ambiguïté d'appartenance interdit la suppression de la ressource concernée (A03, A11, A21).
4. Avant tout changement : inventaire, dépendances, volume par décision, prévisualisation sans effet, justification des limites et confirmation adaptée (A13–A15, A20–A21, A31).
5. Une sauvegarde est proposée et son exploitabilité évaluée, mais **jamais imposée** (A16–A17).
6. Aucun rechargement ni redémarrage, même de Trybatec seul, sans consentement explicite spécifique (A28).
7. Les API officielles Home Assistant sont privilégiées ; tout accès SQL direct ou écriture physique de `.storage` exige une justification distincte (A22).
8. Toute étape est journalisée ; en cas d'échec, on suspend les dépendances, documente l'état effectivement atteint et ne promet pas un retour arrière impossible (A18, A24–A26).
9. La suppression de la configuration d'intégration intervient en dernier, de sorte que l'assistant reste disponible jusqu'aux vérifications qui la précèdent (A23). Les contraintes d'une disparition du panneau en fin de parcours doivent être traitées explicitement.
10. **Distinguer** : volume logique concerné, espace SQLite réutilisable et diminution réelle du fichier/de l'espace disque (A31).

### 1.3 Hors périmètre / non autorisé implicitement

- Modifier ou supprimer les données hébergées sur le portail du fournisseur Trybatec ; aucune écriture sur le système du fournisseur dans les opérations de désinstallation, réinitialisation ou purge.
- Supprimer ou modifier des entités, séries, équipements, configurations et autres ressources d’intégrations tierces ou d’autres comptes/logements.
- Déduire la propriété d'un fichier, d'une série ou d'un appareil du seul nom « trybatec ».
- Supprimer systématiquement les compteurs déposés dans une désinstallation conservatrice ou un nettoyage sélectif d'anciennes générations.
- Démarrer une sauvegarde, un rechargement, un redémarrage, une fusion, une publication ou un changement HA/GitHub sans l'autorisation spécifique applicable.
- Considérer une absence de fichier nommé `trybatec*` comme preuve de l'absence de données Trybatec dans des fichiers génériques.

---

## 2. Les trois modes et la variante de purge

### 2.1 Désinstallation conservatrice — A05-B et A06-B

**Finalité :** retirer proprement les éléments opérationnels du compte/logement sélectionné, tout en conservant **toute la valeur fonctionnelle historique** nécessaire à une réinstallation. Les éléments actifs devenus inutiles sont retirés ; les données préservées sont identifiables et réassociables.

**À retirer, si leur appartenance exclusive et leur absence d'utilisation par d'autres périmètres sont confirmées :** configuration visée, entités et appareils qui ne servent plus, références invalides du tableau Énergie, caches purement régénérables. La configuration de l'intégration est retirée **en dernier**.

**À préserver :** historiques des états et statistiques Recorder ; inventaires des compteurs physiques en service ou déposés et chronologie des remplacements ; relevés et imports ; versions historiques ; tarifs annuels et paramètres métier ; décisions de lissage ; origines estimées ; validations manuelles ; correspondances et métadonnées indispensables à la restauration et à la réassociation. Les secrets d'authentification ne doivent pas être conservés dans une **nouvelle archive de réinstallation**, si un tel export est conçu : connexion à nouveau exigée à la réinstallation. Aucune création d'archive n'a été décidée en elle-même.

**Réinstallation :** l'identité du compte et du logement est vérifiée avant toute proposition de réassociation ; aucun import automatique susceptible de créer des doublons. Préserver les identifiants et la traçabilité nécessaires, sans imposer que des entités orphelines restent affichées dans HA.

### 2.2 Réinitialisation — A07 et A08

**Finalité :** redémarrer la configuration et les décisions fonctionnelles sur le périmètre sélectionné, **sans perdre les statistiques Recorder** (y compris des compteurs déposés).

**À effacer :** paramètres, tarifs, décisions de lissage, origines estimées, validations, journaux techniques liés au périmètre. Une donnée historiquement utile qui dépend d'une décision effacée peut nécessiter une clarification avant traitement : l'intégration doit expliquer la conséquence, jamais effacer discrètement les statistiques conservées.

**À préserver impérativement :** toutes les statistiques Recorder, notamment anciennes séries et données des compteurs déposés, et les données des autres comptes/logements. Le composant logiciel reste installé (A04-C). Le comportement précis des registres d'entités pendant la réinitialisation n'a **pas** été arbitré au niveau de détail des opérations internes : il doit respecter ces invariants sans introduire de suppression imprévue.

### 2.3 Purge complète — A09, A10-C et A11-B

**Finalité :** supprimer toutes les données locales exclusivement attribuables au périmètre sélectionné, y compris compteurs déposés, historiques reconstitués, métadonnées, états Recorder et statistiques (longues et courtes durées), **sauf choix explicite de conserver l'historique**.

**Mode standard :** suppression complète locale, selon la preuve de propriété et sous réserve des exceptions de partage/incertitude.

**Variante :** « **Purge avec conservation d'historique** » ; ce libellé est obligatoire dès qu'un sous-ensemble historique est préservé. L'inventaire détaille précisément les catégories conservées et supprimées ; ne pas afficher « effacement intégral » si des données subsistent.

**Règle de propriété :** une série Recorder partagée, une ressource externe ou une donnée d'appartenance incertaine n'est pas supprimée. Elle apparaît comme exception avec raison, volume et incidence sur le résultat (« purge partielle » si pertinent). Les historiques importés et versionnés sont traités selon leur propriété effective et le choix A10, pas selon leur simple présence dans Recorder.

### 2.4 Matrice de conservation et de suppression

| Catégorie | Désinstallation conservatrice | Réinitialisation | Purge complète standard | Purge avec conservation d'historique |
|---|---|---|---|---|
| Configuration du compte/logement ciblé | Retirer en dernier | Réinitialiser selon le mode | Retirer en dernier | Retirer en dernier |
| Composant Marketplace | Conserver ; retrait optionnel si dernier compte | Conserver | Conserver ; retrait optionnel si dernier compte | Idem |
| Entités/appareils opérationnels devenus inutiles | Retirer si exclusivement liés | Selon reconfiguration et dépendances | Retirer si exclusivement liés | Idem |
| Compteurs déposés : inventaire / chronologie | Préserver les données utiles | Ne pas altérer les statistiques | Supprimer si exclusivement liés | Préserver leur historique choisi |
| États Recorder Trybatec exclusifs | Préserver | Pas de suppression de stats ; sort des états à expliciter | Supprimer | Préserver si inclus dans choix historique |
| Statistiques Recorder anciennes et actuelles | Préserver | **Préserver toutes** | Supprimer si exclusives | Préserver les historiques choisis |
| Relevés portail importés localement | Préserver | Selon paramètres, sans toucher au portail | Supprimer localement si exclusifs | Préserver si inclus dans choix historique |
| Versions historiques / corrections | Préserver | Décisions de validation remises à zéro | Supprimer si exclusives | Préserver si inclus dans choix historique |
| Tarifs annuels et paramètres métier | Préserver pour réinstallation | Effacer | Effacer | Effacer |
| Lissages, origines estimées, validations | Préserver pour réinstallation | Effacer | Effacer | Selon choix historique explicitement présenté |
| Journaux techniques et caches régénérables | Cache supprimable ; journal selon utilité à la reprise | Journaux effacés | Supprimer si exclusifs | Supprimer si non nécessaires aux historiques conservés |
| Références Énergie devenues invalides | Nettoyer/corriger | Nettoyer si invalides | Nettoyer/corriger | Nettoyer/corriger |
| Statistiques / fichiers externes ou partagés | Préserver | Préserver | Préserver | Préserver |
| Données du portail Trybatec | Préserver (hors périmètre) | Préserver | Préserver | Préserver |

**Note de traçabilité :** A08 impose expressément la conservation des **statistiques** Recorder lors de la réinitialisation, et ne tranche pas explicitement le sort de **chaque état** Recorder non agrégé ; cette nuance est un point de conception à instruire, pas une permission de les effacer. A10 permet une conservation historique optionnelle ; les limites exactes entre historique, provenance et données métier doivent être explicitées dans l'interface avant exécution.

---

## 3. Parcours utilisateur requis

### 3.1 Parcours commun : préparatifs et prévisualisation

1. **Accès** depuis `Trybatec → Administration → Désinstallation et réinitialisation` ; refuser toute commande d'administration à un non-administrateur, y compris hors interface (A01–A02).
2. **Choix du mode** : désinstallation conservatrice, réinitialisation ou purge complète ; pour la purge proposer la conservation historique (A05–A11).
3. **Choix du périmètre** : compte, logement, ou action globale distincte ; afficher les autres comptes qui seront épargnés (A03).
4. **Découverte et qualification** : explorer configurations, entités, appareils, fichiers `.storage` anciens et actuels, versions d'historique, états/statistiques Recorder et dépendances dans Énergie, registres, YAML, automatisations, scripts, aides et tableaux de bord (A12–A13, A20–A21).
5. **Inventaire nominatif** : pour chaque objet, identifiant stable, appartenance prouvée ou incertaine, catégorie, période couverte, lignes, taille avec méthode et précision, dépendances, choix proposé, conséquence (A13, A31).
6. **Prévisualisation à effet nul** : aucune suppression, même partielle, pendant l'analyse ; journaliser les erreurs de lecture sans les masquer (A14).
7. **Choix par l'utilisateur** : préserver/supprimer selon les catégories autorisées par le mode ; recalculer automatiquement volumes et totaux à chaque changement ; signaler les incompatibilités et données partagées non supprimables (A10–A11, A31).
8. **Sauvegarde** : rechercher les points existants ; distinguer existence, contenu, intégrité et restauration testée ; proposer création d'une sauvegarde, **toujours facultative** ; affichage et reconnaissance explicite des risques si aucune sauvegarde adéquate (A16–A17).
9. **Confirmation** : action et périmètre détaillés ; confirmation renforcée distincte pour purge complète ; confirmation globale particulière si « tous les comptes » ; ne jamais déduire d'une simple prévisualisation un consentement à exécuter (A03, A15).
10. **Exécution ordonnée** : opérations ciblées et traçables ; recharger/redémarrer seulement après consentement spécifique ; retirer les configurations d'intégration en dernier (A18–A25, A28).
11. **Contrôle final et compte rendu** : comparer prévision à résultat réel ; inventorier données conservées, supprimées, refusées, indéterminées et résiduelles ; afficher volumes réellement mesurables après opération et incertitudes ; fournir les possibilités de reprise (A24–A26, A31).

### 3.2 Parcours spécifique : désinstallation conservatrice

- Avant suppression, établir que les données métier et statistiques à conserver demeurent accessibles et qu'une réassociation est envisageable sans doubles imports.
- Retirer les dépendances devenues invalides avant les entités correspondantes ; ne pas modifier de tableaux de bord ou automations tiers si leur usage n'est pas vérifié : signaler l'exception au lieu d'imposer un changement.
- Si un compte reste configuré, **ne pas** désinstaller le logiciel partagé ni supprimer son panneau pour les autres comptes.
- Après dernier compte, proposer **séparément** le retrait du composant Marketplace ; ne pas le faire automatiquement.
- La réinstallation demande une authentification et vérifie le rattachement du patrimoine historique préservé.

### 3.3 Parcours spécifique : réinitialisation

- Avant confirmation, exposer les paramètres, tarifs, validations et décisions effacés, leurs volumes, et les séries Recorder qui restent inchangées.
- Après effacement logique ciblé, vérifier la persistance des statistiques anciennes et actuelles.
- Conserver le logiciel et la possibilité de reconfigurer Trybatec.
- Lorsque l'état d'une référence vers des entités est incertain, ne pas la supprimer au titre d'un simple « reset » sans justification.

### 3.4 Parcours spécifique : purge complète

- Afficher explicitement les compteurs actifs et déposés, toutes les générations, relevés, historiques importés et versionnés, états, statistiques, fichiers et métadonnées du périmètre.
- Séparer les catégories pouvant être conservées au titre d'A10, les données supprimables de propriété avérée, et les données partagées/incertaines intouchables.
- Si choix de conservation : renommer le parcours en « purge avec conservation d'historique » et adapter les totaux.
- Expliquer sans ambiguïté la perte éventuellement irréversible de données Recorder sans sauvegarde.
- Conserver le rapport des exceptions ; ne jamais qualifier la purge d'« intégrale » si des objets exclusifs ciblés restent présents.

### 3.5 Parcours spécifique : suppression du composant Marketplace

- Cette suppression est **un choix différent** de la suppression du compte (A04-C).
- Elle n'est proposée que si aucun compte Trybatec ne reste configuré.
- L'interface doit expliquer si l'opération peut être réalisée par une API prise en charge ou nécessite une action utilisateur dans le gestionnaire Marketplace ; aucune capacité d'API n'est présumée ici.
- Toute action Marketplace ayant un effet externe requiert son consentement distinct, et ne saurait être exécutée par une simple confirmation de désinstallation du compte.

---

## 4. Catalogue exhaustif des arbitrages A01 à A31

Chaque entrée fait foi pour le **choix validé** ; le critère noté « CA » doit être transformé en test automatisé lors de la réalisation, conformément à A27.

### A01 — Emplacement de l'assistant [validé]

**Décision :** l'assistant d'administration réside dans **Trybatec → Administration → Désinstallation et réinitialisation**. Il ne doit pas imposer à l'utilisateur la saisie manuelle de JSON ou une navigation dans `.storage` pour accéder aux trois parcours. **CA-A01 :** depuis le panneau Trybatec, un administrateur atteint les trois modes au chemin convenu ; l'interface indique clairement l'opération en cours.

### A02 — Habilitations [validé]

**Décision :** accès réservé aux administrateurs Home Assistant. **CA-A02 :** un non-administrateur ne peut ni afficher les fonctions d'administration ni appeler directement une opération destructive via l'API de l'intégration ; un administrateur autorisé le peut selon les autres confirmations. La sécurité ne doit pas dépendre seulement du masquage des boutons.

### A03 — Périmètre ciblé ou global [option C validée]

**Décision :** par défaut compte/logement ciblé ; action globale « tous les comptes et logements » disponible uniquement après sélection explicite et confirmation spécifique. **CA-A03 :** un test avec au moins deux comptes et plusieurs logements montre que le compte hors périmètre, ses métadonnées et ses statistiques restent inchangés ; une action globale présente la portée complète et une confirmation spécifique.

### A04 — Configurations et composant logiciel indépendants [option C validée]

**Décision :** supprimer des configurations Trybatec ne désinstalle pas automatiquement le composant installé par Marketplace ; si dernier compte supprimé, proposer le retrait logiciel séparé ; réinitialiser conserve le composant. **CA-A04 :** supprimer un compte parmi plusieurs ne touche pas au composant ; supprimer le dernier expose une option distincte ; refuser cette option conserve le composant ; réinitialiser ne déclenche jamais sa désinstallation.

### A05 — Désinstallation conservatrice propre [option B validée]

**Décision :** retirer le compte, les entités/appareils sans usage, les références Énergie invalides ; garder historiques/statistiques/données utiles ; panneau absent uniquement si plus aucun compte, selon A04. **CA-A05 :** pas d'entité orpheline créée par la procédure sous sa responsabilité ; références Énergie Trybatec non fonctionnelles nettoyées ; séries historiques inchangées ; autres intégrations inchangées. **Précaution :** « appareil devenu inutile » ne signifie pas « compteur déposé » ; ses données historiques sont préservées conformément à A06.

### A06 — Conservation fonctionnelle complète [option B validée]

**Décision :** conserver comptes/compteurs et chronologie historiques, états/statistiques, relevés, imports, versions, tarifs, paramètres métier, lissages, origines estimées, validations, métadonnées de réassociation ; supprimer éventuellement caches régénérables ; nouvelle authentification ; pas de nouvel export contenant des secrets. **CA-A06 :** après désinstallation/réinstallation simulée, les données historiques sont réassociables avec contrôle d'identité et sans doublons ; les décisions conservées restent attribuables à la bonne cible ; l'archive éventuelle ne révèle aucun secret.

### A07 — Réinitialisation des paramètres et décisions [validé]

**Décision :** effacer les paramètres, tarifs, décisions de lissage, origines estimées, validations et journaux techniques associés au périmètre. **CA-A07 :** chacun de ces jeux de données retourne à son état initial pour la cible ; les autres comptes restent inchangés ; le rapport détaille les objets effacés.

### A08 — Maintien de toutes les statistiques Recorder lors d'une réinitialisation [validé]

**Décision :** conserver toutes les statistiques Recorder, y compris celles des compteurs déposés. **CA-A08 :** contrôle avant/après des identifiants, des nombres de lignes et des plages temporelles de toutes les séries Recorder du périmètre ; aucune suppression induite par le reset. **Point à instruire :** sort des états Recorder non statistiques, non explicitement tranché.

### A09 — Portée de la purge complète dans Recorder [validé]

**Décision :** inclure séries statistiques, métadonnées et historique d'états exclusivement Trybatec lorsque la purge standard est demandée. **CA-A09 :** les séries exclusivement détenues par le périmètre et retenues pour suppression disparaissent du registre des statistiques et de la consultation historique ; les séries conservées au titre d'A10, partagées ou externes restent accessibles.

### A10 — Purge configurable et compteurs déposés [option C validée]

**Décision :** purge standard inclut les données locales des compteurs actifs/déposés, historique reconstitué, inventaire et métadonnées ; possibilité explicite de conserver l'historique, opération alors nommée « purge avec conservation d'historique ». **CA-A10 :** l'interface détaille chaque population et son volume ; conserver l'historique modifie effectivement le plan avant confirmation ; le libellé et le bilan reflètent la conservation.

### A11 — Propriété vérifiée des données [option B validée]

**Décision :** seules les ressources dont la propriété exclusive est établie sont supprimables ; protéger données partagées, externes ou incertaines ; rapporter les exceptions. **CA-A11 :** des séries homonymes détenues par un autre composant, des fichiers non attribuables et des ressources multi-comptes restent intacts ; chacune des exceptions est motivée. **Attention :** le préfixe de nom ou la présence de « trybatec » ne prouve pas à lui seul la propriété.

### A12 — Compatibilité de détection `.storage` [validé]

**Décision :** détecter les fichiers anciens, y compris renommés ou restructurés entre versions ; ne pas limiter l'inventaire à `trybatec*`. **CA-A12 :** jeux de tests avec anciennes clés/formats connus, fichiers aux noms génériques et versions de schéma différentes ; la procédure identifie, qualifie ou signale « attribution incertaine », mais ne supprime pas silencieusement un fichier générique entier contenant d'autres données.

### A13 — Inventaire détaillé préalable [validé]

**Décision :** avant validation, montrer identifiant exact, catégorie, compte/logement, nombre de lignes, dates extrêmes, volume, dépendances, conséquences, statut de propriété et opération prévue. **CA-A13 :** chaque élément envisagé est représenté par une entrée consultable et aucune catégorie ciblée n'est absente sans être marquée inaccessible/indéterminée. Pour les données groupées, permettre d'identifier le détail des composants.

### A14 — Prévisualisation sans effet [validé]

**Décision :** « examiner » ne modifie rien. **CA-A14 :** deux prévisualisations successives produisent une analyse sans écriture, sans purge, sans sauvegarde non autorisée, sans reload ni changement de registres. Les données peuvent évoluer entre prévisualisation et exécution ; le plan doit être revalidé si elles ne concordent plus.

### A15 — Confirmation renforcée pour purge complète [validé]

**Décision :** confirmation distincte et particulièrement explicite pour une purge, en plus de la sélection de mode. **CA-A15 :** aucun lancement destructif par simple consultation, sélection de case ou confirmation destinée à un autre mode ; afficher périmètre, catégories, volume, pertes irréversibles et sauvegarde ; exiger un acte affirmatif propre à la purge.

### A16 — Sauvegarde facultative pour tous les modes [option C validée]

**Décision :** vérifier les points de restauration, proposer une sauvegarde mais autoriser la poursuite **sans sauvegarde**, y compris en purge complète, après avertissement et confirmation renforcée. **CA-A16 :** un parcours sans sauvegarde est possible après reconnaissance du risque ; aucun déclenchement de sauvegarde non demandé ; refuser une sauvegarde ne bloque pas à lui seul l'opération.

### A17 — Évaluer les points de restauration [validé, combiné à A16]

**Décision :** avant acte irréversible, rechercher leur présence et évaluer leur exploitabilité. **CA-A17 :** l'interface différencie sauvegarde détectée, contenu adapté, intégrité vérifiée et restauration effectivement testée ; si une vérification est impossible, l'indique plutôt que de promettre une restauration. Une absence de sauvegarde est affichée comme risque, et non comme blocage automatique (A16).

### A18 — Retour arrière ciblé et reprise contrôlée [option B validée]

**Décision :** documenter l'ordre des étapes et leurs résultats ; en cas d'échec, arrêter les étapes dépendantes ; proposer une restauration ciblée seulement lorsqu'elle est prouvablement possible ; jamais de restauration globale automatique ; sans sauvegarde, signaler la perte définitive. **CA-A18 :** tests injectant échec avant/après chaque catégorie ; pas de répétition aveugle, plan de reprise fidèle à l'état réel et aucune affirmation mensongère de « rollback complet ».

### A19 — Références du tableau Énergie [validé]

**Décision :** retirer ou corriger les références invalides au périmètre Trybatec sans toucher aux autres sources. **CA-A19 :** sources non Trybatec conservées à l'identique ; références Trybatec préservées quand elles doivent rester opérationnelles ; aucun remplacement automatique par un capteur au sens énergétique incompatible ; contrôle de validation Énergie après action.

### A20 — Dépendances transversales [validé]

**Décision :** explorer les registres, YAML, automatisations, scripts, aides et tableaux de bord, et toutes les dépendances ciblées reconnues. **CA-A20 :** tests de références présentes dans chaque famille ; références inconnues ou non accessibles signalées comme limite ; aucune affirmation « aucune dépendance » sur une source non examinée.

### A21 — Propriété établie, pas simple nom [validé]

**Décision :** exiger des critères de propriété stricts pour toutes les suppressions. **CA-A21 :** une entité, série ou fichier dont la relation au compte n'est pas certaine est conservé et listé comme exception ; noms ressemblants d'autres intégrations protégés.

### A22 — API officielles priorisées [validé]

**Décision :** effectuer les opérations via les API Home Assistant quand elles existent. SQL direct et modification de fichiers internes `.storage` sont des chemins exceptionnels soumis à justification distincte. **CA-A22 :** trace de l'API utilisée ou justification documentée d'une voie exceptionnelle ; aucune édition silencieuse de l'état interne sans contrôle de compatibilité et intégrité.

### A23 — Configuration supprimée en dernier [validé]

**Décision :** l'opération retirant le compte/config entry est la dernière suppression prévue, après les nettoyages et contrôles dépendants, afin de préserver la disponibilité de l'assistant. **CA-A23 :** tests d'ordre montrent que la configuration reste accessible pendant le travail ; lorsque l'interface disparaît ensuite, le compte rendu doit demeurer accessible par un moyen prévu et autorisé. **Point technique à instruire :** support effectif de cette présentation après disparition du panneau.

### A24 — Journal complet [validé]

**Décision :** journaliser chaque opération « prévue, exécutée, réussie, ignorée, refusée, échouée », avec cible, temps, motif, résultat et volumes lorsque mesurables ; ne pas afficher de secrets. **CA-A24 :** un résultat partiel permet de reconstituer l'ordre, les effets et les erreurs, et distingue une action demandée d'une action réellement exécutée.

### A25 — Échecs partiels et reprise [validé]

**Décision :** sécurité en cas d'interruption ou de panne, reprise sans effacement hors périmètre ni double traitement dommageable. **CA-A25 :** répétition d'une demande après réponse perdue ne déclenche pas une deuxième purge non justifiée ; nouvelle vérification d'état précède la reprise ; les étapes non tentées sont connues.

### A26 — Contrôles après exécution [validé]

**Décision :** réexaminer entités, appareils, fichiers/stockages, statistiques, références, erreurs et résultats de l'opération. **CA-A26 :** bilan distingue confirmé, partiellement confirmé, non vérifiable et échec ; il n'annonce pas « suppression totale » si des dépendances ou objets résiduels demeurent.

### A27 — Tests automatisés seulement [option A validée]

**Décision :** tests unitaires et d'intégration **automatisés** ; couverture des modes, dépendances, multicomptes, confirmations, interruption, reprise, réinstallation sans doublons. Pas d'obligation de recette manuelle ou de tests destructifs sur Home Assistant réel. **CA-A27 :** chaque exigence A est liée à au moins un test automatisé ; les tests concernés réussissent avant de qualifier la version de prête ; un mock ne doit pas être présenté comme un test réel de Recorder.

### A28 — Accord spécifique pour chaque rechargement/redémarrage [option A validée]

**Décision :** aucun reload Trybatec, reload d'un autre composant ou redémarrage Home Assistant sans consentement spécifique préalable, même si cela pourrait simplifier le workflow. **CA-A28 :** tous les parcours qui le requièrent s'arrêtent sur une demande explicite et décrivent l'effet ; refus = aucune action ; bilan signale les actions à réaliser ultérieurement.

### A29 — Compatibilité CI/CD complète des suffixes `b0` [option B validée]

**Décision :** vérifier le traitement des suffixes `b0`, `b1`, etc., la cohérence versions/branches/tags/artefacts, les tris et mécanismes de mise à jour, et les tests de non-régression ; conserver les contrôles existants et séparer CI, fusion et release. **CA-A29 :** jeux d'exemples de versions bêta et stables, y compris `0.3.1b0` ; aucun contrôle qualité/sécurité désactivé ; un CI vert n'autorise pas automatiquement une fusion ni une publication.

### A30 — Publication simplifiée [option A validée]

**Décision :** préparer les notes de version, vérifier le succès des tests automatisés, puis demander l’autorisation explicite avant toute publication logicielle. Les exigences de A29 restent applicables ; la procédure de bilan enrichi d’A30-B n’est pas obligatoire. **CA-A30 :** aucun tag, release, push de code ou fusion sur seule réussite des tests ; notes de version présentes et publication logicielle soumise à un accord distinct. La publication du présent document ne vaut pas autorisation de livraison.

### A31 — Volume associé à **chaque** choix de conservation, purge ou suppression [validé après A30]

**Décision :** chaque décision individuelle affichée porte son volume correspondant ; les totaux « conservé / supprimé / éventuellement récupérable » sont recalculés en temps réel. Cette exigence porte sur les états Recorder, statistiques longues/courtes durées, séries historiques importées et versionnées, compteurs déposés, fichiers `.storage`, paramètres/tarifs/décisions et toutes les catégories ajoutées à l'inventaire.

**Champs attendus pour chaque élément/catégorie :** identifiant, propriétaire/périmètre, action envisagée, nombre de lignes ou d'objets, période, taille et unité, nature du volume (exact/estimé/indéterminé), méthode d'obtention, date de mesure, dépendances et conséquence. L'utilisateur doit pouvoir comparer les volumes des branches « garder » et « supprimer » avant de confirmer ; un élément partagé doit afficher son volume observé mais ne pas compter celui-ci comme intégralement supprimable.

**Règle de fiabilité :** privilégier tailles exactes de fichiers et mesures vérifiables ; si seule une estimation est disponible, la qualifier et en exposer la méthode ; si inaccessible, afficher **« volume indéterminé »** (jamais 0 par défaut). Ne pas additionner deux fois le même stockage sous plusieurs catégories ou le même fichier contenant plusieurs cibles.

**Règle SQLite obligatoire :** distinguer (i) volume logique des données ciblées ; (ii) espace devenu libre **dans** la base ; (iii) diminution réelle du fichier SQLite et de l'occupation disque. Les tailles exactes par ligne ne sont pas toujours disponibles, et une purge Recorder peut ne réduire aucun octet du fichier. Le total « récupérable » n'est pas assimilé au volume logique supprimé.

**CA-A31-01 :** chaque ligne de prévisualisation présente un volume ou « indéterminé », la période et la méthode ; les valeurs fictives de maquette ne doivent jamais apparaître comme données réelles. **CA-A31-02 :** choisir « conserver » plutôt que « supprimer » sur un groupe recalcule tous les totaux pertinents sans double comptage. **CA-A31-03 :** statistiques longues/courtes durées et états sont ventilés ; les fichiers `.storage` contiennent des tailles réellement relevées ou estimées avec provenance. **CA-A31-04 :** avant/après distinguent prévu, effectivement supprimé, effectivement conservé et non vérifiable. **CA-A31-05 :** pour SQLite, aucun gain réel sur disque n'est annoncé sans mesure après opération ; si la taille du fichier ne baisse pas, la colonne « espace disque récupéré » vaut 0 octet seulement si ce zéro est effectivement mesuré, sinon « indéterminé ». **CA-A31-06 :** pour un objet partagé/partiellement ciblé, l'interface distingue la taille totale du conteneur du volume directement attribuable au périmètre et explique l'incertitude.

---

## 5. Modèle de données de la prévisualisation et du rapport (contrat fonctionnel, non choix d'API)

Pour rendre A13 et A31 vérifiables, le résultat **doit permettre de restituer** les informations suivantes, sans présumer un stockage ou format réseau précis :

| Champ logique | Rôle | Règle de restitution |
|---|---|---|
| `resource_id` | Identifiant technique exact (entité, statistic_id, fichier, objet métier...) | Obligatoire si accessible ; sinon valeur « indisponible » justifiée |
| `resource_kind` | Compte, logement, compteur, état, statistique long/court, version, fichier, tarif, décision... | Catégorie non ambiguë |
| `owner_scope` | Compte/logement/installation et preuve d'appartenance | Valeur certaine, partagée ou indéterminée |
| `origin` | Portail, import manuel, intégration, Recorder, autre composant... | Ne jamais inventer la provenance |
| `time_range` / `record_count` | Période et volume d'enregistrements | « indéterminé » si non accessible |
| `storage_bytes` | Octets attribués à la ressource ou au sous-ensemble | Exact, estimé ou inconnu, **jamais implicite** |
| `measurement_method` / `measured_at` | Source, méthode, limites et date de mesure | Accompagne toute taille affichée |
| `shared_container_bytes` | Taille du fichier / DB contenant la donnée | Ne pas confondre avec taille attribuée |
| `dependencies` | Références Énergie, automations, scripts, YAML, tableaux... | Non inspecté ≠ aucune dépendance |
| `proposed_action` | Conserver, supprimer, purger, réinitialiser, exceptionnellement ignorer | Choix compatible avec le mode |
| `consequence` | Perte, restauration, référence cassée, impossibilité de réassociation, etc. | Explication concrète avant confirmation |
| `execution_status` | Non tenté / réalisé / ignoré / refusé / erreur / à contrôler | Renseigné après action |
| `recovery_status` | Rétablissable avec preuve / partiellement / non connu / irréversible | Distinguer présence et validation de sauvegarde |

**Règles de totalisation :** calculer l'union disjointe des ressources physiques pour chaque estimation afin d'éviter double comptage (p. ex. une statistique figurant également dans « historique importé »). Si une ventilation exacte n'est pas réalisable, préférer le total « estimé » et signaler le recouvrement plutôt que sommer naïvement. La taille de `home-assistant_v2.db` est celle d'un **conteneur partagé**, pas un volume effaçable Trybatec. Toute estimation SQLite par rangée doit documenter son hypothèse et ses limites. Le tableau Énergie représente des références et non nécessairement des données supplémentaires. L'interface n'affiche jamais secrets, mots de passe, tokens ou contenu YAML confidentiel dans l'inventaire.

**Concurrence et dérive :** si, entre prévisualisation et confirmation, des identifiants, dépendances, volumes ou règles de propriété changent matériellement, une nouvelle prévisualisation doit précéder l'exécution. La politique exacte de seuil de dérive et les détails de gestion des transactions restent à concevoir : aucune tolérance arbitraire n'a été validée.

---

## 6. Ordonnancement, échecs et preuves de fin

### 6.1 Ordre logique imposé par les décisions

1. Vérifier l'identité, les droits, le mode et la portée.
2. Inventorier, qualifier la propriété, détecter les dépendances, mesurer/estimer les volumes.
3. Prévisualiser, exposer les choix et risques ; vérifier les sauvegardes ; obtenir les confirmations exigées.
4. Retirer/corriger les références invalides vers les futurs objets supprimés, **sans affecter les autres sources**.
5. Exécuter les suppressions de données sélectionnées, uniquement dans le respect du mode et des exceptions.
6. Retirer les entités/appareils qui doivent disparaître après vérification de leurs dépendances.
7. Contrôler les résultats tant que l'intégration et son interface sont encore disponibles.
8. Retirer la configuration du périmètre **en dernier** si le mode le prévoit.
9. Afficher/mettre à disposition le bilan final ; demander séparément tout reload/restart et, si éligible, retrait du composant Marketplace.

Il s'agit d'un **ordre de dépendances fonctionnelles** : l'ordre exact de certaines API Recorder/registres devra être validé par tests automatisés ; aucune opération destructive ne doit être avancée avant l'autorisation requise.

### 6.2 Gestion des interruptions

- La procédure ne prétend pas disposer d'une transaction atomique globale : les APIs et magasins HA distincts peuvent être modifiés successivement.
- Toute action est associée à son identité, son périmètre, sa catégorie et un statut vérifiable ; le journal permet de distinguer « envoyé » de « résultat constaté ».
- En cas de rupture de connexion, relire l'état réel avant tout nouvel appel ; ne pas rejouer une purge sans contrôle.
- Les objets refusés pour propriété incertaine sont conservés et annoncés en fin de parcours, pas invisiblement ignorés.
- Un rollback ciblé ne doit pas restituer une sauvegarde globale qui écraserait d'autres configurations sans accord explicite et sans analyse d'impact.

### 6.3 États de sortie affichés

**Succès complet :** toutes les actions autorisées effectuées et confirmées, aucune exception empêchant la qualification du mode.  
**Succès avec exceptions :** opérations demandées effectuées sur les seules ressources prouvées, éléments incertains ou partagés conservés et explicitement comptés.  
**Partiel / reprise nécessaire :** opérations dépendantes interrompues, liste exacte des étapes exécutées et restantes.  
**Non vérifiable :** API ou sources indisponibles, résultat non prouvé ; ne jamais qualifier la suppression de totale.  
**Échec :** opération impossible ou erreur sans état final conforme, avec explication et actions manuelles envisageables.

---

## 7. Matrice de recette automatisée

La colonne « Références » assure la traçabilité ; chaque test doit avoir des assertions négatives (ce qui **ne doit pas** être supprimé) autant que positives.

| ID de test | Scénario automatisé obligatoire | Références |
|---|---|---|
| T01 | Accès admin via le panneau, refus de l'accès non admin au service et à l'UI | A01, A02 |
| T02 | Par défaut compte/logement ciblé, autres comptes préservés | A03, A11, A21 |
| T03 | Option globale distincte, confirmation renforcée spécifique | A03, A15 |
| T04 | Deux comptes : suppression du premier sans supprimer composant/panneau | A03, A04, A05 |
| T05 | Dernier compte : proposition séparée de retrait Marketplace, refus sans effet | A04, A23 |
| T06 | Désinstallation conservatrice : supprimer entités et références invalides, conserver états/statistiques | A05, A06, A19 |
| T07 | Réinstallation après désinstallation conservatrice : reprise des données historiques sans doublon | A06 |
| T08 | Archive éventuelle : absence de secrets et nouvelle authentification | A06 |
| T09 | Réinitialisation : effacement tarifs, validations, lissages, origines et journaux ciblés | A07 |
| T10 | Réinitialisation : conservation statistiques anciennes, nouvelles et compteurs déposés | A08 |
| T11 | Purge complète : séries, métadonnées statistiques et états exclusifs supprimés | A09, A11 |
| T12 | Purge avec conservation historique : statistiques/historiques sélectionnés préservés | A10, A11 |
| T13 | Inventaire complet des compteurs déposés et des historiques versionnés | A10, A13 |
| T14 | Série externe, partagée ou propriété incertaine : suppression refusée et exception tracée | A11, A21 |
| T15 | Stockage ancien : fichier clé générique et ancien schéma détectés sans suppression d'autres données | A12, A21 |
| T16 | Inventaire nominatif, périodes, quantités, volumes, conséquences et dépendances | A13, A20, A31 |
| T17 | Prévisualisation plusieurs fois sans écritures ni sauvegardes | A14, A16 |
| T18 | Action destructive impossible sans confirmation de purge spécifique | A15 |
| T19 | Aucune sauvegarde présente : avertissement mais possibilité de poursuivre après confirmation | A16, A17 |
| T20 | Sauvegarde existante mais contenu insuffisant : ne pas annoncer « restaurable » | A17 |
| T21 | Erreur simulée milieu de processus : arrêt dépendances et reprise après relecture | A18, A24, A25 |
| T22 | Aucune restauration globale automatique ; rollback ciblé seulement si fiable | A18 |
| T23 | Sources Énergie non Trybatec strictement inchangées après retrait de références invalides | A19 |
| T24 | Dépendances YAML, script, automatisation, aide et dashboard détectées ou non inspectées explicitées | A20 |
| T25 | Objet homonyme mais étranger : préservé | A21 |
| T26 | API native privilégiée ; usage SQL/.storage écrit non silencieux et justifié | A22 |
| T27 | Suppression configuration en dernier ; résultat disponible même si panneau disparaît | A23 |
| T28 | Journal horodaté avec réussis/refusés/ignorés/erreurs et quantités | A24 |
| T29 | Redémarrage du processus : pas de suppression répétée non contrôlée | A25 |
| T30 | Contrôle post-exécution des registres, fichiers, Recorder et références ; état incomplet annoncé | A26 |
| T31 | Exécution CI des tests unitaires/intégration sans recette manuelle imposée | A27 |
| T32 | Refus d'un rechargement ou d'un redémarrage : aucune exécution | A28 |
| T33 | Suffixe b0, b1, version stable ; cohérence tags/version/artefacts, non-régression | A29 |
| T34 | CI réussi sans fusion ni release automatique ; notes de version et autorisation distincte | A29, A30 |
| T35 | Volume ou « indéterminé » pour **chaque** décision de conserver/supprimer | A31 |
| T36 | Recalcul interactif des volumes sans double comptage lorsque l'utilisateur change d'option | A31 |
| T37 | Différencier taille totale SQLite, taille logique estimée et gain disque mesuré | A31 |
| T38 | Volumes avant/après et exceptions, dont ressource partagée et taille partiellement attribuable | A24, A26, A31 |
| T39 | Prévisualisation devenue obsolète après modification de ressources/dépendances : nouveau contrôle avant action | A13, A14, A21 |
| T40 | Périmètre global + option historique : autres intégrations et portail distant jamais touchés | A03, A10, A11 |

**Critère d'acceptation de la livraison :** toutes les exigences A01–A31 sont couvertes par des assertions automatisées ; les tests pertinents sont réussis, les contrôles A29 sont satisfaits et toute lacune est signalée avant autorisation de publication. Une suite simulée réussie ne doit pas être décrite comme une recette réelle de la base Home Assistant de l'utilisateur.

---

## 8. Registre de traçabilité synthétique A01–A31

| ID | Statut / option validée | Domaines de contrôle | Tests |
|---|---|---|---|
| A01 | Validé | Menu administration | T01 |
| A02 | Validé | Droits administrateur | T01 |
| A03 | Option C | Portée ciblée/globale | T02–T04, T40 |
| A04 | Option C | Découplage Marketplace | T04–T05 |
| A05 | Option B | Désinstallation propre | T04, T06 |
| A06 | Option B | Conservation et réinstallation | T06–T08 |
| A07 | Validé | Reset métier | T09 |
| A08 | Validé | Stats préservées | T10 |
| A09 | Validé | Purge Recorder | T11 |
| A10 | Option C | Purge et historiques facultatifs | T12–T13, T40 |
| A11 | Option B | Propriété exclusive | T11–T14, T40 |
| A12 | Validé | Anciennes générations .storage | T15 |
| A13 | Validé | Inventaire | T13, T16, T39 |
| A14 | Validé | Prévisualisation sans effet | T17, T39 |
| A15 | Validé | Confirmation purge | T03, T18 |
| A16 | Option C | Sauvegarde facultative | T17, T19 |
| A17 | Validé | Vérification des restaurations | T19–T20 |
| A18 | Option B | Rollback ciblé | T21–T22 |
| A19 | Validé | Énergie | T06, T23 |
| A20 | Validé | Dépendances | T16, T24 |
| A21 | Validé | Propriété stricte | T02, T14–T15, T25, T39 |
| A22 | Validé | API et exceptions | T26 |
| A23 | Validé | Config supprimée en dernier | T05, T27 |
| A24 | Validé | Journal | T21, T28, T38 |
| A25 | Validé | Reprise | T21, T29 |
| A26 | Validé | Contrôle final | T30, T38 |
| A27 | Option A | Tests automatisés seuls | T31 |
| A28 | Option A | Consentement reload/restart | T32 |
| A29 | Option B | CI b0 et non-régression | T33–T34 |
| A30 | Option A | Publication simplifiée contrôlée | T34 |
| A31 | Validé | Volumes individuels, totaux, SQLite | T16, T35–T38 |

---

## 9. Orientations V01–V16 et exclusions R01–R08

**Attention à la nature des statuts :** V et R reprennent la première **checklist de synthèse de l'assistant**, entérinée comme référentiel d'orientation lors de la suite des arbitrages, mais ne constituent **pas 24 nouveaux votes A**. D sont des opérations constatées sur l'installation de l'utilisateur et **non des fonctionnalités à implémenter**.

### 9.1 Orientations V01–V16 précédemment retenues

| Réf. | Orientation conservée |
|---|---|
| V01 | Préparer une version bêta désignée `0.3.1b0`. |
| V02 | Distinguer trois modes de traitement plutôt qu'une suppression indifférenciée. |
| V03 | Désinstallation conservatrice maintenant les historiques utiles. |
| V04 | Réinitialisation permettant un nouveau départ sans supprimer les statistiques Recorder. |
| V05 | Purge complète possible des éléments exclusivement Trybatec, historiques inclus. |
| V06 | Réinstallation propre après retrait ou réinitialisation. |
| V07 | Inclure les anciens `entity_id` et `unique_id` au diagnostic de résidus. |
| V08 | Gérer les anciens appareils techniques orphelins sans assimiler tout compteur déposé à un déchet. |
| V09 | Prendre en compte les anciens états Recorder et les séries statistiques inutiles. |
| V10 | Auditer les fichiers internes `.storage`, décisions, validations, migrations, historiques et audits. |
| V11 | Traiter les références résiduelles en Énergie, dashboards, automatisations, scripts et configuration. |
| V12 | Ne pas rendre obligatoire la conservation des historiques du tableau Énergie dans une purge explicite. |
| V13 | Ne pas supprimer de données étrangères à Trybatec. |
| V14 | Inventaire préalable en lecture seule avant intervention destructive. |
| V15 | Consentement explicite avant effets externes. |
| V16 | Ne pas désinstaller la version en service pour le seul nettoyage des résidus d'entités. |

### 9.2 Exclusions R01–R08 conservées

| Réf. | Solution écartée / non autorisée |
|---|---|
| R01 | Imposer le maintien de références obsolètes dans le tableau Énergie. |
| R02 | Supprimer les compteurs déposés pendant un simple nettoyage d'entités anciennes. |
| R03 | Supprimer les capteurs actifs d’une génération courante pendant un nettoyage sélectif de générations anciennes. |
| R04 | Modifier ou supprimer les données des autres intégrations. |
| R05 | Supprimer sans preuve de propriété tout élément contenant « Trybatec » dans son nom. |
| R06 | Effectuer une suppression non inventoriée ou sans accord explicite. |
| R07 | Créer une sauvegarde sans consentement explicite, y compris pendant un audit ou un nettoyage. |
| R08 | Considérer la validation des spécifications comme une autorisation implicite de modifier le code, fusionner une PR ou publier une release. |


---

## 10. Questions de mise en œuvre explicitement **non tranchées**

Ces points doivent être étudiés techniquement et, s'ils impliquent une nouvelle décision fonctionnelle ou un effet externe, être soumis à l'utilisateur ; **ils ne sont pas des décisions supplémentaires déjà validées** :

1. **Conservation historique et fichier `.storage` mixte :** format concret d'une conservation sélective lorsqu'un fichier contient plusieurs comptes, versions ou données non Trybatec ; procédure fiable via API éventuelle.
2. **États Recorder pendant un reset :** A08 protège expressément toutes les statistiques ; le statut des états historiques non agrégés nécessite une formulation définitive avant codage destructif.
3. **Réinstallation sans doublons :** schéma exact de réassociation des entités/statistiques/imports et interaction avec les identifiants HA conservés, notamment après suppression de la config entry.
4. **Mesure par ligne SQLite :** méthode fiable de volume logique imputable par ressource, coût de calcul et traitement des pages partagées ; l'impossibilité doit rester visible plutôt qu'être masquée.
5. **Capacité Marketplace :** API réellement disponible pour désinstaller le composant, ou simple guidage manuel ; A04 ne présume pas l'existence d'une API.
6. **Dernier affichage de rapport :** disponibilité du bilan si le panneau ou la config entry disparaît après la dernière étape A23.
7. **Sémantique du contrôle « sauvegarde exploitable » :** vérifications techniquement possibles sans restauration réelle ; comment afficher une restauration non testée.
8. **Gestion des données partagées :** rattachement aux autres comptes et conflits entre une « purge globale » et une statistique possédée aussi par un composant externe.
9. **Disponibilité des API :** version de Home Assistant et capacités effectives de `recorder`, registres, Energy, et gestion des fichiers ; plan d'échec sûr lorsque l'API manque.
10. **Rechargements :** dépendances techniques d'un reload/restart et conséquences du refus (A28) ; aucun contournement par automatisation implicite.
11. **Rapport de volumes :** conservation des unités, précision, format d'export éventuel, calendrier de mesure et politique de recalcul ; sans inventer de seuil de taille ni de durée.
12. **Niveau de tests automatisés des API natives :** utilisation de faux environnements, fixtures de sauvegarde, et limites des mocks ; A27 exclut d'imposer un test destructif sur une installation réelle.
13. **Purge des données relevant d'autres modules :** traitement conservateur des références cassées dans des tableaux/automatisations appartenant à un autre composant, et distinction entre correction autorisée et suppression non autorisée.
14. **Limites de collecte des sources YAML et des registres :** recherches exhaustives sans exposition de mots de passe, clés ou jetons, et statut clair des fichiers inaccessibles.

Tant que les réponses techniques n'existent pas, une fonctionnalité peut être documentée et acceptée en principe, **mais ne doit pas être déclarée prête pour publication** si elle ne respecte pas les invariants validés.

---

## 11. Portes de validation et gouvernance de livraison

### 11.1 Statuts à ne pas confondre

- **Spécification approuvée :** A01–A31, objet du présent document.
- **Implémentation réalisée :** aucune affirmation à ce stade.
- **Tests exécutés et réussis :** aucune affirmation pour `0.3.1b0`.
- **Conformité CI/CD :** à vérifier sur le dépôt réel.
- **Fusion et publication :** exige chacune une autorisation explicite, distincte de la spécification et des validations CI.

### 11.2 Livrables à produire lors du développement (pas créés ici)

- Code des trois parcours et leurs variantes, avec politique stricte d'administration.
- Tests automatisés T01 à T40, ou tests équivalents explicitement reliés à chaque exigence.
- Inventaires, prévisualisations et rapports individuels de volumes A31, avec méthode de mesure.
- Documentation utilisateurs et notes de version `0.3.1b0`.
- Adaptations et tests CI/CD de prise en charge `b0` sans affaiblissement des contrôles.
- Traçabilité des erreurs, des exceptions et des décisions de conservation.

### 11.3 Interdictions de ce document

**La rédaction et la publication de cette spécification n’autorisent pas** : modification du code, création de PR de développement, édition de fichiers en production, suppression de données, sauvegarde, exécution de tests destructifs sur Home Assistant réel, rechargement/redémarrage, fusion ou publication d’une version logicielle. Une demande spécifique distincte doit autoriser toute action ultérieure.

---

## 12. Synthèse décisionnelle finale

- **31 arbitrages validés :** A01–A31 ; A31 ajouté après les 30 arbitrages initiaux.
- **Choix à options effectivement validés :** A03-C, A04-C, A05-B, A06-B, A10-C, A11-B, A16-C, A18-B, A27-A, A28-A, A29-B, A30-A (**12** choix à options).
- **Principe central :** une opération est définie par sa portée précise, ses objets prouvés, les décisions individualisées de conserver ou effacer, les dépendances, les risques, les volumes A31 et une confirmation spécifique.
- **Sauvegarde :** vérification et offre obligatoires, réalisation **facultative** ; pas de faux engagement de réversibilité.
- **Recette :** automatisée uniquement ; les limites de la simulation doivent être déclarées.
- **Publication :** simplifiée (A30-A), mais **toujours autorisée explicitement** et soumise à A29.
- **État du document :** référentiel fonctionnel publié, distinct de toute autorisation d’implémentation ou de diffusion logicielle.