# Design — Build pipeline

- **Status:** Référence
- **Date:** 2026-09-18
- **Modules:** `build.py`, `ingest.py`, `eval.py`,
  `build_config.py`

## Build workflow

```
lore-mcp build manifest.yaml --config config.yaml
│
├─ 0. [Optional] Preprocess
│     preprocess_sources() → manifest-prep.yaml
│
├─ 1. Validate models
│     Check API endpoints, HF cache existence
│
├─ 2. Optimize (unless --skip-optimize)
│     ├─ Generate questions from docs (headings)
│     ├─ For each (model × chunk_size × overlap):
│     │   ├─ Ingest with params
│     │   ├─ Evaluate retrieval (NDCG, Recall, MRR)
│     │   └─ Record scores
│     └─ Select best config (highest score)
│
├─ 3. Final ingest
│     With winning params → collection.db
│
├─ 4. Metadata
│     generate_all() → .json, .bib, .md
│
└─ 5. Report
       build-report.json
```

## Chunking (`ingest.py`)

- **Splitter**: `MarkdownTextSplitter` (langchain)
  Tables, headings, code blocks protected natively.
- **Default**: chunk_size=1024, overlap=128
- **Parent-child**: optional double indexation.
  Parent chunks inserted in `parent_chunks` table,
  child chunks linked via `parent_id`.
- **IDs**: deterministic SHA-256 of
  `source_file:index:content[:64]`
- **Clean**: `clean_text()` applied before chunking
- **ConsecutiveErrorThreshold**: 3 consecutive
  embedding failures → stop build

## Embedding (`embedder.py`)

Three modes (automatic fallback):
1. `builtin:gpu` — sentence-transformers CUDA
2. `builtin:cpu` — sentence-transformers CPU
3. `api` — remote /v1/embeddings endpoint

`Embedder.unload()` frees GPU memory between
models (gc.collect + torch.cuda.empty_cache).

## Optimization (`eval.py`)

Dimensions varied:
- Embedding models (from config)
- chunk_size (default: 512, 1024, 2048)
- chunk_overlap (default: 64, 128)
- top_k (default: 3, 5, 10)
- Reranking models (optional)
- Window sizes (optional)
- MMR on/off (optional)

Evaluation: heading-based QA pairs (before
chunking → no chunking bias). Metrics: NDCG@k,
Recall@k, MRR, plus embedding metrics
(score_spread, source_diversity).

Resumability: scores saved to `scores.jsonl`,
existing configs skipped on resume.

## Ingest with manifest

`ingest_with_manifest()` reads manifest, iterates
sources, reads each prep file from docs_dir,
chunks, embeds, and inserts. Upserts source
metadata (title, author, license, url, date).

## Key config fields

| Field | Default | Purpose |
|-------|---------|---------|
| `embedding.model` | nomic-v2-moe | Embedding model |
| `embedding.mode` | builtin | GPU/CPU/API |
| `chunking.chunk_size` | 1024 | Chunk chars |
| `chunking.chunk_overlap` | 128 | Overlap chars |
| `optimize.chunk_sizes` | [512,1024,2048] | Grid |
| `optimize.num_questions` | 50 | Eval questions |
| `judge.models` | [] | RAGAS judge LLM |

## Cross-references

- `docs/studies/design-search-pipeline.md` — search
- `docs/studies/design-config-registry.md` — config
- `docs/studies/design-captioning-pipeline.md` — preprocess captioning
- `docs/studies/grooming-E11.01.md` — build design
- `docs/studies/grooming-E10.29.md` — optimize

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
