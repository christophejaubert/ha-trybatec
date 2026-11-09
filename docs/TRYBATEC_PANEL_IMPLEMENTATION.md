# Interface Trybatec — première PR d'architecture (issue #45)

Le panneau Home Assistant supplémentaire **Trybatec** est livré en tant que
web component autonome, sans supprimer l'interface de configuration actuelle.

## Architecture

- `panel_api.py` : enregistrement sous `/trybatec`, module JavaScript statique
  local, WebSocket **administrateur uniquement**. Aucune donnée sensible
  (mot de passe, jeton API ou UUID de la copropriété) ne figure dans la réponse.
- `panel/trybatec-panel.js` : sept sections avec une mise en page réactive,
  bureau et mobile : vue d'ensemble, compteurs, historique et lissage,
  tarifs, Énergie et versions, diagnostics, réglages.
- État des compteurs : distinction **en service**, **déposé** et **inconnu**.
  L'inventaire fusionne uniquement les identités physiques exactes (lot,
  fluide, numéro), en laissant les appareils et historiques distincts.
- Audit technique : affiche les entités Trybatec et leurs états. Une entité
  indisponible **n'est jamais déclarée supprimable automatiquement**.
- Le panneau montre les tarifs annuels déjà enregistrés, les séries Recorder
  versionnées et les références actuelles d'Énergie sans les modifier.
- Les accès aux Options Trybatec et aux Actions HA subsistent ; aucun service
  existant, capteur, `unique_id` ou assistant de configuration n'est retiré.

## Ce que ce socle ne fait pas encore

Les formulaires de saisie des tarifs sans JSON, les corrections de relevé,
les visualisations avant/après de lissage, les migrations contrôlées et
l'activation des versions Recorder/Énergie sont les **lots suivants**. Ils ne
sont ni simulés ni annoncés comme fonctionnels dans le panneau. Ces fonctions
seront intégrées avant de considérer l'issue #45 comme terminée ou de
publier `0.3.0b1`.

**Périmètre limité aux tests et au dépôt :** pas d'installation sur
Home Assistant de production, pas d'import, pas de modification des
préférences Énergie ni de suppression d'ancienne entité.

## Recette

- [ ] 34 contrôles CI sur le SHA de PR réussis ou explicitement ignorés.
- [ ] Vérifier la compatibilité des flux d'options natifs existants.
- [ ] Vérifier que l'accès WebSocket exige un compte administrateur.
- [ ] Vérifier que les compteurs déposés restent des appareils historiques.
- [ ] Vérifier le rendu FR et les parcours bureau/mobile sur HA réel (non
      attestable par de simples tests unitaires).
