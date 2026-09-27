# Grooming E12.80 — All corrections and improvements

Consolidated from E12.80 study + pipeline validation findings.

## Corrections (bugs)

### C1. YouTube URL handling (E12.73 correction)

**Problem**: YouTube URLs (`youtube.com/watch?v=...`) are
fetched as HTML pages via `_fetch_url` instead of being
routed through `download_video` (yt-dlp). Three issues:
1. `_fetch_url` doesn't detect video platform URLs
2. yt-dlp is only wired in STT phase, after parse
3. Name collision: all `/watch` URLs produce `watch.html`

**Fix**:
- In `_phase1_worker`, detect video platform URLs BEFORE
  `_fetch_url`. Use `yt_dlp.YoutubeDL.extract_info(url,
  download=False)` to test. If it works → `download_video`
  path (E12.73). If not → `_fetch_url` (HTTP).
- For naming: use video ID from yt-dlp metadata
  (`info['id']`), not the URL path.

**DoD**:
- YouTube URLs produce video files (not HTML)
- Unique filenames per video (ID-based)
- STT transcription runs on downloaded video
- Frame extraction works on downloaded video
- Test: manifest with 3 YouTube URLs → 3 distinct outputs

**MVP1**: detect + download. **MVP2**: subtitle download
(skip STT if captions available).

---

### C2. ConversionResult discarded (HIGH)

**Problem**: `parse.py:1149` does
`doc = converter.convert(path).document`, discarding
status, errors, timings, confidence. Partial failures
silently treated as success.

**Fix**: capture `ConversionResult`, check `.status`,
log warnings for `PARTIAL_SUCCESS`, surface `.errors`
in preprocess report.

**DoD**:
- `ConversionResult.status` checked after each parse
- `PARTIAL_SUCCESS` logged as warning
- `.errors` included in preprocess report per source
- Test: mock partial result → warning emitted

---

## Improvements (features)

### I1. PDF heading hierarchy (HIGH)

**Problem**: `heading_hierarchy_options` disabled by
default in Docling. All PDF headings flatten to level 1,
destroying heading structure critical for
`MarkdownTextSplitter` chunking.

**Fix**: enable in `_create_docling_converter`:
```python
opts.heading_hierarchy_options = HeadingHierarchyOptions(
    enabled=True,
    use_bookmarks=True,
    use_numbering=True,
)
```

**DoD**:
- PDF headings have proper hierarchy (h1/h2/h3)
- Chunking produces better boundaries
- Test: PDF with bookmarks → heading levels preserved
- Eval: before/after RAG quality comparison

---

### I2. Docling HybridChunker evaluation (HIGH)

**Problem**: lore-mcp uses `MarkdownTextSplitter`
(text-based), losing document structure. Docling's
`HybridChunker` operates on the structured document
model, preserving table boundaries, heading hierarchy,
and metadata.

**Fix**: benchmark study, not implementation.
- Compare MarkdownTextSplitter vs HybridChunker on
  the test-redist corpus
- Metrics: NDCG@5, recall@5, chunk quality (heading
  coherence, table integrity)

**DoD**: study document with benchmark results and
recommendation (replace, complement, or keep current).

---

### I3. VLM captioning concurrency (MEDIUM)

**Problem**: `PictureDescriptionApiOptions.concurrency`
defaults to 1. PPTX with 49 images takes ~2h serially
on CPU. Setting concurrency=2-4 with API-based VLM
could parallelize captioning.

**Fix**: add `concurrency` to captioning config.
Must be compatible with per-image checkpoint.

**DoD**:
- Configurable concurrency in config.yaml
- Per-image checkpoint preserved
- Test: mock concurrent captioning

---

### I4. Document timeout (MEDIUM)

**Problem**: no `document_timeout` set. Docling can
process indefinitely on complex documents.

**Fix**: set `document_timeout` in pipeline options
(default 120s). Returns `PARTIAL_SUCCESS` with partial
results rather than hanging. Configurable via
config.yaml.

**DoD**:
- `document_timeout` in config (default 120s)
- Partial results logged as warning
- Test: timeout returns partial document

