# Architecture

This document describes the internal architecture
of lore-mcp: why each design decision was made,
how the components interact, and how the code
implements the design. For configuration
reference, see [`configuration.md`](configuration.md).
For decision records, see `adr/`.

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
│  (Claude,    │     │  (MCPServer)   │     │  + sqlite-vec │
│   Cursor…)   │     │              │     │   (.db file)  │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────┴───────┐
                     │   Embedder   │
                     │  (query-time)│
                     └──────────────┘
```

Two distinct phases share the same `.db` file:

1. **Ingestion** (offline): reads files,
   preprocesses, chunks, embeds, and stores
   vectors in SQLite.
2. **Serving** (runtime): MCP server receives
   queries, embeds them, performs KNN search
   in SQLite, and returns results.

### Why two phases?

The embedding model (~2 GB) takes 10-30 seconds
to load. If ingestion and serving were the same
process, the MCP server would block on model
loading at startup. By separating the phases,
the server starts instantly and only loads the
model on the first query (lazy loading).

The `.db` file is the interface between the two
phases — a single portable file that can be
copied, distributed, or versioned independently
from the code.

## Store layer

**Module:** `src/lore_mcp/store.py`

### Why sqlite-vec?

Three vector stores were evaluated (see
`docs/studies/reference/research-notes.md`):

| Criteria | FAISS | ChromaDB | sqlite-vec |
|----------|-------|----------|------------|
| Portability | Binary file | Directory | **Single .db** |
| SQL standard | No | No | **Yes** |
| Infrastructure | None | Server optional | **None** |
| Suited volume | Billions | < 10M | Thousands-millions |

sqlite-vec was chosen because:
1. **Single file** — a `.db` file is self-contained
   and redistributable. No server, no directory
   tree, no binary format conversion.
2. **SQL standard** — queries, joins, window
   functions, transactions. No proprietary API.
3. **Zero infrastructure** — no server process,
   no network, no configuration. Just a file.
4. Our expected volume (~50K chunks) is well
   within sqlite-vec's sweet spot.

FAISS is overkill (designed for billions of
vectors). ChromaDB adds unnecessary complexity
(client-server, directory storage).

### Why two tables?

sqlite-vec's `vec0` virtual table stores only
vectors and rowids — no metadata columns (text
content, source file, etc.). This is by design:
the virtual table is optimized for KNN search,
not for general-purpose storage.

A regular `chunks` table stores all metadata.
The two are linked by SQLite's implicit `rowid`.

This is the standard sqlite-vec pattern, not
a lore-mcp invention. The alternative — using
vec0 auxiliary columns (`+content text`) — was
rejected because auxiliary columns cannot be
used in WHERE clauses and have a 16-column limit.

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

### Rowid synchronization pattern

The critical implementation detail: when
inserting, the regular table must be inserted
**first** to get its auto-generated rowid, which
is then used as the explicit rowid for the vec0
table.

```python
# store.py:insert_chunk() — simplified
cur = db.execute(
    "INSERT OR IGNORE INTO chunks(...) VALUES (...)",
    (chunk_id, source_file, chunk_index, content),
)
if cur.rowcount > 0:
    db.execute(
        "INSERT INTO chunks_vec(rowid, embedding) "
        "VALUES (?, ?)",
        (cur.lastrowid, serialize_float32(embedding)),
    )
