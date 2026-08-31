# Release Notes — lore-mcp v0.1.0-dev

## Overview

First development release of LORE — Local Offline
Retrieval Engine for MCP. Semantic search over
local technical documents via Model Context
Protocol.

## Features

### Core RAG

- **SQLite + sqlite-vec** storage backend with
  cosine KNN search, model validation via meta
  table, deterministic chunk IDs
- **Embedding engine** with `builtin` mode
  (sentence-transformers, auto GPU/CPU with VRAM
  assessment) and `api` mode (OpenAI-compatible
  endpoints, SSL/CA support)
- **MCP server** (MCPServer v2) exposing
  `search_docs`, `list_indexed_sources`,
  `list_collections` via stdio or SSE transport
- **Ingestion pipeline** with preprocessing
  (NUL/base64 stripping), recursive chunking
  (configurable size/overlap via env vars),
  batch embedding

### Multi-collection

- **LORE_DB_DIR** for multi-collection mode —
  directory of `.db` files with `<theme>-<level>`
  naming convention (nda/libre/restreint/gris)
- **Cross-corpus search** merging results by
  descending score across collections
- **Per-collection metadata** display including
  model name, dimensions, chunk parameters

### Bibliographic metadata

- **Sources table** in each `.db` with title,
  author, URL, license, level
- **YAML manifest** for production indexing with
  per-source bibliographic metadata
- **Front matter extraction** from Markdown when
  no manifest provided
- **Output files**: `.json` (machine-readable),
  `.bib` (BibTeX), `.md` (human-readable) per
  collection
- **Search results** include bibliographic
  metadata (title, author, license)

### AutoRAG evaluation

- **`lore-mcp eval`** — evaluate retrieval
  quality with 3 metric levels:
  - Embedding (no LLM): score_spread, source_diversity
  - Retrieval (with ground truth): hit, word_overlap, MRR
  - LLM-based (RAGAS, optional): faithfulness, context_recall
- **`lore-mcp optimize`** — auto-optimize
  chunking params (chunk_size × overlap × top_k)
- **Multi-model optimization** — compare
  embedding models alongside chunk params via
  `--models` CLI or YAML config
- **Extractive fallback** — evaluation works
  without RAGAS or LLM installed

### Build workflow

- **`lore-mcp build`** — single command:
  manifest + models → optimized `.db` + metadata
  + build report
- **Pre-flight validation** of all models before
  starting (probe endpoints, check HF cache)
- **Resumability** — interrupted builds resume
  from where they stopped
- **`--skip-optimize`** for fast builds without
  optimization
- **Unified build config** (`build-config.yaml`)
  merging embedding models, judge LLM, metrics,
  and optimization params in one file

### Embedding modes

- **`builtin`** — sentence-transformers in-process
  with automatic GPU/CPU selection and FP16/FP32
  based on VRAM assessment
- **`builtin:gpu`** — force GPU (crash if unavailable)
- **`builtin:cpu`** — force CPU
- **`api`** — external endpoint (TEI, vLLM)
- **`Embedder.unload()`** — free GPU memory
  between models during multi-model optimization

## Default model

**nomic-ai/nomic-embed-text-v2-moe** (Level 2 —
Libre quasi-reproducible, Apache 2.0, 768d,
multilingual). See ADR-005.

bge-m3 (BAAI) excluded as default — Level 4
(opaque training data) per free AI policy.
Available via `LORE_MODEL` with documented
derogation.

## Documentation

- **9 EPUBs** generated from Markdown docs:
  architecture, API reference, code guide,
  configuration, tutorial, ADRs, AI guidelines,
  research notes, quality observations
- **5 ADRs**: license (GPL→AGPL), project name,
  AGPL migration, multi-collection, default model
- **Tutorial**: builtin, TEI containers, API,
  build workflow
- **TEI recipes**: Nomic v2 MoE (120-1.9.3),
  Granite R2 311M (latest)

## Quality

- **168 tests** (TDD, 10 test files)
- **AGPL-3.0-or-later** license (network clause)
- **DCO** (Developer Certificate of Origin)
- **AI-assisted development** with dual trailers
  (Assisted-by + Co-Authored-By)

## Environment variables

| Variable | Default |
|----------|---------|
| `LORE_DB_PATH` | `./lore.db` |
| `LORE_DB_DIR` | *(none)* |
| `LORE_MODEL` | `nomic-ai/nomic-embed-text-v2-moe` |
| `LORE_EMBED_MODE` | `builtin` |
| `LORE_API_URL` | *(none)* |
| `LORE_API_MODEL` | same as LORE_MODEL |
| `LORE_API_VERIFY` | `true` |
| `LORE_API_CA_BUNDLE` | *(system CA)* |
| `LORE_CHUNK_SIZE` | `1024` |
| `LORE_CHUNK_OVERLAP` | `128` |
| `LORE_LLM_URL` | *(required for eval)* |
| `LORE_LLM_MODEL` | `granite-8b-instruct` |
