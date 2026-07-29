# Architecture

This document describes the internal architecture
of lore-mcp. It explains design decisions, data
flows, and implementation trade-offs. For
configuration reference, see
[`configuration.md`](configuration.md).

## System overview

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Markdown/   │     │   Embedder   │     │    SQLite     │
│  text files  │────▶│  (GPU/API/   │────▶│  + sqlite-vec │
│              │     │   CPU)        │     │   (.db file)  │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
     Ingestion (offline, CLI)                     │
─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│─ ─ ─ ─
     Serving (runtime, MCP)                       │
                                                  │
┌──────────────┐     ┌──────────────┐     ┌──────┴───────┐
│  MCP client  │◀───▶│  MCP server  │◀───▶│    SQLite     │
│  (Claude,    │     │  (FastMCP)   │     │  + sqlite-vec │
│   Cursor…)   │     │              │     │   (.db file)  │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────┴───────┐
                     │   Embedder   │
                     │  (query-time)│
                     └──────────────┘
```

Two distinct phases share the same `.db` file:

1. **Ingestion** (offline): CLI reads files,
   preprocesses, chunks, embeds, and stores
   vectors in SQLite.
2. **Serving** (runtime): MCP server receives
   queries, embeds them, performs KNN search
   in SQLite, and returns results.

## Store layer

**Module:** `src/lore_mcp/store.py`

### Why two tables?

sqlite-vec requires a `vec0` virtual table for
KNN indexing. This virtual table stores only
vectors and rowids — no metadata. A regular
`chunks` table stores all metadata (content,
source file, chunk index). The two are linked
by SQLite's implicit `rowid`.

This is the standard sqlite-vec pattern, not
a lore-mcp invention.

### Table schema

```sql
-- KNN index (sqlite-vec virtual table)
CREATE VIRTUAL TABLE chunks_vec USING vec0(
    embedding float[1024] distance_metric=cosine
);

-- Metadata (regular SQLite table)
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    source_file TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT DEFAULT '{}'
);

-- Index metadata (model tracking)
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

### Rowid synchronization

When inserting a chunk, the regular table is
inserted first. `cursor.lastrowid` captures the
auto-generated rowid, which is then used as the
explicit rowid for the vec0 table. This ensures
the JOIN works correctly.

See `store.py:insert_chunk()` for the
implementation.

### Distance metric

`distance_metric=cosine` is set at table
creation. sqlite-vec cosine distance returns
values in `[0, 2]` (0 = identical, 2 = opposite).
The store converts this to a similarity score:
`score = 1 - distance`.

This matches the convention used by the pgvector
prototype (`1 - (embedding <=> query)`).

### KNN query pattern

```sql
WITH knn AS (
    SELECT rowid, distance
    FROM chunks_vec
    WHERE embedding MATCH ?
    ORDER BY distance
    LIMIT ?
)
SELECT c.content, c.source_file, knn.distance
FROM knn
LEFT JOIN chunks c ON c.rowid = knn.rowid
ORDER BY knn.distance
```

The CTE performs the KNN search in the vec0
table, then JOINs back to the regular table
for metadata. See `store.py:search()`.

### Model validation

The `meta` table stores `model_name`, `model_dim`,
and `created_at` at index creation time.
`store.py:validate_model()` checks these values
before any query — refusing to search an index
built with a different model prevents silent
garbage results.

### Embeddings as binary BLOBs

`sqlite_vec.serialize_float32()` packs a
`list[float]` into a compact binary BLOB
(`struct.pack`). This is more efficient than
JSON serialization and is the recommended
sqlite-vec approach.

## Embedding layer

**Module:** `src/lore_mcp/embedder.py`

### Fallback chain

The embedder tries backends in priority order:

1. **Local GPU (CUDA):** fastest (~20ms/query).
   Requires NVIDIA GPU with sufficient VRAM.
2. **Remote API:** any OpenAI-compatible
   `/v1/embeddings` endpoint (vLLM, Llama Stack).
3. **Local CPU:** slowest (~200ms) but always
   available if RAM is sufficient.

In `auto` mode, `embedder.py:_select_device_dtype()`
evaluates GPU capabilities first, falls back to
CPU if GPU is unavailable or has insufficient
VRAM.

### Capability assessment

Before loading the model, the embedder evaluates
hardware capabilities to choose the optimal
loading strategy.

