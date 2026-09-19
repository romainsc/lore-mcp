# Sync lore-mcp → openshift

> Dernière MàJ : 2026-09-19 (sync 36)
> Source : sessions lore-mcp 15-19 sept
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

## Retours IS captioning (2026-09-19, sync 36)

### granite-vision 507 — diagnostic précis

**Symptôme** : granite-vision retourne HTTP 507
sur DUDH (2480×3548) systématiquement dans le
pipeline lore-mcp, alors que le test IS isolé
fonctionne en 25s.

**VRAM au moment du start** : 150 MiB utilisés,
3670 MiB libres. Suffisant.

**Cause racine** : `GET /health` retourne OK
**avant** que le modèle soit prêt pour
l'inférence. Le serveur IS répond "healthy"
dès que uvicorn est up, mais le modèle est
encore en cours de chargement GPU. La première
requête d'inférence (DUDH, 70 patches) arrive
pendant le chargement → OOM.

**Preuve** (logs IS capturés par lore-mcp) :
le log se termine à "Loading weights: 100%" +
"Application startup complete" + warning
bitsandbytes. Pas de requête traitée avant le
507.

**Timing** :
- 17:43:38 : Service ready (/health OK)
- 17:43:41 : Caption failed 507 (3s après ready)

**Fixes demandés** :
1. `/health` ne doit retourner OK qu'après
   qu'une inférence de test ait réussi (pas
   juste uvicorn up)
2. Le script start doit vérifier la VRAM libre
   avant de lancer le modèle et avertir si
   marge < 1 Go (déjà mentionné sync IS E17.07)
3. Le script stop doit s'assurer que la VRAM
   GPU est libérée avant de retourner (podman
   stop est asynchrone pour la libération VRAM)

**Côté lore-mcp (corrigé, E12.31)** :
Phase 1 (Docling parse) tourne maintenant dans
un **subprocess**. À sa sortie, le contexte CUDA
PyTorch est entièrement libéré.

VRAM mesurée au moment du start granite-vision :
**22 MiB utilisés, 3798 MiB libres**. C'est la
VRAM au repos, totalement propre. Rien de plus
ne peut être libéré côté lore-mcp.

Malgré 3798 MiB libres, granite-vision retourne
507 sur DUDH. Le modèle charge (3588 MiB
utilisés, 232 MiB libres) puis OOM à la
première inférence (DUDH 70 patches). 

Le sync IS indique "non reproductible" et "au
bord exact de la capacité". Mais côté
consommateur, avec 3798 MiB libres (le maximum
possible), le 507 est **systématique** sur DUDH.
Si granite-vision ne peut pas traiter une image
2480×3548 avec 3798 MiB libres, soit le serveur
doit redimensionner en interne, soit le modèle
NF4 4B n'est pas adapté à cette carte GPU pour
les images haute résolution.

### granite-docling — mésusage corrigé

granite-docling-258M n'est pas un modèle de
captioning. IBM : "only as part of the Docling
library", "not intended for general image
understanding". Retiré de `caption_models`.
Item E12.30 créé pour l'intégration via
Docling VlmPipeline en phase 1.

### molmo — fonctionne

molmo-7b captioning fonctionne sur DUDH (CPU,
~12 min). Le juge sélectionne correctement
l'OCR quand il est plus complet que le caption
Molmo.

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
