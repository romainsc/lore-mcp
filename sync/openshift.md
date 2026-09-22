# Sync lore-mcp → openshift

> Dernière MàJ : 2026-09-22 (sync 37)
> Source : sessions lore-mcp 19-22 sept
> Ce fichier est maintenu par le dépôt lore-mcp.
> Il est lu par le dépôt openshift au `sync`.

## État du projet

### Statistiques

- 17 modules Python (dont preprocess/), 427 tests
- Branche active : feat/E12-preprocessing-tool
- Release tag : v0.1.0-dev

### Backlog E12 — preprocessing (en cours)

**`Implémenté`** cette itération (19-22 sept) :
- E12.30 Docling-native architecture refonte
- E12.42 Multi-model via Docling natif (parse once, caption N)
- E12.43 Tesseract OCR + langue par source (Level 1-2)
- E12.44 Configurable timeout per model in LLM registry

**`À faire`** :
- E12.45 Standalone photo/infographic fallback
- E12.46 Enrich meta labels in source language
- E12.10 Build integration (config YAML pending)
- E12.24 Docling VLM scannés (bloqué Python 3.14)
- E12.13 Proposition indexing (hors MVP)

### Résultats clés

**Architecture Docling-native** (E12.30+42) :
- Parse-once, caption-N via Docling JSON
  serialization
- `PictureDescriptionApiModel` pour le captioning
- ~350 lignes de code VLM custom supprimées
- Subprocess isolation pour la phase 1 parse

**Tesseract OCR** (E12.43) :
- Level 1-2 libre (remplace RapidOCR Level 3)
- 0 artefact I' sur le français avec `fra`
- `lang` par source dans le manifest
- tesseract-osd interdit (régression Docling)

**Audit full 18 sources** (2026-09-22) :
- 18/18 traités, 16/18 exploitables RAG
- 0 artefact OCR I'
- 1 bug : pexels photo vide (E12.45)
- 1 amélioration : labels enrich_meta FR (E12.46)
- Molmo timeout résolu par E12.44 (600s)

**Études réalisées** :
- OCR engine benchmark (6 moteurs, Tesseract seul
  Level 1-2). `docs/studies/ocr-engine-benchmark-
  2026-09-21.md`
- Docling capabilities analysis (PictureDescription
  API, JSON serialization). `docs/studies/docling-
  capabilities-analysis-2026-09-20.md`

### Contrat d'interface

Ajouts depuis sync 36 :
- `timeout` : timeout d'inférence par modèle
  dans le registre LLM (E12.44, défaut 180s)
- `parse.ocr_engine` : moteur OCR (tesseract)
- `parse.ocr_lang` : langues OCR fallback
- `lang` : champ par source dans le manifest

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
