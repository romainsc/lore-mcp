# Docling capabilities analysis — what lore-mcp reimplements

- **Date:** 2026-09-20
- **Docling version:** 2.127.0

## 1. What Docling does natively (exhaustive)

### Parsing pipelines

| Pipeline | Usage | Models |
|----------|-------|--------|
| `standard` (default) | PDF/DOCX/PPTX/XLSX/IMAGE via layout detection + OCR + table structure | Layout (Heron/Egret), TableFormer, OCR engine |
| `vlm` | End-to-end VLM document understanding from page images | 19 presets: granite_docling, granite_vision, smoldocling, deepseek_ocr, pixtral, got_ocr, phi4, qwen, nanonets_ocr2, gemma_12b/27b, dolphin, glm_ocr, lightonocr, falcon_ocr, chandra_ocr2, unlimited_ocr, dots_ocr, dots_mocr |
| `asr` | Audio/speech recognition | Whisper variants |

### OCR engines

7 engines: `auto` (selects best available),
`easyocr`, `rapidocr`, `tesserocr`, `tesseract`,
`kserve_v2_ocr`, `nemotron-ocr`, `ocrmac`.

Language support via BCP-47 tags (`iso:fr`,
`iso:de`, etc.). RapidOCR supports French via
`iso:fr-Latn`.

### Enrichment models

| Enrichment | CLI flag | Purpose | Default model |
|------------|----------|---------|---------------|
| Picture classification | `--enrich-picture-classes` | Categorize images (26 types) | DocumentFigureClassifier-v2.5 |
| Picture description | `--enrich-picture-description` | VLM captioning of images | SmolVLM-256M (inline) or API |
| Chart extraction | `--enrich-chart-extraction` | Extract chart data to tables | granite-vision-3.3-2b-chart2csv |
| Code enrichment | `--enrich-code` | Code block language detection | CodeFormula model |
| Formula enrichment | `--enrich-formula` | Math formulas → LaTeX | CodeFormula model |

### Picture description options

Three backends:
1. `PictureDescriptionVlmEngineOptions` — inline
   model with presets (smolvlm, granite_vision,
   pixtral, qwen). Loads in-process.
2. `PictureDescriptionApiOptions` — OpenAI-
   compatible API endpoint. Configurable URL,
   headers, prompt, timeout, concurrency.
   Requires `enable_remote_services=True`.
3. `PictureDescriptionVlmOptions` — legacy
   HuggingFace Transformers direct loading.

`PictureDescriptionApiOptions` fields:
- `url` — API endpoint (default localhost:8000)
- `params` — model name, seed, max_tokens
- `prompt` — captioning prompt
- `timeout` — default 20s (too low for CPU)
- `concurrency` — concurrent requests (default 1)
- `batch_size` — images per batch (default 8)
- `picture_area_threshold` — skip small images
  (default 0.05 = 5% of page area)
- `classification_allow/deny` — filter by type
- `classification_min_confidence` — threshold

### VLM pipeline (--pipeline vlm)

Replaces the entire standard pipeline (layout
+ OCR + table structure) with a single VLM
forward pass. 19 model presets available.

Key option: `force_backend_text=True` — hybrid
mode that uses PDF native text for text regions
and VLM for images/tables.

Can use API endpoints via `ApiVlmOptions`:
- `url` — OpenAI chat/completions endpoint
- `timeout` — default 60s
- `concurrency` — concurrent requests
- `response_format` — doctags, markdown, html,
  plaintext

### Other capabilities

- `--image-export-mode embedded|referenced|
  placeholder`
- `--table-mode fast|accurate` (TableFormer)
- `--device auto|cpu|cuda|mps|xpu`
- `--force-ocr` — override PDF text with OCR
- `--document-timeout` — per-document timeout
- `--page-batch-size` — pages per batch
- `--profiling` — performance metrics
- HybridChunker — semantic chunking with
  metadata preservation
- Multiple output formats: md, json, yaml,
  html, text, doctags

## 2. What lore-mcp reimplements unnecessarily

