# Study E12.80: Exhaustive Docling Usage Analysis

Analysis of lore-mcp's Docling integration based on
Codebase-Memory graph analysis of both docling-upstream
(19887 nodes) and pillow-upstream (7575 nodes).

## 1. Parsing — Pipeline Options

### Current usage

`parse.py:1054-1094` (`_create_docling_converter`):
- Only sets `ocr_options` (Tesseract lang/scale)
- Only configures `InputFormat.IMAGE` and
  `InputFormat.PDF` format options
- PPTX/DOCX/XLSX use default `DocumentConverter()`
  with no custom options

### Docling capabilities not leveraged

**a) `heading_hierarchy_options` (HIGH)**

`PdfPipelineOptions.heading_hierarchy_options`:
disabled by default. When enabled, Docling infers
section-header levels from PDF bookmarks, numbering
and font style. Without this, ALL PDF headings are
level 1 — destroying the heading hierarchy that is
critical for RAG chunking quality.

```python
opts.heading_hierarchy_options = HeadingHierarchyOptions(
    enabled=True,
    use_bookmarks=True,
    use_numbering=True,
    use_style=True,  # requires generate_parsed_pages=True
)
```

**Impact**: directly affects `MarkdownTextSplitter`
behavior in `ingest.py` — headings are the primary
split signal. Flat headings = poor chunk boundaries.

**Priority**: HIGH — directly impacts RAG quality
for PDF sources.

**b) `document_timeout` (MEDIUM)**

`PipelineOptions.document_timeout`: not set. Docling
can process indefinitely on complex documents. When
set (e.g. 120s), returns PARTIAL_SUCCESS with partial
results rather than hanging.

**Impact**: prevents the pipeline from blocking
indefinitely on a single document. Partial results
are better than no results.

**Priority**: MEDIUM — resilience improvement.

**c) `images_scale` for PDF (LOW)**

`PdfPipelineOptions.images_scale`: defaults to 1.0.
Higher values (2.0) produce better quality images
for VLM captioning but increase processing time.

Currently, OCR `scale=4.0` is set for Tesseract, but
`images_scale` for picture extraction is at default
1.0. VLM receives lower-resolution images than OCR.

**Priority**: LOW — minor quality improvement,
increases processing time.

**d) `do_code_enrichment` (LOW)**

`PdfPipelineOptions.do_code_enrichment`: disabled by
default. For technical documentation with code blocks,
this could improve code extraction accuracy.

**Priority**: LOW — only relevant for code-heavy PDFs.

## 2. Image Handling

### Current usage

`parse.py:188` (`caption_with_docling`):
- Accesses `pic.image.pil_image` directly
- NEW (E12.80 MVP1): converts P mode to RGBA

### Not leveraged

**a) `PictureDescriptionBaseOptions.batch_size` (MEDIUM)**

Default: 8. We process images ONE AT A TIME (line
216-229 loop). Docling's base model supports batch
processing when called via `caption_model(doc,
element_batch)` — but we call it per-image for
checkpoint granularity.

Trade-off: batching improves throughput (especially
with API concurrency) but breaks per-image checkpoint.
Could batch checkpointed groups.

**Priority**: MEDIUM — significant performance gain
for sources with many images.

**b) `PictureDescriptionApiOptions.concurrency` (MEDIUM)**

Default: 1. Docling supports concurrent API requests
for captioning. Setting `concurrency=2-4` with API-
based VLM could parallelize captioning.

**Priority**: MEDIUM — 2-4x speedup for captioning
phase, but requires VLM server to handle concurrency.

**c) `PictureDescriptionBaseOptions.scale` (LOW)**

Default: 2.0. Controls image resolution sent to VLM.
We don't set it, using the default. Could be tuned
per source type.

**d) `picture_area_threshold` (LOW)**

Default: 0.05 (5% of page area). Skips tiny images.
We don't set it. Could filter decorative elements.

**e) `classification_deny` (LOW)**

Could deny decorative image types (logos, decorations)
to skip VLM captioning on non-informative images.
We already do OCR-based filtering in phase 1.7
(E12.71) but Docling's classification is more
sophisticated.

## 3. Export

### Current usage

`parse.py:1156`:
```python
doc.export_to_markdown(image_mode=ImageRefMode.EMBEDDED)
```

Only sets `image_mode`. All other parameters use
defaults.

### Not leveraged

**a) `strict_text` (LOW)**

When `True`, strips all formatting markers. Could be
useful for producing cleaner text for embedding.

**b) `labels` filter (MEDIUM)**

Can filter export by item type (headings, text,
tables, pictures). Could be used to export different
views for different purposes (text-only for embedding,
full for user display).

**c) `compact_tables` (LOW)**

Produces more compact table markdown. Could reduce
chunk sizes for table-heavy documents.

**d) `traverse_pictures` (MEDIUM)**

When `True`, exports picture sub-elements (nested
content inside pictures). Currently disabled — we
may be losing structured content inside complex
figures.

**e) `included_content_layers` (MEDIUM)**

Default: `{ContentLayer.BODY}`. By default, page
headers/footers (`FURNITURE`) are excluded. This is
correct for RAG. But we should verify we're not
accidentally including furniture content.

## 4. Serialization (JSON Round-trip)

### Current usage

`parse.py:1154`: `doc.save_as_json(docling_json_path)`
`parse.py:176`: `DoclingDocument.load_from_json(path)`

### Verified

Images survive the JSON round-trip (confirmed in
E12.42 grooming). The `pil_image` property
deserializes from embedded base64 in the JSON.

### Risk

**a) JSON file size (LOW)**

PPTX with 49 images produces a 362 KB JSON. PDFs
with high-resolution images could produce much larger
files. No compression option exists.

