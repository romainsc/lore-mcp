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
  → OCR (always, once)
  → Docling classifier (26 classes, once)
  → Model 1 (granite-docling) → result_1
  → Model 2 (granite-vision) → result_2
  → Model 3 (molmo) → result_3
  → Decision (configurable, E12.29) → final
```

No hardcoded routing: lore-mcp does not decide
which model handles which image type. All models
process all images.

### Phase 2 detail

For each image in a parsed document:
1. **OCR** (RapidOCR) — run once, cache result
2. **Existing alt text** — if the image has a
   real alt text (not "Image"/"Figure"
   placeholder), use it to enrich the caption
   prompt. Do NOT skip captioning. The alt text
   is context, not a replacement.
3. **For each caption model** (sequentially):
   a. Start IS (if start command configured)
   b. Health check (inference probe)
   c. Send image + prompt to model. The prompt
      includes: OCR text, alt text (if any),
      source context, description
   d. Receive caption, post-process (clean meta-
      commentary)
   e. Write result to per-image cache
   f. Write progressive phase2-caption-{name}.md
   g. Stop IS (if stop command configured)

Each model handles classification internally
via its own prompt. Docling's 26-class classifier
was tested and found unusable on PPTX images
(0/5 correct: BD→topographical_map, logo→
qr_code, slide→table, timeline→box_plot,
screenshot→crossword_puzzle). See benchmark
2026-09-18.

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

  # E12.29: selection strategy
  caption_selection: judge
  # Options: first_nonempty, longest,
  #          classification_based, fusion, judge
  caption_judge: granite-8b  # LLM from llm registry
```

### Per-model intermediate files

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

### E12.29 — Caption selection (MVP = judge)

Configurable via `caption_selection` in config.

Five strategies:
1. `first_nonempty` — first model (by config
   order) that produced non-empty output
2. `longest` — the richest non-empty result
3. `classification_based` — use Docling class to
   prefer certain models (e.g. screenshot →
   granite-docling, photograph → VLM)
4. `fusion` — combine results (OCR text +
   structured extraction + visual description)
5. `judge` — send all results to a judge LLM
   which selects or synthesizes the best caption

**MVP implements strategy 5 (judge)** using the
LLM configured in `caption_judge` (references
a model from the llm registry). The judge
receives: OCR text, alt text (if any), and all
N model captions. It produces the final unified
caption.

The other strategies are declared but not
implemented in this MVP. They can be added
incrementally.

### Available IS (user infrastructure)

| IS | Port | Model | Device | Latency |
|----|------|-------|--------|---------|
| start-docling-server.sh | 8091 | granite-docling-258M | GPU | ~15s |
| start-granite-vision-server.sh | 8092 | Granite Vision 4.1 4B NF4 | GPU | ~6s |
| start-molmo2-server.sh | 8090 | Molmo2-O 7B FP32 | CPU | ~100-490s |

## DoD

1. Config accepts list of caption models in
   parse.caption_models
2. All models run sequentially on all images
3. One phase2-caption-{name}.md per model
4. OCR cached (run once for all models)
5. Existing alt text used as context (not skip)
6. IS lifecycle per model (start/stop/health)
7. caption_selection configurable in config
8. caption_judge references LLM from registry
9. Judge strategy implemented as MVP
10. Progressive write per image per model
11. Tests for multi-model execution + judge
12. Existing single-model tests still pass

## Implementation order

MVP1: Part A — multi-model config + sequential
  execution + per-model phase files
MVP2: Part B — alt text as context (not skip)
MVP3: Part C — judge selection (E12.29 MVP)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