| Feature | lore-mcp code | Docling native | Notes |
|---------|--------------|----------------|-------|
| **Image captioning** | `caption_image()`, `caption_inline_images()` (~300 lines in parse.py) | `do_picture_description=True` + `PictureDescriptionApiOptions` | Docling can point to our granite-vision server via API. Handles batching, area filtering, classification-based allow/deny natively |
| **Image type classification** | `_build_classify_prompt()` + VLM classify call (2 VLM calls per image) | `do_picture_classification=True` | Docling uses a trained classifier (faster, no VLM call needed). Tested 0/5 on our PPTX — but Docling v2.5 classifier may have improved |
| **Skip small images** | `_MIN_IMAGE_SIZE_B64 = 13000` heuristic | `picture_area_threshold=0.05` | Docling uses page area fraction (more robust) |
| **Image resize for VLM** | Removed (design: no resize) | `scale=2.0` on picture description | Docling handles scaling internally |
| **OCR language** | Not configured | `ocr_options=RapidOcrOptions(lang=['iso:fr'])` | We don't set French OCR — may improve quality |
| **Chart extraction** | Not implemented | `do_chart_extraction=True` | Extracts bar/pie/line chart data to tables |

### Estimated code savings

If lore-mcp delegates image captioning to
Docling's `PictureDescriptionApiOptions`:
- Remove ~300 lines (caption_image,
  caption_inline_images, _vlm_api_call,
  _build_classify_prompt, _CAPTION_PROMPTS,
  _clean_vlm_output, _ocr_from_b64,
  _b64_hash, circuit breaker, dedup)
- Remove multi-model caption loop in
  __init__.py (~100 lines)
- Remove judge_captions (~50 lines)
- Total: ~450 lines of custom captioning code

Docling handles captioning during parse
(phase 1), not as a separate phase 2. The
phase 2 captioning loop, progressive output
per model, and IS lifecycle per caption model
all become unnecessary.

## 3. What lore-mcp adds that Docling cannot do

| Feature | lore-mcp | Docling | Keep? |
|---------|---------|---------|-------|
| **Multi-model captioning** | All models run, judge selects | One model per conversion | **Re-evaluate** — Docling can run multiple conversions with different models |
| **Judge LLM selection** | granite-8b selects best caption | No selection mechanism | **Keep** if multi-model needed |
| **OCR-first captioning** | OCR enriches VLM prompt | Not supported — captioning is post-parse | **Keep** as our differentiation |
| **LLM post-OCR correction** | `correct_ocr()` sends to LLM | No post-OCR correction | **Keep** |
| **LLM enrichment** (context, Q&A, meta) | `enrich_context()`, `enrich_qa()`, `enrich_meta()` | Not supported | **Keep** — Docling parses, we enrich |
| **Column reorder** | `_reorder_columns()` bbox clustering | Rule-based reading order (known issues) | **Keep** as workaround |
| **IS lifecycle** | start/stop/health check | Not supported | **Keep** |
| **Progressive output** | Phase-suffixed files | Not supported | **Keep** |
| **Subprocess VRAM isolation** | Phase 1 in subprocess | Not supported | **Keep** |
| **Deduplication** | MinHash LSH | Not supported | **Keep** |
| **PII detection** | Regex patterns | Not supported | **Keep** |
| **Quality gate** | Lint + density check | Not supported | **Keep** |
| **Manifest-driven pipeline** | Manifest YAML input | Not supported (file/URL input only) | **Keep** |

## 4. Recommended architecture

### Current: 4-phase pipeline

```
Phase 1: Docling parse (subprocess)
Phase 2: Multi-model VLM caption (our code)
Phase 3: Clean + Enrich LLM
Phase 4: Validate + Write
```

### Recommended: Delegate captioning to Docling

```
Phase 1: Docling parse + caption (subprocess)
  - Standard pipeline with:
    - do_picture_description=True
    - PictureDescriptionApiOptions(
        url=granite-vision-server)
    - do_picture_classification=True
    - ocr_options=RapidOcrOptions(
        lang=['iso:fr'])
    - ImageRefMode.EMBEDDED
  - Docling captions images inline during parse
  - Column reorder after parse (keep ours)

Phase 2: LLM enrichment (our code)
  - correct_ocr (LLM, OCR sources only)
  - enrich_context, enrich_qa, enrich_meta
  - Source language instruction

Phase 3: Validate + Write
  - Dedup, PII, quality gate, manifest
```

