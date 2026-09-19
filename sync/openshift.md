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

**Traces diagnostic détaillées (E12.32+34,
2026-09-19, --debug)** :

```
Lancement lore-mcp :         VRAM 22/3798 MiB
CUDA check (subprocess) :    VRAM 22/3798 MiB
Après phase 1 subprocess :   VRAM 22/3798 MiB
Avant start granite-vision : VRAM 22/3798 MiB
Image :                      2480x3548 RGBA
Après modèle chargé :        VRAM 2646/1174 MiB
Après classify (1ère req) :  VRAM 3588/232 MiB
507 sur caption (2ème req) : "GPU or VRAM shared"
Après stop :                 VRAM 22/3798 MiB
```

Côté consommateur, la VRAM est **totalement
propre** à 22 MiB (le minimum absolu) au moment
du start granite-vision. Le check CUDA se fait
dans un subprocess (zéro impact VRAM). La phase 1
Docling tourne aussi dans un subprocess.

**Le problème est dans le serveur IS** :
la 1ère requête (classify, prompt court) fait
passer la VRAM de 2646 à 3588 MiB (+942 MiB
d'activations). Ces activations ne sont pas
libérées entre les requêtes. La 2ème requête
(caption) trouve 232 MiB libres → OOM 507.

**Test après mise à jour IS (empty_cache)** :
le 507 persiste malgré l'ajout de
`torch.cuda.empty_cache()` côté IS.

Body 507 détaillé (améliorations IS visibles) :
```
Tried to allocate 74.00 MiB
GPU total: 3.73 GiB
Free: 51.94 MiB
Process uses: 3.65 GiB
PyTorch allocated: 3.45 GiB
PyTorch reserved but unallocated: 107.02 MiB
```

Le serveur a besoin de 74 MiB, 51.94 libres.
107 MiB sont "reserved but unallocated" —
`empty_cache` ne les a pas récupérés.
C'est de la **fragmentation mémoire GPU**.

PyTorch suggère `PYTORCH_CUDA_ALLOC_CONF=
expandable_segments:True` pour éviter la
fragmentation. Le fournisseur IS pourrait
ajouter cette variable d'environnement au
conteneur.

**Pattern d'appel lore-mcp** :
1. Probe health (image 1×1 pixel)
2. Classify (image 2480×3548 + prompt court)
3. Caption (image 2480×3548 + prompt long)
→ chaque appel alloue/libère des activations
  de tailles différentes → fragmentation.

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