```

Why `INSERT OR IGNORE`? Chunk IDs are
deterministic (see Ingestion pipeline below).
Re-indexing the same file produces the same IDs.
The `OR IGNORE` makes ingestion idempotent — safe
to run multiple times without duplicates.

Why check `cur.rowcount > 0`? If the chunk
already exists (duplicate ID), the INSERT is
ignored and `lastrowid` would be stale. We only
insert the vector if the metadata row was
actually created.

### Why cosine distance?

`distance_metric=cosine` is set at table
creation. Two reasons:

1. **bge-m3 produces normalized vectors** — for
   normalized vectors, cosine similarity and dot
   product are equivalent, but cosine distance is
   the standard convention in the embedding
   community.
2. **Compatibility with the pgvector prototype**
   — the lab prototype used `vector_cosine_ops`
   (see `docs/studies/reference/pgvector-schema-reference.sql`).
   Using the same metric ensures scores are
   comparable between local and cluster deployments.

sqlite-vec cosine distance returns values in
`[0, 2]` (0 = identical, 2 = opposite). The
store converts to similarity: `score = 1 - distance`.

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

Why a CTE (Common Table Expression)? The KNN
search runs in the vec0 virtual table, which
only knows about rowids and distances. The CTE
isolates the KNN operation, then the outer query
JOINs back to the regular table for metadata.
This is more efficient than a subquery because
SQLite can optimize the CTE independently.

See `store.py:search()` for the implementation.

### Model validation

The `meta` table stores `model_name`, `model_dim`,
and `created_at` at index creation time.
`store.py:validate_model()` checks these values
before any query.

Why this matters: if you change `LORE_MODEL`
after indexing, the query embeddings will be in
a different vector space than the stored
embeddings. KNN search would return meaningless
results without any error. The meta check
prevents this silent failure.

### Embeddings as binary BLOBs

`sqlite_vec.serialize_float32()` packs a
`list[float]` into a compact binary BLOB via
`struct.pack`. This is ~4× smaller than JSON
serialization and avoids the parsing overhead.
This is the recommended sqlite-vec approach.

### Thread safety

In single-collection mode, the server caches one
database connection (`server.py:_get_single_db()`).
SQLite supports concurrent reads from the same
connection. A `threading.Lock` prevents the race
condition where two concurrent requests would
both create a connection.

In multi-collection mode, connections are opened
and closed per-request with `try/finally` to
prevent resource leaks.

## Embedding layer

**Module:** `src/lore_mcp/embedder.py`

### Why sentence-transformers?

sentence-transformers is the de facto standard
Python library for generating embeddings. It
wraps HuggingFace Transformers with an
embedding-specific API (`encode()`,
`normalize_embeddings=True`). Native CUDA GPU
support, no separate GPU library needed.

The alternative — calling the HuggingFace
Transformers API directly — would require manual
pooling, normalization, and device management.
sentence-transformers handles all of this.

### Why bge-m3?

BAAI/bge-m3 was selected based on AutoRAG
benchmarks on a Red Hat technical corpus (see
`docs/studies/reference/research-notes.md`):
+13% answer_correctness vs nomic-embed-text-v1.5.
It's also MIT-licensed, multilingual (FR, EN, ZH),
and recommended by Red Hat for AutoRAG.

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
loading strategy — and to provide actionable
feedback when resources are insufficient.

**GPU assessment** (`embedder.py:assess_gpu()`):

```python
free, total = torch.cuda.mem_get_info(0)
major, _ = torch.cuda.get_device_capability(0)
```

Decision tree:
1. Check CUDA availability
2. Read free VRAM via `torch.cuda.mem_get_info()`
3. Check compute capability for FP16 support
   (major >= 7 = Volta architecture, 2017+)
4. Decision:
   - Free VRAM >= 2.8 GB → FP32 (full precision)
   - Free VRAM >= 1.5 GB and FP16 supported → FP16
   - Otherwise → unavailable, with **actionable
     message** ("try freeing VRAM")

Why actionable messages? A Platform component
should help its consumers solve problems, not
just report them. "CUDA not available" is useless.
"NVIDIA RTX 500 Ada: 1.3/3.7 GB VRAM free,
need 1.5 GB minimum. Try freeing VRAM (close
GPU-heavy applications)." tells the user what
to do.

**CPU assessment** (`embedder.py:assess_cpu()`):

1. Read available RAM from `/proc/meminfo`
   (fallback: `psutil`)
2. bge-m3 needs ~4 GB minimum (2.1 GB weights
   + ~2× overhead during loading)
3. FP16 has no benefit on CPU (x86 upcasts to
   FP32 for computation anyway)

The thresholds (`FP32_VRAM_GB=2.8`,
`FP16_VRAM_GB=1.5`, `CPU_RAM_MIN_GB=4.0`) are
module constants. They were derived from the
actual bge-m3 model size (2.1 GB FP32 on disk,
measured from the cached model files) plus ~30%
overhead for inference buffers.

### Lazy loading

The model is not loaded at import time or at
`Embedder.__init__()`. It loads on the first
call to `embed()` or `embed_batch()` via
`_ensure_loaded()`. This is critical for two
reasons:

1. **Instant MCP server startup** — no 30-second
   model load blocking the MCP handshake.
2. **Fresh capability assessment** — VRAM/RAM
   state is evaluated at load time, not at import
   time. If the user frees GPU memory between
   server start and first query, the model can
   use the GPU.

Trade-off: the `model_dim` property triggers
model loading in local mode (it needs the model
to know the dimension). In API mode, `model_dim`
detects the dimension via a test API call
(`_probe_api_dim()`) without loading the local
model.

### SSL and self-signed certificates

For API mode with self-signed certificates
(e.g. OpenShift internal CA), two env vars
control SSL behavior:

- `LORE_API_VERIFY=false` — disable SSL
  verification entirely
- `LORE_API_CA_BUNDLE=/path/to/ca.pem` — use
  a custom CA bundle

See `embedder.py:_get_api_verify()` and
[`configuration.md`](configuration.md).

### Output format

`sentence-transformers` `encode()` returns
`numpy.ndarray` (float32). The embedder converts
to `list[float]` via `.tolist()` for compatibility
with `sqlite_vec.serialize_float32()`.

`normalize_embeddings=True` is always passed to
`encode()` — bge-m3 requires L2-normalized
vectors for cosine similarity search. Without
normalization, cosine distance is not meaningful.

## MCP server

**Module:** `src/lore_mcp/server.py`

### Why MCPServer (MCP SDK v2)?

MCPServer (formerly FastMCP in v1) is the official
Anthropic Python SDK for MCP servers. It handles
protocol negotiation, tool registration, and
transport (stdio, SSE, streamable-http). Using it
means lore-mcp is compatible with any MCP client
without custom protocol code.

The migration from FastMCP (v1) to MCPServer (v2)
was triggered by a consumer bug report: `pip
install` resolved `mcp>=1.0` to v2.x, which
renamed the class. The project now pins
`mcp>=2.0`.

### Tools exposed

| Tool | Signature | Description |
|------|-----------|-------------|
| `search_docs` | `(query: str, top_k: int = 5, collection: str = "") -> str` | KNN semantic search (single or cross-collection) |
| `list_indexed_sources` | `(collection: str = "") -> str` | List indexed files with counts |
| `list_collections` | `() -> str` | List available collections (multi-collection mode) |

All tools return **formatted text strings**, not
structured data. This is intentional — MCP tool
results are consumed by LLMs which work better
with readable text than JSON. The format is
designed for LLM context windows: concise headers,
one result per section, source file and score
visible.

### Two operating modes

The server supports two modes determined by
environment variables:

1. **Single-collection** (`LORE_DB_PATH`): one
   `.db` file, the original behavior. The
   database connection is cached across queries
   (`_get_single_db()`) to avoid opening a new
   connection per request.

2. **Multi-collection** (`LORE_DB_DIR`): a
   directory of `.db` files. Each query can
   target a specific collection or search across
   all. Connections are opened and closed per
   request to avoid holding locks on all files.

`LORE_DB_DIR` takes precedence. If neither is
set, the default is `./lore.db`.

### Lazy initialization and thread safety

The embedder and single-collection database are
lazily initialized on first use. A
`threading.Lock` prevents the race condition
where two concurrent SSE requests could both
see `_embedder is None` and create two instances
(wasting GPU memory by loading the model twice).

```python
_init_lock = threading.Lock()

