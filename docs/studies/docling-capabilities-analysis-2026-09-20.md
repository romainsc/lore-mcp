# Docling capabilities analysis — what lore-mcp reimplements

- **Date:** 2026-09-20
- **Docling version:** 2.127.0
- **Purpose:** Identify what Docling does natively that
  lore-mcp reimplements, and what lore-mcp adds

## 1. Docling native capabilities (exhaustive)

### Parsing & conversion

| Feature | CLI flag | API class |
|---------|----------|-----------|
| PDF parsing | default | `PdfPipelineOptions` (layout + OCR + tables) |
| DOCX/PPTX/XLSX | default | `DocumentConverter` backends |
| HTML/EPUB | default | `HTMLBackend` |
| VLM page conversion | `--pipeline vlm` | `VlmPipelineOptions` |
| Output formats | `--to md\|json\|yaml\|html\|text\|doctags` | `export_to_markdown()` etc. |
| Image export | `--image-export-mode` | `ImageRefMode.EMBEDDED\|REFERENCED\|PLACEHOLDER` |

### OCR

| Feature | CLI flag | API |
|---------|----------|-----|
| Multi-engine | `--ocr-engine` | `OcrAutoOptions`, `RapidOcrOptions`, `EasyOcrOptions`, `TesseractOcrOptions`, etc. |
| Language | `--ocr-lang` | `ocr_options.lang` |
| Force OCR | `--force-ocr` | `force_backend_text` |
| OCR mode | — | `OcrMode.FULL_PAGE\|LAYOUT_REGIONS\|PDF_AWARE` |

### Enrichments (all opt-in, default off)

| Feature | CLI flag | API | Default model |
|---------|----------|-----|---------------|
| Picture classification | `--enrich-picture-classes` | `do_picture_classification` | DocumentFigureClassifier-v2.5 (26 classes) |
| Picture description | `--enrich-picture-description` | `do_picture_description` | SmolVLM-256M |
| Chart extraction | `--enrich-chart-extraction` | `do_chart_extraction` | granite-vision |
| Code enrichment | `--enrich-code` | `do_code_enrichment` | VLM-based |
| Formula enrichment | `--enrich-formula` | `do_formula_enrichment` | VLM-based LaTeX |

### Picture description backends

| Backend | Class | Use case |
|---------|-------|----------|
| Remote API | `PictureDescriptionApiOptions` | OpenAI-compat endpoint (vLLM, Ollama) |
| Local transformers | `PictureDescriptionVlmOptions` | HuggingFace model in-process |
| Preset-based | `PictureDescriptionVlmEngineOptions` | `from_preset("smolvlm"\|"granite_vision"\|"pixtral"\|"qwen")` |

`PictureDescriptionApiOptions` key params:
- `url` — API endpoint (default localhost:8000)
- `prompt` — customizable description prompt
- `timeout` — per-request (default 20s)
- `concurrency` — parallel API requests
- `batch_size` — images per batch
- `picture_area_threshold` — skip small images
- `classification_allow/deny` — filter by class
- `headers` — auth headers (Bearer token)
- Requires `enable_remote_services=True`
- Requires `generate_picture_images=True`

### VLM pipeline presets (page conversion)

19 presets: smoldocling, granite_docling,
deepseek_ocr, granite_vision, pixtral, got_ocr,
phi4, qwen, nanonets_ocr2, gemma_12b, gemma_27b,
dolphin, glm_ocr, lightonocr, falcon_ocr,
chandra_ocr2, unlimited_ocr, dots_ocr, dots_mocr

### Infrastructure

- `--device auto|cpu|cuda|mps|xpu`
- `--enable-remote-services` for API calls
- `--document-timeout` per document
- `--page-batch-size` for parallelism
- `--profiling` for performance analysis

## 2. What lore-mcp reimplements unnecessarily

| lore-mcp feature | Code | Docling equivalent | Migrate? |
|------------------|------|-------------------|:--------:|
| Image captioning (inline) | `caption_inline_images()` ~150 lines | `do_picture_description` + `PictureDescriptionApiOptions` → granite-vision IS | **YES** |
| Image classification | `_build_classify_prompt()` VLM call per image | `do_picture_classification` trained classifier | **YES** (verify quality) |
| Image skip by size | `_MIN_IMAGE_SIZE_B64` heuristic | `picture_area_threshold` fraction of page | **YES** |
| VLM API call | `_vlm_api_call()` ~50 lines | `PictureDescriptionApiOptions` handles API, retry, concurrency | **YES** |
| Standalone image caption | `caption_image()` ~60 lines | Standard pipeline + `do_picture_description` | **YES** |
| Image dedup | `_b64_hash()` | Not in Docling | Keep |
| Circuit breaker | consecutive failure count | Not in Docling | Keep |

