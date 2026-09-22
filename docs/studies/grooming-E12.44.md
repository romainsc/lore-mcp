# Grooming E12.44 — Configurable timeout per model

- **Status:** Implémenté
- **Date:** 2026-09-22

## Problem

`PictureDescriptionApiOptions` uses a fixed 180s
timeout. Molmo CPU inference takes 300-600s per
PPTX image (49 images). granite-vision CPU also
exceeds 180s on large images.

## Solution

Add `timeout` field to LLM registry entries.
Read by `caption_with_docling()` and passed to
`PictureDescriptionApiOptions.timeout`.

```yaml
llm:
  - name: granite-vision
    timeout: 600       # CPU mode, large images
  - name: molmo-7b
    timeout: 600       # CPU, 7B model
```

Default: 180s (Docling default).

## Implementation

- `preprocess/__init__.py`: read `cap_entry.get("timeout", 180)`,
  pass to `caption_with_docling(timeout=...)`
- `parse.py`: `caption_with_docling()` already accepts `timeout` param
- Config: no schema change needed — `timeout` is a dict field
  in the LLM registry, read directly
- Docs: `design-config-registry.md`, `design-preprocess-pipeline.md`

## DoD

1. `timeout` field read from LLM registry entry
2. Passed to `PictureDescriptionApiOptions`
3. Default 180s (backward compatible)
4. Tests pass
5. Documentation updated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
