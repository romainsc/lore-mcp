# Grooming E12.42 — Multi-model via Docling natif

- **Status:** Prêt
- **Date:** 2026-09-21

## Problem

La phase 2 (modèles additionnels) utilise encore
du code VLM custom (`_vlm_api_call`, `caption_image`)
alors que Docling gère nativement le captioning
via API. Le document est re-parsé N fois si on
lance Docling N fois.

## Recherche préliminaire

Le document Docling est sérialisable :
- `DoclingDocument.save_as_json()` / `load_from_json()`
- `PictureDescriptionApiModel` existe comme
  modèle indépendant dans Docling

À vérifier : si `PictureDescriptionApiModel`
peut s'appliquer sur un document chargé depuis
JSON (les images bitmap doivent être accessibles).

## Solution

### Architecture parse-once, caption-N

```
Phase 1a: Parse (sans captioning, subprocess)
  Docling parse → document sérialisé JSON
  → subprocess exit (VRAM libérée)

Phase 1b: Pour chaque modèle caption :
  → Start IS
  → load_from_json → appliquer PictureDescriptionApiModel
  → export_to_markdown → phase-{model}.md
  → Stop IS

Judge → sélectionne le meilleur

Phase 2: Clean + Enrich
Phase 3: Validate + Write
```

### Avantages

- Parse une seule fois (OCR, layout, tables)
- Chaque modèle bénéficie du traitement Docling
  natif (classification, area threshold, batching)
- Zéro code VLM custom — tout passe par Docling
- IS lifecycle par modèle (VRAM propre)
- Le juge compare des résultats Docling homogènes

### Investigation (2026-09-21, vérifié)

Testé sur le PPTX Parcoursup (49 images) :
1. ✅ `save_as_json` : 6.7 MB, 49 pictures
2. ✅ `load_from_json` : 49 pictures intactes,
   `pil_image` rechargeable
3. ✅ `ItemAndImageEnrichmentElement` construit
   depuis les pictures rechargées
4. ✅ `PictureDescriptionApiModel` instancié
   seul avec config API custom
5. ✅ `model(doc, elements)` prêt à appeler

Pas de risque : les images survivent au JSON
(stockées en base64 dans `ImageRef.uri`).

## DoD

1. Multi-model via Docling natif (pas de code
   VLM custom)
2. Parse une seule fois
3. Chaque modèle produit son phase file
4. Judge sélectionne parmi N résultats Docling
5. `_vlm_api_call`, `caption_image` supprimés
   de parse.py
6. Tests passent

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