## 5. Performance

### Current usage

`parse.py:1145-1147`: Global `_docling_converter`
reused across calls. Created once, reused for all
sources in a single phase 1 run. This is correct.

### Issues

**a) Converter re-creation across runs (LOW)**

After `unload_docling()`, the converter is set to
None. Next call recreates it (loading layout model
to GPU ~2s). This is by design for VRAM management
(E12.26).

**b) No batch conversion (MEDIUM)**

`DocumentConverter.convert()` processes one document
at a time. Docling supports `convert_all()` for batch
processing with better throughput. Currently we call
`convert()` in a loop in `_phase1_worker`.

```python
# Current (parse.py:1149):
doc = _docling_converter.convert(str(path)).document

# Could use:
results = _docling_converter.convert_all(paths)
for result in results:
    doc = result.document
```

**Priority**: MEDIUM — could improve phase 1 throughput
for many small documents.

## 6. Error Handling

### Current usage

`parse.py:1149`:
```python
doc = _docling_converter.convert(str(path)).document
```

We extract `.document` and DISCARD the full
`ConversionResult` — including:
- `status` (SUCCESS/PARTIAL_SUCCESS/FAILURE)
- `errors` (list of ErrorItem with category, message)
- `timings` (per-stage profiling data)
- `confidence` (ConfidenceReport)

### Not leveraged

**a) `ConversionResult.status` (HIGH)**

Docling can return PARTIAL_SUCCESS when some pages
failed but others succeeded. We don't check this —
we'd use partial content without knowing it's
incomplete.

**Priority**: HIGH — correctness issue. We should
check status and log warnings for partial results.

**b) `ConversionResult.errors` (HIGH)**

Detailed error items with category (TIMEOUT,
INFERENCE_FAILURE, etc.) and page-level granularity.
We lose all of this by extracting `.document` only.

**Priority**: HIGH — observability. Should surface
errors in the preprocess report.

**c) `ConversionResult.timings` (LOW)**

Per-stage timing data. Could be used for performance
monitoring and optimization.

**d) `ConversionResult.confidence` (MEDIUM)**

Document-level confidence scores. Could inform quality
gating — low-confidence documents might need manual
review or different processing.

## 7. Docling Native Chunking

### Current usage

lore-mcp uses `langchain-text-splitters`
`MarkdownTextSplitter` for chunking (`ingest.py:8,75`).
This operates on exported markdown text, losing the
structured document model.

### Docling capability

Docling provides `HybridChunker` and
`HierarchicalChunker` (in docling-core) that operate
directly on `DoclingDocument` — preserving document
structure, table boundaries, heading hierarchy, and
metadata.

```python
from docling_core.transforms.chunker import HybridChunker
chunker = HybridChunker(
    tokenizer="sentence-transformers/all-MiniLM-L6-v2",
    max_tokens=1024,
    merge_peers=True,
)
chunks = list(chunker.chunk(doc))
```

**Key advantage**: chunks carry structured metadata
(headings, page numbers, table context) that our
current text-based chunking loses.

**Priority**: HIGH for evaluation — should be
benchmarked against MarkdownTextSplitter. Could
replace or complement our chunking pipeline.
Not necessarily a replacement — MarkdownTextSplitter
is proven and simple. Benchmark needed.

## 8. New Capabilities Not Used

**a) ASR Pipeline (MEDIUM)**

Docling has native ASR (audio speech recognition)
via `AsrPipelineOptions` with Whisper support. We
implemented our own STT pipeline (E12.48). Could
evaluate Docling's native ASR as an alternative.

**b) VLM Streaming (LOW)**

Docling supports VLM streaming responses for
captioning. We don't use it — not needed for our
batch pipeline.

**c) Service Client (LOW)**

Docling provides `DoclingService` / `AsyncDoclingService`
for remote document conversion. Not relevant for our
local-first architecture.

## 9. Deprecation Check

No deprecated APIs detected in our usage. The imports
we use are current:
- `PictureDescriptionApiModel` (current path)
- `PictureDescriptionApiOptions` (current)
- `ImageRefMode.EMBEDDED` (current)
- `FormatOption`, `InputFormat` (current)

Note: `PictureDescriptionVlmOptions` is marked as
"legacy" in Docling docs, but we use the API variant.

## Summary — Prioritized Recommendations

| # | Area | Issue | Priority | Effort |
|---|------|-------|----------|--------|
| 1 | Parse | Enable `heading_hierarchy_options` for PDFs | HIGH | Low |
| 2 | Error | Capture `ConversionResult` status/errors | HIGH | Medium |
| 3 | Chunk | Benchmark Docling `HybridChunker` vs MarkdownTextSplitter | HIGH | Medium |
| 4 | Caption | Use `concurrency` for parallel VLM captioning | MEDIUM | Low |
| 5 | Parse | Set `document_timeout` for resilience | MEDIUM | Low |
| 6 | Export | Evaluate `traverse_pictures` for complex figures | MEDIUM | Low |
| 7 | Perf | Use `convert_all()` for batch document processing | MEDIUM | Medium |
| 8 | Export | Test `labels` filter for embedding-optimized export | MEDIUM | Low |
| 9 | Caption | Evaluate `batch_size` > 1 with checkpoint groups | MEDIUM | Medium |
| 10 | Confidence | Surface `ConversionResult.confidence` in report | MEDIUM | Low |
| 11 | ASR | Compare Docling native ASR vs our STT pipeline | MEDIUM | High |
| 12 | Parse | Tune `images_scale` for VLM captioning quality | LOW | Low |
| 13 | Export | Test `compact_tables` for table-heavy docs | LOW | Low |
