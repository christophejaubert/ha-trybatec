# 🤖 #70 — Réconciliation de l'emblème / Brand asset reconciliation

## FR — Périmètre et constat

Issue [#70](https://github.com/christophejaubert/ha-trybatec/issues/70). Références : [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md), [UI_GUIDELINES.md](UI_GUIDELINES.md) et [WCAG 2.2](https://www.w3.org/TR/WCAG22/).

Cette PR corrige **uniquement** la palette indexée des deux PNG du logo : `icon.png` (256 × 256) et `icon@2x.png` (512 × 512). Les images sont produites à partir des ressources publiques de `main` au SHA `a1bd6d8558c8fe1cc13cadeb1ff4aaa20528dc53`.

| Rôle | Ancienne couleur 256 / 512 | Couleur canonique |
|---|---|---|
| Eau froide (EF) | `#0B85D7` / `#0B84D7` | `#0A84D8` |
| Eau chaude (ECS) | `#C7395C` / `#C7395D` | `#C73A5C` |
| Chauffage (CET) | `#DF9F24` / `#DF9F25` | `#E0A126` |
| Marque | `#4F9E49` / `#4D9D47` | `#4E9E4A` |

Les entrées PLTE concernées sont respectivement les indices EF=2, ECS=4, CET=3 et marque=5. Le patch modifie uniquement les 12 octets RGB de ces quatre entrées et le CRC du bloc PLTE de chaque fichier. Aucun octet IDAT, tRNS ou IHDR n'est modifié : les indices de pixels, la géométrie et la transparence restent identiques aux ressources précédentes.

**Test de non-régression supplémentaire :** `tests/test_brand_canonical_render_70.py` décode les lignes de pixels indexés (filtres PNG 0–4), vérifie que chaque teinte canonique figure effectivement dans les pixels visibles et réutilise les contrôles de CRC, dimensions et transparence de `scripts/brand_asset_audit.py`.

### Acceptation restant nécessaire

- Vérifier humainement la silhouette approuvée (trois formes entrelacées, séparation blanche, accents verts internes, pas de cercle extérieur) et la lisibilité de l'emblème à petite taille.
- Contrôler les références du panneau à l'image réellement servie, les thèmes Home Assistant clair/sombre, y compris le cache de ressource.
- Conserver #70 ouverte tant que contraste des composants, clavier, reflow, zoom 200 %, lecteur d'écran et recette réelle ne sont pas démontrés.
- Une CI au vert sur un SHA exact n'est pas une recette Home Assistant.

**Sécurité :** aucun ID d'installation, aucune consommation, aucun identifiant personnel ; aucun fichier du panneau ou de la PR tarifaire #118 modifié. Pas de fusion, release ou modification de Home Assistant.

## EN — Scope and evidence

This PR fixes only the indexed PNG palettes for the 256px and 512px Trybatec emblem assets. All four approved exact RGB values are now declared consistently: cold water `#0A84D8`, hot water `#C73A5C`, heating `#E0A126`, brand `#4E9E4A`.

The only modified bytes are the four PLTE RGB entries and the PLTE CRC in each PNG. Indexed raster data (IDAT), alpha (tRNS) and dimensions (IHDR) are bit-for-bit preserved. The new regression test reconstructs visibly used indexed pixel colours instead of treating palette declaration alone as proof of actual usage.

**Outstanding:** human review of the approved emblem shape and small-size readability; actual light/dark Home Assistant display, browser cache and asset references; remaining #70 WCAG and keyboard/screen reader acceptance. The test does **not** certify a live Home Assistant installation or overall WCAG 2.2 AA conformity.

No changes to the tariff-owned panel, private data, Recorder, Energy, migration or production.
