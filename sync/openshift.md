# Sync lore-mcp → openshift

> Dernière MàJ : 2026-09-18 (sync 35)
> Source : sessions lore-mcp 15-18 sept
> Ce fichier est maintenu par le dépôt lore-mcp.
> Il est lu par le dépôt openshift au `sync`.

## État du projet

### Statistiques

- 17 modules Python (dont preprocess/), 453 tests
- Branche active : feat/E12-preprocessing-tool
- Release tag : v0.1.0-dev

### Backlog E12 — preprocessing (en cours)

**`Implémenté`** cette itération (15-18 sept) :
- E12.25 IS lifecycle (start/stop/health check)
- E12.26 Sequential 4-phase pipeline
- E12.23 OCR artifact correction + column reorder
- E12.27 Progressive output + VLM resilience
- E12.28 Multi-model captioning + judge selection

**`À faire`** :
- E12.10 Build integration (config YAML pending)
- E12.24 Docling VLM scannés (bloqué Python 3.14)
- E12.13 Proposition indexing (hors MVP)

### Résultats clés

**Pipeline 4 phases** opérationnel :
1. Parse (Docling/trafilatura/markitdown)
2. Caption (multi-model, séquentiel)
3. Clean + Enrich (LLM context/qa/meta)
4. Dedup + Validate + Write

**Test corpus 18 sources** : 18/18 OK, 10
formats (HTML, PDF, MD, CSV, DOCX, PPTX, XLSX,
PNG, JPG, JSON).

**Multi-model captioning** (E12.28) :
- Config: `parse.caption_models` liste de modèles
  du registre LLM
- Tous les modèles tournent séquentiellement
- Un fichier phase2-caption-{name}.md par modèle
- Sélection par juge LLM configurable
- 3 IS captioning disponibles : granite-docling
  (GPU 15s), granite-vision (GPU 6s), Molmo
  (CPU 100-490s)

**Études réalisées** :
- OCR comparison (5 moteurs, RapidOCR meilleur
  pour le FR). `docs/studies/ocr-comparison-
  2026-09-15.md`
- Captioning benchmark (5 modèles, 4 types
  d'images). `docs/studies/captioning-benchmark-
  2026-09-18.md`
- Model compliance (rerankers, VLM, embedding).
  granite-reranker EN-only seul libre, mmarco
  non-compliant (MS MARCO NC)

**Findings** :
- SmolVLM-256M inutilisable pour le RAG
  (descriptions trop génériques)
- Docling 26-class classifier inutilisable sur
  images PPTX (0/5 correct)
- granite-docling excelle sur slides/screenshots,
  échoue sur BD/timelines
- Molmo 7B CPU : captioning utilisable mais lent
  et hallucinations

### Contrat d'interface

Inchangé depuis sync 34. Ajout :
- `parse.caption_models` : liste de modèles pour
  le captioning multi-model
- `parse.caption_selection` : stratégie de
  sélection (judge, first_nonempty, longest)
- `parse.caption_judge` : modèle juge LLM
- `start_timeout` : timeout par modèle dans le
  registre LLM

## Retours IS captioning (2026-09-18)

Tests d'intégration avec les 3 IS sur le DUDH
(image scannée 2480×3548, 1.8MB) :

| IS | Port | Résultat | Cause probable |
|----|------|----------|----------------|
| granite-docling | 8091 | timeout 600s | Image trop grande pour 258M en inférence |
| granite-vision | 8092 | HTTP 507 | Insufficient Storage — VRAM saturée par l'image haute résolution |
| molmo | 8090 | timeout health 600s | Première inférence CPU 7B FP32 trop longue |

**Actions suggérées** :
- Investiguer la limite de résolution de chaque
  IS (max pixels / max base64 size)
- Considérer un redimensionnement côté serveur
  (pas côté client lore-mcp — on envoie l'image
  originale, c'est au serveur de gérer)
- Le health check lore-mcp envoie un pixel 1×1
  PNG — si ça passe mais que les vraies images
  échouent, le health check est insuffisant

Les tests sur le PPTX (images plus petites,
46-395KB) fonctionnaient correctement avec les
3 modèles.

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
