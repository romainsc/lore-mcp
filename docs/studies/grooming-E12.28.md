# Grooming E12.28 — Multi-model image captioning

- **Status:** Prêt
- **Date:** 2026-09-18

## Problem

No single model covers all image types. The
pipeline must support multiple captioning models
and produce comparable results. The selection/
fusion logic must be configurable, not hardcoded.

## Solution

### Principle: run all, decide after

For each image, ALL configured caption models
run sequentially. Each produces its own result.
A configurable decision step selects or fuses.

```
Image
  → OCR (always)
  → Docling classifier (26 classes, metadata)
  → Model 1 (granite-docling) → result_1
  → Model 2 (granite-vision) → result_2
  → Model 3 (molmo) → result_3
  → Decision (configurable) → final caption
```

No hardcoded routing: lore-mcp does not decide
which model handles which image type. All models
process all images. The decision step (E12.29)
uses the results + classification metadata.

### Config

```yaml
parse:
  caption_models:
    - name: granite-docling
      model: ibm-granite/granite-docling-258M
      api_url: http://127.0.0.1:8091/v1
      start: ./scripts/start-docling-server.sh
      stop: podman stop docling-server

    - name: granite-vision
      model: ibm-granite/granite-3.2-4b-vision
      api_url: http://127.0.0.1:8092/v1
      start: ./scripts/start-granite-vision-server.sh
      stop: podman stop granite-vision-server

    - name: molmo-7b
      model: allenai/Molmo2-O-7B
      api_url: http://127.0.0.1:8090/v1
      start: ./scripts/start-molmo2-server.sh
      stop: podman stop molmo2-server
```

### Implementation

#### Part A — Multi-model config

`parse.caption_models` is a list of models in
the LLM registry. Each has name, api_url,
start/stop. The pipeline iterates them
sequentially (E12.26 model-by-model).

#### Part B — Per-model intermediate files

Each model produces its own phase file:
```
prep/
  doc.phase1-parse.md
  doc.phase2-caption-granite-docling.md
  doc.phase2-caption-granite-vision.md
  doc.phase2-caption-molmo-7b.md
  doc.phase3-enrich.md
  doc.md  (final)
```

This provides:
- Observability (compare models per image)
- Resumability (skip models already done)
- Debugging (which model produced what)

#### Part C — Per-model execution

For each caption model in config:
1. Start IS (if start command)
2. Health check (inference probe)
3. For each image: OCR + classify + caption
4. Write phase2-caption-{model-name}.md
5. Stop IS (if stop command)

Models run one at a time (VRAM constraint).
OCR runs once, results cached.
Docling classification runs once, results cached.

#### Part D — Classification metadata

Docling's 26-class classifier produces metadata
attached to each image (class + confidence). This
metadata is available to all models and to the
decision step (E12.29). Not used for routing.

### Separate item: E12.29 — Caption selection

Configurable rules for selecting/fusing results
from multiple models. Examples:
- Take longest non-empty result
- Prefer granite-docling if classification is
  screenshot/table
- Fuse: granite-docling text + VLM visual
- LLM judge: send all results to LLM, pick best

This is a separate item because the rules need
experimentation and may vary per corpus.

Default (no config): take the result from the
first model that produced non-empty output.

### Available IS (user infrastructure)

| IS | Port | Model | Device | Latency |
|----|------|-------|--------|---------|
| start-docling-server.sh | 8091 | granite-docling-258M | GPU | ~15s |
| start-granite-vision-server.sh | 8092 | Granite Vision 4.1 4B NF4 | GPU | ~6s |
| start-molmo2-server.sh | 8090 | Molmo2-O 7B FP32 | CPU | ~100-490s |

## DoD

1. Config accepts list of caption models
2. All models run sequentially on all images
3. One phase2-caption-{name}.md per model
4. OCR and classification cached (run once)
5. IS lifecycle per model (start/stop)
6. Default decision: first non-empty result
7. Tests for multi-model execution
8. Existing single-model tests still pass

## Implementation order

MVP1: Part A+C (multi-model config + execution)
MVP2: Part B (per-model intermediate files)
MVP3: Part D (classification metadata)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
