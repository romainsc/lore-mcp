# Design — Preprocessing pipeline

- **Status:** Reference
- **Date:** 2026-09-18
- **Module:** `src/lore_mcp/preprocess/`

## Overview

`lore-mcp preprocess` converts raw sources (PDF,
HTML, DOCX, PPTX, XLSX, images, CSV, JSON, MD)
into clean, enriched markdown ready for
`lore-mcp build`.

**Input:**
- Manifest YAML (source list with metadata)
- Original files in `--orig-dir`
- Optional: `urls.txt` in docs-base-dir

**Output:**
- Preprocessed `.md` files in `--prep-dir`
- Enriched manifest (`-prep` suffix)
- `preprocess-report.json` (machine-readable)

**Invariant:** input files are never modified.

## 4-phase pipeline

```
Phase 1: Parse        (no external model)
Phase 2: Caption      (VLM IS, sequential per model)
Phase 3: Clean+Enrich (LLM IS)
Phase 4: Validate+Write (no model)
```

Entry point: `preprocess_sources()` in
`preprocess/__init__.py`.

### Phase 1 — Parse

For each source in the manifest:

1. `resolve_source_fields()` — cascade
   orig→path→title from manifest entry
2. If orig missing + URL present → `_fetch_url()`
3. `parse_to_markdown(src_path)` — 4-tier cascade:
   - `.md` → passthrough (`_read_text` with
     charset_normalizer encoding detection)
   - `.html` → trafilatura (extract article text)
   - `.pdf/.docx/.pptx/.xlsx/.epub/images` →
     Docling (`DocumentConverter`, cached at
     module level). Images: `ImageRefMode.EMBEDDED`
     (base64 inline). Standalone images:
     `_reorder_columns()` for OCR column fix
   - `.csv/.json/.xml` → markitdown (fallback
     `_convert_text_data` for JSON UnicodeDecodeError)
4. Write `{name}.phase1-parse.md`
5. After all sources: `unload_docling()`

**Models:** Docling internal (layout, OCR via
RapidOCR). No external IS.

**Error handling:** per-source try/except. Errors
reported, pipeline continues.

### Phase 2 — Caption

See `docs/studies/design-captioning-pipeline.md`
for full captioning design (prompts, flow, etc.).

For each configured caption model (sequentially):
1. `start_service(cap_entry)` — start IS, health
   check with VLM inference probe
2. For each source with images:
   - **Standalone** (`.png/.jpg`): `caption_image()`
     with OCR text + alt text as context
   - **Inline** (`data:image/` in markdown):
     `caption_inline_images()` with OCR-first,
     per-image resilience
3. Write `{name}.phase2-caption-{model}.md`
4. `stop_service(cap_entry)` (in finally block)

After all models: judge selection. OCR text from
phase 1 is a candidate alongside VLM captions.

**Models:** configured in `parse.caption_models`.
Each references a model from the LLM registry.

### Phase 3 — Clean + Enrich

For each source:
1. `clean_text()` in order:
   - Strip NUL chars
   - Unicode NFC normalization
   - `_fix_ocr_artifacts()` — `I'` → `l'` regex
   - `_strip_images()` — `![alt](src)` → alt text
   - `_strip_html()` — residual tags + entities
2. If enrich techniques configured:
   - `enrich_context()` — 2-3 sentence context
     paragraph per section (contextual retrieval)
   - `enrich_qa()` — 2-3 Q: per section
   - `enrich_meta()` — summary + keywords per
     section
3. `detect_pii()` — report-only (emails, IPs,
   API keys, internal domains)
4. `extract_source_metadata()` — title, author,
   license, date from front matter
5. Write `{name}.phase3-{enrich|clean}.md`

**Models:** LLM from `enrich.models` via IS
lifecycle (start/stop in finally block).

### Phase 4 — Validate + Write

1. **Dedup** (report-only):
   - `find_exact_duplicates()` — SHA-256 hash
   - `find_near_duplicates()` — MinHash+LSH
     (datasketch, k=5 shingles, 128 perms,
     threshold=0.8)
2. **Quality gate** per file:
   `quality_gate()` → `lint.analyze_file()`.
   Blocks `poor` files unless `--force`.
3. **Write** final `{name}.md` (no phase suffix)
4. **Cleanup** intermediate phase files
5. **Write** enriched manifest (`-prep` suffix)
6. **Write** `preprocess-report.json`

**Models:** none.

## Config keys

| Config path | Controls |
|-------------|----------|
| `parse.caption_models` | List of caption model names from llm registry |
| `parse.caption_selection` | Selection strategy: first_nonempty, longest, judge |
| `parse.caption_judge` | Judge LLM name from registry |
| `enrich.techniques` | List: context, qa, meta |
| `enrich.models` | LLM name(s) from registry |

All model references resolve via
`config.get_llm(name)` to the `llm:` registry.

## File naming

```
prep/
  doc.phase1-parse.md             (after phase 1)
  doc.phase2-caption-modelA.md    (after phase 2, per model)
  doc.phase2-caption-modelB.md
  doc.phase3-enrich.md            (after phase 3)
  doc.md                          (final, phase 4)
```

Phase files persist on crash for debugging.
Cleaned up after successful phase 4 write.
Progressive write via `on_progress` callback
during inline captioning.

## IS lifecycle

Per model, via `service.py`:
- `start_service()`: run `start` command, poll
  `/v1/models`, then VLM inference probe (1×1
  PNG, 120s HTTP timeout). Configurable
  `start_timeout` (default 300s).
- `stop_service()`: run `stop` command. Always
  in finally block.
- Health check probe: sends actual inference
  request to detect model-loaded vs HTTP-only.

## Error handling

- **Per-source:** try/except in phase 1. Error
  → report entry, pipeline continues.
- **Per-image:** try/except in phase 2. Error →
  log warning, skip image, pipeline continues.
- **Inline resilience:** skip <10KB, content-hash
  dedup, circuit breaker (5 consecutive failures).
- **IS failure:** start timeout → TimeoutError
  raised (stops pipeline — IS is a prerequisite).
- **Quality gate:** poor files blocked unless
  `--force`.

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