Migrating to Docling native replaces ~300 lines
of custom captioning code with ~10 lines of
Docling configuration.

## 3. What lore-mcp adds (Docling cannot do)

| Feature | Why needed |
|---------|-----------|
| Multi-model captioning (E12.28) | All models run on same images. Docling = one model per run. |
| Judge LLM selection | Best caption among models. No equivalent. |
| OCR-first captioning | OCR text enriches VLM prompt. Docling doesn't inject OCR into caption prompt. |
| LLM OCR correction (E12.38) | `correct_ocr()` sends to LLM. Docling has no post-OCR correction. |
| LLM enrichment (context, Q&A, meta) | Contextual retrieval, Q&A generation. Beyond Docling scope. |
| Column reorder (E12.23) | Bbox clustering. Docling's reading order fails on complex layouts. |
| Progressive output (E12.27) | Phase-suffixed files. Docling outputs once. |
| IS lifecycle (E12.25) | Start/stop containers. Docling assumes models available. |
| VRAM management (E12.31, E12.34) | Subprocess isolation. Docling manages own VRAM. |
| Keep-intermediates | Diagnostic artifacts. Not in Docling. |
| VLM meta-commentary cleanup | Regex post-process. Not in Docling. |
| Manifest-driven pipeline | Source resolution, enriched manifest. Beyond Docling. |
| Dedup, PII, quality gate | Pipeline orchestration. Not in Docling. |

## 4. Recommended architecture

### Phase 1: Parse — delegate more to Docling

Configure `PdfPipelineOptions` with:
```python
opts = PdfPipelineOptions()
opts.do_picture_classification = True
opts.do_picture_description = True
opts.enable_remote_services = True
opts.picture_description_options = PictureDescriptionApiOptions(
    url="http://127.0.0.1:8092/v1/chat/completions",
    params={"model": "granite-vision"},
    prompt="Describe this image...",
    timeout=180,
)
```

This handles: image classification, image
captioning via remote VLM, area filtering.
Removes: `caption_inline_images()`,
`_vlm_api_call()`, `_build_classify_prompt()`,
`_ocr_from_b64()` for classification.

### Phase 2: Caption — multi-model only

If ONE model: use Docling native (phase 1).
If MULTIPLE models: phase 2 runs additional
models + judge. The primary model (granite-vision)
is already done by Docling in phase 1.

### Phase 3: Clean + Enrich — keep (beyond Docling)

LLM enrichment, OCR correction, dedup, PII.

### Phase 4: Validate + Write — keep

Quality gate, manifest, report.

## 5. Impact on existing items

| Item | Impact |
|------|--------|
| E12.28 (multi-model) | Simplify: primary model via Docling, phase 2 only for additional models |
| E12.30 (Docling integration) | This IS the migration item. Major simplification ~300 lines removed. |
| E12.41 (prompt quality) | Resolved by Docling's `PictureDescriptionApiOptions.prompt` |
| E12.23 (column reorder) | Keep — Docling's reading order still fails on complex layouts |
| E12.27 (progressive output) | Keep — Docling doesn't do phase files |
| E12.25 (IS lifecycle) | Keep — Docling doesn't manage containers |

## Sources

- [Docling remote VLM example](https://docling-project.github.io/docling/examples/pictures_description_api/)
- [Docling enrichments docs](https://docling-project.github.io/docling/usage/enrichments/)
- [API-Based VLM Models — DeepWiki](https://deepwiki.com/docling-project/docling/4.3.2-api-based-vlm-models)
- [Picture annotation with Docling — DEV](https://dev.to/aairom/picture-annotation-with-docling-eo1)
- [Docling vs Unstructured](https://markaicode.com/vs/docling-vs-unstructured/)
- [Docling RAG — The New Stack](https://thenewstack.io/from-unstructured-data-to-rag-ready-with-docling/)
- [RAG frameworks comparison — ThinkDeeply](https://www.thinkdeeply.ai/post/a-comparative-analysis-of-data-pre-processing-frameworks-for-retrieval-augmented-generation-chonkie)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
