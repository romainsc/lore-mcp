# Grooming E12.45 — Standalone photo/infographic fallback

- **Status:** Prêt
- **Date:** 2026-09-22

## Problem

Docling is a document parser, not a photo viewer.
On a standalone photo (e.g. pexels .jpg), Docling
produces a JSON with 0 pictures, 0 texts → empty
output. `PictureDescriptionApiModel` has nothing
to caption.

## Solution

After phase 1, detect empty Docling output on
standalone images. Fall back to direct VLM API
call with the image as base64.

```
Phase 1 parse → Docling JSON empty?
  → yes + source is IMAGE_EXTENSIONS?
    → direct VLM captioning (base64 + prompt)
    → result = markdown description
  → no → normal pipeline (Docling caption)
```

### Detection criteria

All three must be true:
1. `docling_json` path exists on disk
2. Docling document has 0 pictures AND 0 texts
3. Source file extension in `IMAGE_EXTENSIONS`

### Implementation

New function in `parse.py`:

```python
def caption_standalone_image(
    image_path: str, api_url: str, model_name: str,
    prompt: str = "", timeout: int = 180,
) -> str:
```

Sends image as base64 to `/v1/chat/completions`
(OpenAI-compatible vision API). Returns markdown
with the description.

Called from `preprocess_sources()` in `__init__.py`
between phase 1 report reading and phase 2
captioning loop. If triggered, the result replaces
the phase 1 text (which is empty) and skips the
Docling captioning path for this source.

### Prompt

Same as `caption_with_docling` default:
"Describe this image in detail: subject, scene,
visible objects, text, and any information it
conveys."

## DoD

1. Pexels photo produces non-empty description
2. Normal pipeline unchanged for other formats
3. Fallback only on empty Docling + IMAGE_EXTENSIONS
4. timeout from LLM registry (E12.44)
5. Unit tests (mock VLM API response)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