def _get_embedder():
    global _embedder
    with _init_lock:
        if _embedder is None:
            _embedder = Embedder(...)
    return _embedder
```

## Collections layer

**Module:** `src/lore_mcp/collections.py`

See also: [`adr/004-multi-collection.md`](adr/004-multi-collection.md)

### Why separate .db files?

The alternative was a single database with a
`collection` column. Separate files were chosen
because:

1. **Portability** — each `.db` is independently
   copyable and redistributable.
2. **License isolation** — a `libre` collection
   and an `nda` collection must not be in the
   same file, because distributing the file
   would leak NDA content.
3. **Independent lifecycle** — collections can
   be rebuilt, deleted, or versioned independently.
4. **No schema changes** — the existing store.py
   works unmodified. Each `.db` has the same
   schema.

### File naming convention

`<theme>-<level>.db` where level ∈ {`nda`,
`libre`, `restreint`, `gris`}.

The level indicates redistribution rights:

| Level | Redistributable | Criteria |
|-------|----------------|----------|
| `nda` | No | Sources under subscription or NDA |
| `libre` | Yes | License allows redistribution as RAG base |
| `restreint` | No | Public license forbids RAG redistribution |
| `gris` | Yes (warning) | Redistribution uncertain, personal use |

`collections.py:_parse_name()` extracts theme
and level from the filename by splitting on the
last hyphen and checking against the known level
set.

### Cross-corpus search

`search_across()` queries every `.db` file
independently, collects all results, sorts by
descending score, and returns the top-k.

This is a simple merge strategy. Each collection
runs its own KNN search with `top_k` results,
then the results are merged. This means up to
`N × top_k` results are collected (where N is
the number of collections) before truncation.

Why not a smarter merge? For our scale (< 10
collections), the simple approach is fast enough
and avoids the complexity of distributed KNN
algorithms. If performance becomes an issue with
many collections, a threshold-based early
termination could be added.

### Discovery

`discover_collections(db_dir)` scans a directory
for `.db` files, opens each one, reads chunk/file
counts via `list_sources()`, and extracts
theme/level from the filename. Invalid or
corrupt `.db` files are silently skipped.

## Ingestion pipeline

**Module:** `src/lore_mcp/ingest.py`

### Pipeline stages

```
Files → Preprocess → Chunk → Embed → Store
```

1. **Traverse:** recursively find `*.md` files
   via `pathlib.rglob("*.md")`.
2. **Preprocess** (`ingest.py:preprocess()`):
   strip NUL characters and base64 image data
   lines. Documents shorter than 100 characters
   after preprocessing are skipped.
3. **Chunk** (`ingest.py:chunk_document()`):
   `RecursiveCharacterTextSplitter` with Markdown-
   aware separators.
4. **Embed:** batch embedding (64 chunks per
   batch) via the embedder.
5. **Store:** batch insert into SQLite.

### Why RecursiveCharacterTextSplitter?

This splitter from langchain-text-splitters tries
separators in order: `\n## `, `\n### `,
`\n#### `, `\n\n`, `\n`, ` `, `""`. It
preserves document structure by preferring to
split at heading and paragraph boundaries.