### Key changes

1. **Phase 2 (caption) merges into Phase 1** —
   Docling does captioning during parse via
   `PictureDescriptionApiOptions`. No separate
   caption phase needed.

2. **IS lifecycle simplifies** — only need to
   start granite-vision IS before phase 1 and
   stop after. No per-model sequential start/
   stop during captioning.

3. **Multi-model becomes optional** — if Docling
   + granite-vision captioning is sufficient,
   no need for multi-model + judge. If quality
   comparison is needed, can still run Docling
   twice with different VLM APIs.

4. **OCR-first preserved** — Docling does OCR
   during standard pipeline, and caption prompts
   can be customized. However, Docling's picture
   description prompt does NOT include OCR text
   by default. Our OCR-first approach (injecting
   OCR into caption prompt) is a differentiation
   that requires custom code.

5. **OCR language configured** — set
   `RapidOcrOptions(lang=['iso:fr'])` for better
   French OCR quality.

6. **Chart extraction** — enable
   `do_chart_extraction=True` for free structured
   data from charts.

### What to keep custom

- LLM enrichment (context, Q&A, meta)
- LLM OCR correction (correct_ocr)
- Column reorder (_reorder_columns)
- Manifest-driven pipeline
- Subprocess VRAM isolation
- Dedup, PII, quality gate
- Progressive output
- IS lifecycle (start/stop)

### What to delegate to Docling

- Image captioning (PictureDescriptionApiOptions)
- Image classification (do_picture_classification)
- Skip small images (picture_area_threshold)
- Chart extraction (do_chart_extraction)
- OCR language (RapidOcrOptions with iso:fr)

## 5. Impact on existing items

| Item | Impact |
|------|--------|
| **E12.28** (multi-model caption) | Re-evaluate: Docling can caption via API natively. Multi-model adds complexity. Consider single-model (granite-vision via Docling) as default, multi-model as optional |
| **E12.30** (full Docling integration) | Expanded scope: not just granite-docling VlmPipeline, but also PictureDescriptionApiOptions for captioning, OCR language, chart extraction |
| **E12.23** (column reorder) | Keep — Docling reading order is still rule-based with known issues |
| **E12.38** (LLM OCR correction) | Keep — Docling has no post-OCR correction |
| **E12.41** (caption prompt quality) | May become moot if Docling handles captioning — Docling's prompt is simpler and doesn't have the OCR-context degradation issue |

## 6. Caveat: OCR-first is our differentiation

Docling's `PictureDescriptionApiOptions` sends
the image to the VLM with a fixed prompt
("Describe this image in a few sentences.").
It does NOT inject OCR text into the prompt.

Our OCR-first approach (extract OCR, inject
into VLM prompt, produce unified description)
is unique and research-backed (kapa.ai p<0.05).
If we delegate to Docling, we lose this.

Options:
- Accept Docling's simpler captioning (no OCR
  context) for most images, and add a custom
  post-captioning step for OCR-heavy images
- Customize Docling's prompt to include OCR
  text (not straightforward — Docling controls
  the prompt per-image, not per-document)
- Keep our custom captioning for OCR-heavy
  documents, delegate to Docling for simple
  images

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.

Sources:
- [Docling PictureDescriptionApiOptions example](https://docling-project.github.io/docling/examples/pictures_description_api/)
- [Docling enrichments docs](https://docling-project.github.io/docling/usage/enrichments/)
- [Docling chart extraction blog](https://docling.ai/blog/20260203_00_chart_understanding_in_docling/)
- [VlmPipeline vs Standard discussion](https://github.com/docling-project/docling/discussions/2726)
- [OCR quality comparison 2026](https://slavadubrov.github.io/blog/2026/03/04/ocr-guide/)
- [Docling vs custom pipeline comparison](https://dreaming.press/posts/2026-06-21-docling-vs-unstructured-vs-llamaparse.html)
- [Docling VLM scaling discussion](https://github.com/docling-project/docling/discussions/2821)