---

### I5. Batch document conversion (MEDIUM)

**Problem**: `_phase1_worker` calls
`converter.convert()` per document. Docling's
`convert_all()` processes a batch with better
throughput.

**Fix**: use `convert_all()` in phase 1 subprocess
for all sources of the same format.

**DoD**:
- Phase 1 uses batch conversion
- Error per source still reported individually
- Test: batch of 3 docs → 3 results

---

### I6. Export options evaluation (MEDIUM)

**Problem**: `export_to_markdown` called with only
`image_mode=EMBEDDED`. Options like
`traverse_pictures`, `labels`, `compact_tables` not
evaluated.

**Fix**: study, not implementation. Test each option
on the test-redist corpus and measure impact on
chunk quality and RAG retrieval.

**DoD**: study document with option impact analysis.

---

## Priority order

1. **C1** YouTube fix — broken functionality, no
   video content indexed
2. **C2** ConversionResult — correctness, silent
   failures
3. **I1** Heading hierarchy — direct RAG quality
   impact, trivial fix
4. **I2** HybridChunker study — potential major
   quality improvement
5. **I3** Concurrency — 2-4x captioning speedup
6. **I4** Document timeout — resilience
7. **I5** Batch conversion — performance
8. **I6** Export options — quality tuning

---

## E12.89 — Concurrent LLM calls

### Problem

All LLM calls are sequential. Two unfactored functions
(`_call_llm` in enrich.py, `_fetch_api` in parse.py)
for the same need. 9 call sites total.

### Approach

**MVP1 — Factorize**: unified `call_llm()` in
`preprocess/llm.py`. All callers migrate.

**MVP2 — Parallelize**: 1 thread per call (daemon=True),
`threading.Semaphore(concurrency)` limits parallelism.
Main thread polls `_shutdown_requested` every 0.5s.
Ctrl+C response < 500ms guaranteed.

```python
sem = threading.Semaphore(concurrency)
threads = []
for i, task in enumerate(tasks):
    def worker(idx=i, t=task):
        with sem:
            results[idx] = call_llm(t)
    t = Thread(target=worker, daemon=True)
    t.start()
    threads.append(t)

while any(t.is_alive() for t in threads):
    time.sleep(0.5)
    if _shutdown_requested:
        raise KeyboardInterrupt
```

**MVP3 — Config**: `concurrency` from llm registry
entry (already wired for captioning).

### DoD

- Single LLM call function (factorized)
- Semaphore-limited parallelism
- Ctrl+C < 500ms
- Test: mock, concurrency=4, same result as sequential
- Benchmark: enrichment 17 sources before/after

---

## E12.90 — Harmonize directory arguments

### Problem

6 directory flags with confusing semantics.
`--prep-dir` resolved relative to `--docs-base-dir`,
not CWD. `--docs-base-dir` redundant when orig-dir
and prep-dir are explicit.

### New model

Two flags only:
- `--orig-dir`: read-only source files
- `--build-dir`: everything else

```
build-dir/
  <collection>.db
  <collection>.json/.bib
  manifest-prep.yaml
  build-report.json
  prep/
    source1.md
    source2.md
  .work/                  # transient, deleted unless --keep-intermediates
    checkpoint.json
    phase1-report.json
    *.phase1-parse.md
    *.docling.json
    *.frame-caption.md
    *.stt.json
    opt-*.db
```

### Key changes

- `--docs-base-dir` removed
- `--prep-dir` removed (becomes `build-dir/prep/`)
- `--output-dir` renamed to `--build-dir`
- Checkpoint moves from `~/.local/state/lore-mcp/<hash>/`
  to `build-dir/.work/`
- `--keep-intermediates` keeps `.work/` after success
- Reprise: same `--build-dir` = checkpoint found

### DoD

- 2 flags only: `--orig-dir` + `--build-dir`
- Checkpoint in `build-dir/.work/`
- `~/.local/state/lore-mcp/` no longer used
- All existing tests updated
- CLI help and docs updated
- Migration: deprecation warning for old flags (1 release)

### Risk

Breaking change CLI. Pre-release, no external users.

