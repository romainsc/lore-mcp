# Grooming E12.32 — VLM diagnostic traces

- **Status:** Prêt
- **Date:** 2026-09-19

## Problem

granite-vision retourne 507 sur DUDH dans le
pipeline lore-mcp mais pas en test IS isolé.
Le fournisseur IS demande des traces pour
diagnostiquer l'écart.

## Traces demandées (IS sync E17.07)

1. VRAM avant chaque appel VLM (pas juste au
   démarrage)
2. Taille du payload JSON (octets)
3. Dimensions et mode de l'image avant encodage
4. CUDA context du processus lore-mcp
5. Body de la réponse 507

## Solution

### Verbosité debug à deux niveaux

- `--debug` : traces lore-mcp uniquement (tout
  ce que lore-mcp reçoit et produit). Les
  loggers tiers restent à WARNING.
- `--debug --debug` (ou `--debug-all`) : active
  le mode debug de tous les composants
  (Docling, RapidOCR, onnxruntime, etc.)

### Traces ajoutées sous --debug

Dans `_vlm_api_call()` :
- VRAM (nvidia-smi) avant chaque appel
- Taille du payload JSON (KB)
- Type mime et taille base64

Dans `caption_image()` :
- Dimensions et mode image (PIL)
- Taille fichier (KB)

Sur erreur HTTP (507, etc.) :
- Body de la réponse (500 premiers chars)
- VRAM après l'erreur

Dans `preprocess_sources()` :
- `torch.cuda.is_available()` au démarrage
- VRAM au démarrage du processus main

### Logging levels

| Mode | lore_mcp logger | Tiers |
|------|:---:|:---:|
| default | WARNING | ERROR |
| --verbose | INFO | ERROR |
| --debug | DEBUG | WARNING |
| --debug --debug | DEBUG | DEBUG |

Le niveau actuel `--debug` dans `progress.py`
met déjà `lore_mcp` à DEBUG et les tiers à
WARNING. C'est le bon comportement pour le
premier niveau. Le second niveau (tous en DEBUG)
est à implémenter.

## DoD

1. VRAM logguée avant chaque `_vlm_api_call`
   (debug level)
2. Payload size logguée (debug level)
3. Image dimensions + mode logguées (debug level)
4. Body 507 logguée (error level — toujours
   visible)
5. `--debug` ne montre que les traces lore-mcp
6. `--debug --debug` active le debug de tout
7. Tests existants passent

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