**GPU assessment** (`embedder.py:assess_gpu()`):

1. Check CUDA availability (`torch.cuda.is_available()`)
2. Read free VRAM (`torch.cuda.mem_get_info()`)
3. Check compute capability for FP16 support
   (major >= 7, Volta+)
4. Decision:
   - Free VRAM >= 2.8 GB → FP32 (full precision)
   - Free VRAM >= 1.5 GB and FP16 supported → FP16
   - Otherwise → unavailable, with actionable
     message ("try freeing VRAM")

**CPU assessment** (`embedder.py:assess_cpu()`):

1. Read available RAM from `/proc/meminfo`
   (fallback: `psutil`)
2. bge-m3 needs ~4 GB minimum (2.1 GB weights
   + loading overhead)
3. FP16 has no benefit on CPU (x86 upcasts to
   FP32 for computation)

The thresholds are defined as module constants
(`FP32_VRAM_GB`, `FP16_VRAM_GB`, `CPU_RAM_MIN_GB`)
for easy tuning.

### Lazy loading

The model is not loaded at import time or at
`Embedder.__init__()`. It loads on the first
call to `embed()` or `embed_batch()`. This is
critical for two reasons:

1. The MCP server starts instantly (no 30-second
   model load at startup).
2. The capability assessment runs just before
   loading, with the most current VRAM/RAM state.

See `embedder.py:_ensure_loaded()`.

### Output format

`sentence-transformers` `encode()` returns
`numpy.ndarray` (float32). The embedder converts
to `list[float]` via `.tolist()` for compatibility
with `sqlite_vec.serialize_float32()`.

`normalize_embeddings=True` is always passed to
`encode()` — bge-m3 requires L2-normalized
vectors for cosine similarity.

## MCP server

**Module:** `src/lore_mcp/server.py`

### Tools exposed

| Tool | Signature | Description |
|------|-----------|-------------|
| `search_docs` | `(query: str, top_k: int = 5) -> str` | KNN semantic search |
| `list_indexed_sources` | `() -> str` | List indexed files with counts |

Both tools return formatted text strings, not
structured data. This is intentional — MCP tool
results are consumed by LLMs which work better
with readable text than JSON.

### Lazy initialization

Both the database connection and the embedder
are lazily initialized on first tool call. This
means the MCP server starts in milliseconds and
only loads the model when a query arrives.

See `server.py:_get_db()` and
`server.py:_get_embedder()`.

### Configuration

All configuration is via environment variables
(see [`configuration.md`](configuration.md)).
The server reads `LORE_DB_PATH`, `LORE_MODEL`,
`LORE_EMBED_MODE`, `LORE_API_URL`, and
`LORE_API_MODEL`.

## Ingestion pipeline

**Module:** `src/lore_mcp/ingest.py`

### Pipeline stages

```
Files → Preprocess → Chunk → Embed → Store
```

1. **Traverse:** recursively find `*.md` files.
2. **Preprocess** (`ingest.py:preprocess()`):
   strip NUL characters and base64 image data
   lines. Documents shorter than 100 characters
   after preprocessing are skipped.
3. **Chunk** (`ingest.py:chunk_document()`):
   `RecursiveCharacterTextSplitter` with Markdown
   separators (`## `, `### `, `\n\n`, `\n`).
   Defaults: 2048 chars, 128 overlap.
4. **Embed:** batch embedding (64 chunks per
   batch) via the embedder.
5. **Store:** batch insert into SQLite.

### Deterministic chunk IDs

Each chunk gets an ID derived from
`sha256(source_file:index:first_64_chars)`,
truncated to 16 hex characters. This makes IDs
deterministic — re-indexing the same file produces
the same IDs, enabling idempotent inserts
(`INSERT OR IGNORE`).

See `ingest.py:chunk_document()`.

### Base64 stripping

Markdown files converted from PDFs (e.g. via
Docling) can contain base64-encoded images. A
70 KB text document can grow to 1 MB with
embedded images. Lines containing `base64,` are
stripped before chunking — otherwise chunks would
be mostly binary noise.

Image captioning (replacing base64 with
AI-generated descriptions) is a post-MVP feature
(backlog E6.03).

### Error handling

`ingest_directory()` catches errors per-file and
continues with the next file. Errors are collected
in the return value for reporting, not raised.
This prevents a single corrupt file from aborting
a large indexing run.