The defaults (1024 chars, 128 overlap) were
validated by AutoRAG E1.08 benchmarks with bge-m3
(+13% answer_correctness vs 2048/128). Configurable
via `LORE_CHUNK_SIZE` and `LORE_CHUNK_OVERLAP`.
See `ingest.py:get_chunk_config()` and
[`configuration.md`](configuration.md).

### Deterministic chunk IDs

```python
chunk_id = hashlib.sha256(
    f"{source_file}:{index}:{content[:64]}".encode()
).hexdigest()[:16]
```

Why this formula?
- `source_file` + `index` → unique per chunk
  position in a file
- `content[:64]` → detects content changes
  (re-indexing after editing a file produces
  different IDs for changed chunks)
- `sha256[:16]` → 16 hex chars = 64 bits,
  collision probability negligible for our scale

This enables idempotent inserts: `INSERT OR
IGNORE` skips chunks that already exist.
Re-indexing a file without changes is a no-op.

### Base64 stripping

Markdown files converted from PDFs (e.g. via
Docling) can contain base64-encoded images. A
70 KB text document can grow to 1 MB with
embedded images. Lines containing `base64,` are
stripped **before chunking** — otherwise chunks
would be mostly binary noise that wastes the
embedding model's token budget.

Image captioning (replacing base64 with
AI-generated descriptions) is planned as backlog
item E6.03.

