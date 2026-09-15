# Grooming E12.26 — Sequential model processing

- **Status:** Implémenté
- **Date:** 2026-09-15

## Problem

3.7 GB VRAM — only one model at a time. Current
pipeline loads models on demand without explicit
unloading. Multiple models loaded simultaneously
causes OOM.

## Solution

Reorganize ALL pipelines into model-sequential
phases. Each phase uses one model.

### Preprocess phases

```
Phase 1: Parse (Docling local, OCR CPU/GPU)
  → all sources parsed to markdown
  → images embedded as base64 (ImageRefMode.EMBEDDED)
  → unload Docling

Phase 2: Captioning VLM (Molmo/Granite Vision)
  → start IS (E12.25)
  → for standalone images: if classify_parse_result = empty
  → for inline images: extract base64 from ![](data:...),
    send to VLM, replace alt text
  → stop IS

Phase 3: Clean + Enrich LLM (granite)
  → start IS if local
  → clean_text (NFC, HTML strip, base64→alt text)
  → enrich (context, qa, meta) per section
  → stop IS

Phase 4: Dedup + Validate + Write
  → no model needed
  → dedup, PII, quality gate, manifest
```

### Optimize phases

```
For each embedding model:
  → start IS
  → index all chunk param combinations
  → eval
  → Embedder.unload()
  → stop IS

For each reranking model:
  → test on winning chunking
  → unload
```

### Implementation

Refactor `preprocess_sources()` from
source-by-source to phase-by-phase:

1. Pass 1: parse ALL sources → store results
2. Pass 2: caption ALL empty images → update
3. Pass 3: clean + enrich ALL sources
4. Pass 4: dedup + validate + write

The current source-by-source loop becomes
multiple phase loops over the same data.

## DoD

1. Pipeline by phases in preprocess
2. Explicit unload between phases
3. Compatible with E12.25 (start/stop IS)
4. Progress shows current phase
5. Same final result (files identical)
6. Optimize also model-sequential

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