### Batch embedding

Chunks are embedded in batches of 64
(`EMBED_BATCH_SIZE`). This balances:
- **GPU utilization** — batching amortizes the
  GPU kernel launch overhead
- **Memory pressure** — 64 × 1024 chars ≈ 65 KB
  of text per batch, well within GPU memory
- **Progress granularity** — each batch produces
  a checkpoint (the store commits after each
  batch)

### Error handling

`ingest_directory()` catches errors per-file and
continues with the next file. Errors are collected
in the return dict (`result["errors"]`), not
raised. This prevents a single corrupt file from
aborting a large indexing run.

The caller can inspect `result["errors"]` to
decide whether the partial index is acceptable.

## Bibliographic metadata

**Modules:** `src/lore_mcp/manifest.py`,
`src/lore_mcp/metadata.py`

### Why store metadata in the database?

Search results that return only file paths are
not useful for citation or provenance. The
`sources` table stores bibliographic metadata
(title, author, URL, license) alongside the
chunks, so `search_docs` can return attribution
information with every result.

This also makes the `.db` file self-contained
for redistribution — a consumer doesn't need
access to the original sources to know where
the content came from.

### Sources table

```sql
CREATE TABLE sources (
    source_file TEXT PRIMARY KEY,
    title TEXT,
    author TEXT,
    url TEXT,
    date TEXT,
    license TEXT,
    level TEXT,
    extra TEXT DEFAULT '{}'
);
```

`chunks.source_file` references
`sources.source_file` by convention (no FK
constraint, for backward compatibility with
`.db` files created before E6.05).

### Manifest-driven ingestion

`manifest.yaml` is the primary input for
production indexing:

```yaml
collection: ia-libre
level: libre
sources:
  - path: intro.md
    title: "Introduction to AI Serving"
    author: "Romain Chantereau"
    license: "CC-BY-SA-4.0"
  - path: config.md
    title: "Configuration Guide"
```

See `manifest.py:parse_manifest()` and
`ingest.py:ingest_with_manifest()`.

Without a manifest, `ingest_directory()` extracts
metadata from YAML front matter or Markdown
headings via `manifest.py:extract_source_metadata()`.

### Output metadata files

After ingestion, `metadata.py:generate_all()`
produces three files alongside each `.db`:

- **`.json`** — machine-readable: model, dims,
  chunking params, stats, SHA-256 checksum,
  source list. See `metadata.py:generate_collection_json()`.
- **`.bib`** — BibTeX: one `@misc` entry per
  source with author, title, URL, license.
  Generated without external dependencies.
  See `metadata.py:generate_collection_bib()`.
- **`.md`** — human-readable: parameters,
  statistics, source list, gris-level warning
  if applicable.
  See `metadata.py:generate_collection_md()`.

### Portability (E7.01)

The `sources` table is standard SQL — portable
to pgvector without modification. For non-SQL
backends (Milvus), the bibliographic data can
be serialized into the `extra` JSON field of
each vector record. The `export(collection)`
method (E7.01 backend abstraction) must include
source metadata alongside chunk data.

### Search output with metadata

When a source has bibliographic metadata, the
MCP tool output includes it:

```
[intro.md] (score: 0.5985)
  Title: Introduction to AI Serving | Author: RC | License: CC-BY-SA-4.0
Content of the matching chunk...
```

See `server.py:format_search_results()`.

## RAG evaluation

**Module:** `src/lore_mcp/eval.py`

### Why integrated evaluation?

A Platform component should provide tools to
validate its own output quality. Without
integrated evaluation, consumers must build
ad hoc pipelines with SDG Hub, RAGAS, and custom
scripts. lore-mcp provides this as a built-in
capability.

### Architecture

```
Chunks (from .db)
    ↓
Question generation (extractive or RAGAS TestsetGenerator)
    ↓
For each question: embed → KNN search → retrieve contexts
    ↓
Score: text overlap (built-in) or RAGAS metrics (optional)
    ↓
JSON report
```

### Two modes

**`lore-mcp eval`** — evaluate an existing index:
1. Generate N questions from indexed chunks
2. For each: embed query, search, score contexts
3. Output JSON report with per-question and
   aggregate scores

**`lore-mcp optimize`** — find optimal parameters:
1. Vary chunk_size (512, 1024, 2048), overlap
   (64, 128), top_k (3, 5, 10)
2. For each config: index, retrieve, score
3. Questions generated once and reused
4. Report best configuration

### Scoring without RAGAS

The built-in scorer uses text overlap metrics:
- **hit**: 1.0 if ground truth appears in any
  retrieved context, 0.0 otherwise
- **word_overlap**: fraction of ground truth
  words found in the best matching context

This works without any LLM or external dependency.
When RAGAS is installed (`pip install lore-mcp[eval]`),
LLM-based metrics (faithfulness, context_recall,
answer_correctness) are available.

### LLM configuration

RAGAS metrics need a **chat-capable LLM** (not
just an embedding model). Two env vars:

- `LORE_LLM_URL` — vLLM/OpenAI-compatible chat
  endpoint
- `LORE_LLM_MODEL` — model name (e.g.
  `granite-8b-instruct`)

See [`configuration.md`](configuration.md).

### Model specificity

Evaluation and optimization results are
**specific to the embedding model** used. A
configuration optimal for bge-m3 1024d may not
be optimal for a different model. Both `run_eval`
and `run_optimize` include `model_name` in the
output report for traceability.

### Optimize with manifest

`lore-mcp optimize --manifest manifest.yaml`
uses `ingest_with_manifest` for each tested
configuration, preserving bibliographic metadata
(title, author, license) in the temporary `.db`
files. This ensures the optimization loop
produces `.db` files with the same metadata
quality as production indexing.

See `eval.py:run_optimize()` and
`server.py:_run_optimize()`.

### Multi-model optimization

`lore-mcp optimize --models "bge-m3,nomic-embed"`
varies embedding models alongside chunk parameters.
Each model gets its own Embedder and produces
separate `.db` files. Results are compared across
all (model × chunk_size × overlap × top_k)
combinations.

Models can be specified as:
- CLI comma-separated names (local models)
- YAML config file with per-model endpoints:

```yaml
models:
  - name: BAAI/bge-m3
    mode: auto
  - name: nomic-embed-text-v1.5
    mode: api
    api_url: https://vllm-nomic/v1/embeddings
```

### Evaluation metrics

Three levels, user-selectable:

**Level 1 — Embedding (no LLM, no ground truth):**
- `score_spread`: max - min score (discrimination)
- `source_diversity`: unique sources / k (redundancy)
- `result_diversity`: inter-result dissimilarity

**Level 2 — Retrieval (with ground truth):**
- `hit`: relevant doc in top-k?
- `word_overlap`: fraction of GT words found
- `mrr`: rank of first relevant result

**Level 3 — LLM-based (RAGAS, optional):**
- faithfulness, context_recall, answer_correctness

See `eval.py:compute_embedding_metrics()`,
`eval.py:compute_retrieval_metrics()`,
`eval.py:METRIC_LEVELS`.
