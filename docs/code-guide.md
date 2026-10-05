# Code guide — Developer reference

This document explains the implementation of each
module. For design rationale, see
[`architecture.md`](architecture.md). For
configuration, see
[`configuration.md`](configuration.md).

## store.py — SQLite + sqlite-vec storage backend

Manages all database operations: table creation,
chunk insertion, vector search, model validation,
and bibliographic source metadata.

### Public API

| Function | Signature | Purpose |
|----------|-----------|---------|
| `open_db` | `(path: str) -> Connection` | Open SQLite, load sqlite-vec extension |
| `create_tables` | `(db, model_name, model_dim, chunk_size?, chunk_overlap?)` | Create all tables + populate meta |
| `validate_model` | `(db, model_name, model_dim)` | Raise if model/dim mismatch |
| `upsert_source` | `(db, source_file, title?, author?, ...)` | Insert or merge bibliographic metadata |
| `get_source` | `(db, source_file) -> dict\|None` | Get one source's metadata |
| `get_all_sources` | `(db) -> list[dict]` | Get all sources metadata |
| `insert_chunk` | `(db, chunk_id, source_file, chunk_index, content, embedding)` | Insert one chunk + vector |
| `insert_chunks` | `(db, chunks, embeddings)` | Batch insert |
| `delete_source_chunks` | `(db, source_file)` | Delete all chunks for a source |
| `set_source_hash` | `(db, source_file, content_hash)` | Store content hash for sync |
| `get_source_hashes` | `(db) -> dict[str, str]` | Get all content hashes |
| `search` | `(db, query_embedding, top_k=5, ...) -> list[dict]` | KNN search with hybrid/reranking |
| `list_sources` | `(db) -> list[dict]` | Files with chunk counts |

### Extension loading pattern (`open_db`)

```python
def open_db(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    return db
```

`enable_load_extension` is toggled on/off to
minimize the window where arbitrary extensions
could be loaded. `sqlite_vec.load()` uses the
bundled `vec0` binary from the `sqlite-vec` PyPI
package — no system-level installation needed.

### Rowid synchronization pattern (`insert_chunk`)

The critical pattern that links the regular
`chunks` table to the `chunks_vec` virtual table:

```python
cur = db.execute(
    "INSERT OR IGNORE INTO chunks(...) VALUES (...)",
    (chunk_id, source_file, chunk_index, content),
)
if cur.rowcount > 0:
    db.execute(
        "INSERT INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
        (cur.lastrowid, serialize_float32(embedding)),
    )
```

**Why `cur.rowcount > 0`?** When `INSERT OR
IGNORE` encounters a duplicate `id`, the row is
not inserted and `cur.rowcount` is 0. In that
case `cur.lastrowid` would return the rowid of
the *previous* insert, not the duplicate — so
inserting into `chunks_vec` with a stale rowid
would corrupt the index. The guard prevents this.

**Why `serialize_float32`?** sqlite-vec expects
embeddings as binary BLOBs (packed `float32`
values), not JSON arrays. `serialize_float32`
from the `sqlite_vec` package does
`struct.pack("%sf" % len(vector), *vector)` —
compact and fast.

### Upsert source with COALESCE (`upsert_source`)

```python
db.execute(
    "INSERT INTO sources(...) VALUES (?, ...) "
    "ON CONFLICT(source_file) DO UPDATE SET "
    "title=COALESCE(excluded.title, sources.title), "
    ...
)
```

`COALESCE(excluded.title, sources.title)` means:
use the new value if provided, otherwise keep the
existing one. This allows incremental enrichment
— a manifest can set `title` and `author`, then
a later call can add `url` without overwriting
the existing fields.

### Search with INNER JOIN (E1.05)

```python
WITH knn AS (
    SELECT rowid, distance
    FROM chunks_vec
    WHERE embedding MATCH ?
    ORDER BY distance
    LIMIT ?
)
SELECT c.content, c.source_file, knn.distance,
       s.title, s.author, s.url, s.license
FROM knn
JOIN chunks c ON c.rowid = knn.rowid
LEFT JOIN sources s ON s.source_file = c.source_file
ORDER BY knn.distance
```

`knn → chunks` uses INNER JOIN: orphan vectors
(rowid in chunks_vec without matching chunk row)
are excluded — prevents NULL content reaching the
reranker. `chunks → sources` remains LEFT JOIN
because sources metadata is optional.

### Model dimension validation (`create_tables`)

```python
if not isinstance(model_dim, int) or model_dim <= 0:
    raise ValueError(...)
```

`model_dim` is interpolated into DDL via f-string
(`float[{model_dim}]`). This validation
prevents SQL injection and malformed vec0 tables
from non-positive dimensions.

### Edge cases

- **Duplicate chunk IDs**: silently ignored via
  `INSERT OR IGNORE` — idempotent ingestion
- **Missing sources table in old DBs**: the
  `LEFT JOIN sources` returns `NULL` metadata fields
- **Orphan vectors**: INNER JOIN on chunks excludes
  vec rows without matching chunk (E1.05)
- **Concurrent reads**: safe on the same
  connection (SQLite serializes writes)
- **Zero-dimension model**: caught by validation

---

## embedder.py — Embedding engine with GPU/API/CPU fallback

Manages embedding model loading, hardware
capability assessment, and vector generation
across three backends.

### Public API

| Name | Type | Purpose |
|------|------|---------|
| `assess_gpu()` | function | Evaluate GPU VRAM, compute capability |
| `assess_cpu()` | function | Evaluate available RAM |
| `Embedder(model_name, mode, api_url, api_model)` | class | Main embedding interface |
| `Embedder.embed(text) -> list[float]` | method | Single text embedding |
| `Embedder.embed_batch(texts) -> list[list[float]]` | method | Batch embedding |
| `Embedder.model_dim -> int` | property | Embedding dimension |
| `Embedder.assess() -> dict` | method | Full backend assessment |

### torch import guard

```python
try:
    import torch
except ImportError:
    torch = None
```

torch is a heavy dependency (~2 GB). The module
works without it when `mode="api"` — only the
API backend is used. The guard allows importing
`embedder.py` even when torch is not installed.
`assess_gpu()` checks `torch is None` before
calling any CUDA API.

### VRAM decision tree (`assess_gpu`)

```python
free, total = torch.cuda.mem_get_info(0)
major, _ = torch.cuda.get_device_capability(0)
supports_fp16 = major >= 7  # Volta architecture (2017+)

if free_gb >= FP32_VRAM_GB:      # 2.8 GB
    → float32
elif free_gb >= FP16_VRAM_GB and supports_fp16:  # 1.5 GB
    → float16
else:
    → unavailable + actionable message
```

The thresholds are module constants derived from
the actual bge-m3 model size (2.1 GB FP32 on
disk, measured from cached model files) plus ~30%
overhead for inference buffers.

**Actionable messages**: when GPU is unavailable,
the message tells the user what to do:
`"NVIDIA RTX 500 Ada: 1.3/3.7 GB VRAM free,
need 1.5 GB minimum. Try freeing VRAM (close
GPU-heavy applications)."` This follows the
Platform posture — help consumers solve problems.

### RAM detection fallback chain (`assess_cpu`)

```python
def _get_available_ram_gb() -> float:
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024**2)
    except OSError:
        pass
    try:
        import psutil
        return psutil.virtual_memory().available / (1024**3)
    except ImportError:
        return 0.0
```

Linux-first (`/proc/meminfo`), then `psutil`
fallback for other platforms, then 0.0 (safe
default — will report CPU unavailable).
`MemAvailable` is used, not `MemFree` — it
includes reclaimable memory (buffers, cache).

### Lazy loading pattern (`_ensure_loaded`)

```python
def _ensure_loaded(self) -> None:
    if self._model is not None:
        return
    if self.mode == "api":
        return
    self._load_local_model()
```

The model is not loaded at `__init__()`. This
is called by `embed()`, `embed_batch()`, and
`model_dim` (in local mode). In API mode, the
model is never loaded — `_embed_api()` uses
httpx directly.

### API dimension probe (`model_dim` property)

```python
@property
def model_dim(self) -> int:
    if self.mode == "api":
        if self._api_dim is None:
            self._api_dim = self._probe_api_dim()
        return self._api_dim
    self._ensure_loaded()
    return self._model.get_embedding_dimension()

def _probe_api_dim(self) -> int:
    result = self._embed_api(["test"])
    return len(result[0])
```

In API mode, there is no local model to query
for the dimension. A test embedding call
determines the dimension. The result is cached
in `_api_dim` to avoid repeated API calls.

### SSL verification (`_get_api_verify`)

```python
def _get_api_verify(self):
    if self.api_ca_bundle:
        return self.api_ca_bundle
    return self.api_verify
```

`httpx.post(verify=...)` accepts `bool` or a
path string. When `api_ca_bundle` is set in
config.yaml, it takes precedence (returns the
path). Otherwise `api_verify` controls
verification on/off.

### Edge cases

- **No torch installed**: `assess_gpu()` returns
  `available: False`, API mode still works
- **No CUDA GPU**: same, falls back to CPU in
  auto mode
- **API endpoint unreachable**: `_probe_api`
  catches all exceptions, returns `False`
- **Self-signed certificates**: `api_verify: false`
  in config.yaml disables verification
- **FP16 on old GPU**: compute capability < 7
  means no FP16 support — falls to unavailable
  even with enough VRAM

---

## collections.py — Collection path utilities

Provides path resolution for `.db` collection
files. Multi-collection logic (discovery, cross-
corpus search, glob patterns) is implemented
directly in `server.py` via `_resolve_collections`.

### Public API

| Function | Signature | Purpose |
|----------|-----------|---------|
| `collection_db_path` | `(db_dir, name) -> str` | Full path to `name.db` |

---

## recipe.py — Recipe parsing and metadata extraction

Parses YAML recipe files (renamed from manifest
in E12.93) and extracts bibliographic metadata
from Markdown front matter when no recipe is
available.

### Public API

| Function | Signature | Purpose |
|----------|-----------|---------|
| `parse_recipe` | `(recipe_path) -> dict` | Parse YAML recipe file |
| `resolve_source_fields` | `(source) -> dict` | Resolve file/path/url from source entry |
| `extract_source_metadata` | `(text, filename) -> dict` | Extract biblio from Markdown |
| `expand_directory_entries` | `(recipe, base_dir) -> dict` | Expand glob patterns in sources |
| `scan_directory` | `(docs_dir) -> dict` | Auto-generate recipe from directory scan |

### Recipe format (`parse_recipe`)

```python
def parse_recipe(recipe_path: str) -> dict:
    with open(recipe_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {
        "collection": data.get("collection", ""),
        "level": data.get("level", ""),
        "sources": data.get("sources", []),
    }
```

Minimal extraction — only the three fields
that lore-mcp uses. Additional keys in the YAML
are silently ignored, allowing recipes to carry
consumer-specific metadata without breaking
lore-mcp.

Expected input format:
```yaml
collection: docs-libre
level: libre
sources:
  - file: intro.md
    title: Introduction
    author: RC
    license: CC-BY-SA-4.0
```

### Source field resolution (`resolve_source_fields`)

Resolves a source entry dict into a normalized
form with `file`, `path`, and optional metadata
fields. Handles multiple input forms: explicit
`file:` key, `url:` key (for remote sources),
or directory entries.

### Metadata extraction cascade (`extract_source_metadata`)

```python
def extract_source_metadata(text, filename):
    meta = {"title": None, "author": None, ...}
    fm = _extract_front_matter(text)
    if fm:
        meta["title"] = fm.get("title")
        ...
    if not meta["title"]:
        heading = _extract_first_heading(text)
        ...
    if not meta["title"]:
        meta["title"] = Path(filename).stem
    return meta
```

Three-level cascade for title:
1. YAML front matter (`---\ntitle: ...\n---`)
2. First `#` heading in the Markdown
3. Filename stem (e.g. `my-doc.md` → `my-doc`)

### Front matter regex (`_extract_front_matter`)

```python
match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
```

`^---` must be at the start of the text (not
just the start of a line). `re.DOTALL` makes
`.` match newlines so the front matter can span
multiple lines. `(.*?)` is non-greedy to match
the first closing `---`, not the last.

`yaml.safe_load` is used (not `yaml.load`) to
prevent arbitrary code execution from malicious
YAML.

### Edge cases

- **No front matter, no heading**: title defaults
  to filename stem
- **Malformed YAML front matter**: `yaml.YAMLError`
  caught, returns `None` — falls through to
  heading/filename
- **Front matter not at start**: not matched —
  some Markdown files have `---` used as
  horizontal rules mid-document
- **Empty recipe sources list**: returns empty
  `sources: []`

---

## server.py — MCP server and CLI entry point

Exposes 18 MCP tools to clients and provides the
CLI entry point with 10 subcommands.

### MCP tools (18)

| Tool | Params | Purpose |
|------|--------|---------|
| `search_docs` | `query, top_k=5, collection="", filter=""` | Semantic search with hybrid/reranking |
| `list_indexed_sources` | `collection="", detail=False, format=""` | List files with chunk counts and biblio |
| `list_collections` | (none) | List available `.db` collections |
| `lint_source` | `path` | Analyze source quality |
| `add_source` | `file, collection="", url="", ...` | Preprocess + index a single file |
| `add_sources` | `sources_json, collection="", ...` | Batch add from JSON array |
| `add_recipe` | `recipe, build_dir="", ...` | Add all sources from a recipe YAML |
| `remove_source` | `source, collection=""` | Remove a source and its chunks |
| `start_eval` | `build_dir, num_questions=50` | Launch eval in background |
| `start_optimize` | `recipe, build_dir` | Launch optimization in background |
| `get_config` | (none) | Active configuration (YAML, secrets masked) |
| `get_version` | `deps=False` | Version and dependency info |
| `get_service_status` | (none) | Inference services state |
| `get_task_status` | `task_id` | Background task progress |
| `cancel_task` | `task_id` | Cancel a running task |
| `list_tasks` | (none) | All background tasks |
| `list_pipeline_state` | (none) | Pipeline state entries |
| `purge_pipeline_state` | `state_id="", older_than=0, all=False` | Delete pipeline state |

### Formatting helpers

| Function | Purpose |
|----------|---------|
| `format_search_results(results, backend)` | Format KNN results as LLM-readable text |
| `format_sources(sources)` | Format source listing as text |

### Module-level state and thread safety

The server maintains three cached objects:

```python
_embedder = None
_db_cache: dict = {}
_init_lock = threading.Lock()
_config = None
```

`_db_cache` is a dict keyed by collection name —
each collection gets its own cached connection.
The lock prevents race conditions under SSE
transport where concurrent requests could both
see `None` and create duplicate instances.

### Configuration pattern (`_get_config`)

```python
def _get_config():
    global _config
    if _config is None:
        from lore_mcp.config import LoreConfig
        _config = LoreConfig.defaults()
    return _config
```

All config is via `LoreConfig` — no env vars.
The config is set during `main()` from
`config.yaml`; defaults are used if no config
file is provided.

### Database cache pattern (`_get_db`)

```python
def _get_db(collection: str = "") -> Connection:
    cfg = _get_config()
    name = collection or cfg.default_collection
    db_path = str(cfg.collection_db(name))
    with _init_lock:
        if name not in _db_cache:
            _db_cache[name] = open_db(db_path)
    return _db_cache[name]
```

Unified pattern for all collections — no
separate single/multi modes. Collection glob
patterns (`collection="*"` or `"ai-*"`) are
resolved by `_resolve_collections()`.

### Embedder lazy init (`_get_embedder`)

The embedder is created on first search query,
not at startup. This allows the MCP server to
start instantly and defer the potentially slow
model loading (GPU detection, API probe).

### search_docs flow

1. Lazy-load the embedder
2. Embed the query text
3. If collection is a glob pattern:
   resolve to matching collection names,
   search each, merge results by score
4. Otherwise: `_get_db(collection)` →
   `validate_model()` → `search()`
5. Format and return as text

### format_search_results

Builds LLM-optimized output with bibliographic
metadata when available:

```python
biblio_parts = []
if r.get("title"):
    biblio_parts.append(f"Title: {r['title']}")
if r.get("author"):
    biblio_parts.append(f"Author: {r['author']}")
if r.get("license"):
    biblio_parts.append(f"License: {r['license']}")
```

Fields are conditionally included — old .db files
without a `sources` table return `None` for these
fields, and the output degrades gracefully to
just `[source_file] (score: X.XXXX)`.

### CLI subcommands (`main`)

`main()` uses `argparse` with subparsers:

- No subcommand → `mcp.run(transport=...)` (MCP server)
- `eval` → evaluate retrieval quality
- `optimize` → optimize chunk/model params
- `build` → full pipeline (recipe → .db)
- `preprocess` → clean and normalize sources
- `enrich` → LLM enrichment on preprocessed files
- `lint` → analyze source quality
- `init` → generate bootstrap config.yaml
- `version` → show version and deps
- `state` → manage pipeline state

The `build` subcommand takes an optional recipe
argument:

```python
build_parser.add_argument("recipe", nargs="?")
build_parser.add_argument("--orig-dir")
build_parser.add_argument("--build-dir")
build_parser.add_argument("--skip-optimize", action="store_true")
build_parser.add_argument("--allow-download", action="store_true")
build_parser.add_argument("--force", action="store_true")
```

### Edge cases

- Empty query string: `embedder.embed("")` works
  but returns low-quality embeddings — no
  validation (acceptable, the LLM client is
  responsible)
- Empty data directory: search returns `[]`,
  formatted as "0 results."
- Collection glob with no matches: returns
  "No matching collections."
- Write operations (`add_source`, `remove_source`)
  use separate db connections and invalidate
  the cache via `_invalidate_db()` after.

### Dependencies

- `mcp.server.MCPServer` — MCP SDK v2
- `lore_mcp.config` — `LoreConfig`
- `lore_mcp.collections` — `collection_db_path()`
- `lore_mcp.embedder` — query-time embedding
- `lore_mcp.store` — database operations
- `lore_mcp.task_manager` — background tasks
- `lore_mcp.eval` — eval/optimize (lazy import)
- `lore_mcp.build` — build workflow (lazy import)
- `lore_mcp.preprocess` — preprocessing (lazy)

---

## ingest.py — Ingestion pipeline

Chunks and indexes preprocessed Markdown files
into SQLite with recipe-driven bibliographic
metadata.

### Public API

| Function | Purpose |
|----------|---------|
| `ConsecutiveErrorThreshold` | Stop build after N consecutive failures |
| `get_batch_size(config?)` | Read embedding batch size from config |
| `chunk_document(text, source_file, ...)` | Split text via Docling HybridChunker |
| `ingest_source(db_path, md_file, embedder, ...)` | Add a single source to existing .db |
| `ingest_directory(dir_path, db_path, embedder, ...)` | Index a directory of .md files |
| `ingest_with_manifest(recipe_path, docs_dir, db_dir, embedder, ...)` | Recipe-driven indexing |

### Constants

```python
DEFAULT_CHUNK_SIZE = 1024
DEFAULT_CHUNK_OVERLAP = 128
EMBED_BATCH_SIZE = 32
MIN_DOC_LENGTH = 100
```

`DEFAULT_CHUNK_SIZE` was changed from 2048 to
1024 in E6.04, based on AutoRAG benchmark results.

`MIN_DOC_LENGTH` (100 chars) skips trivially short
documents that would produce meaningless chunks.

### Chunking via Docling HybridChunker (`chunk_document`)

```python
def chunk_document(text, source_file,
                   chunk_size=1024, chunk_overlap=128):
    converter = DocumentConverter()
    doc = converter.convert(tmp_path).document
    chunker = HybridChunker(max_tokens=chunk_size // 4)
    doc_chunks = list(chunker.chunk(doc))
```

Text is loaded into the Docling Markdown backend
to get a structured `DoclingDocument`, then
chunked with `HybridChunker` which preserves
table boundaries and heading context. Headings
are stored in chunk metadata.

### Deterministic chunk IDs (`chunk_document`)

```python
chunk_id = hashlib.sha256(
    f"{source_file}:{i}:{c.text[:64]}".encode()
).hexdigest()[:16]
```

Three components make the ID:
- `source_file` — file-level uniqueness
- `i` — position within file
- `c.text[:64]` — content-based (detects edits)

Truncated to 16 hex chars (64 bits). This enables
idempotent ingestion: `INSERT OR IGNORE` in
`store.py:insert_chunk()` skips already-indexed
chunks.

### Incremental ingest (`ingest_source`)

Adds a single source to an existing `.db`. Reads
chunk params from the `.db` meta table to ensure
consistency:

```python
def ingest_source(db_path, md_file, embedder,
                  source_meta=None, db=None):
    validate_model(db, embedder.model_name, ...)
    meta = dict(db.execute("SELECT key, value FROM meta")...)
    chunk_size = int(meta.get("chunk_size", DEFAULT_CHUNK_SIZE))
```

Used by the `add_source` MCP tool for incremental
indexing without rebuilding the entire collection.

### Batch embedding (`_ingest_file`)

```python
for batch_start in range(0, len(chunks), batch_size):
    batch = chunks[batch_start : batch_start + batch_size]
    texts = [c["content"] for c in batch]
    embeddings = embedder.embed_batch(texts)
    insert_chunks(db, batch, embeddings)
```

Chunks are embedded in batches of 32. Each batch
is committed to the database immediately. A crash
mid-ingestion loses at most 32 chunks, not the
entire run.

### Declarative sync (`ingest_with_manifest`)

Recipe-driven entry point with declarative sync:
- Computes content hashes for all sources
- Skips unchanged files (hash match)
- Re-indexes changed files (hash mismatch)
- Purges absent files (not in recipe)
- Full rebuild = empty DB or `--force`

Per-file error handling ensures a single corrupt
file doesn't abort the entire run. Errors are
collected in the return dict, not raised.

### Dependencies

- `docling` + `docling_core` — `DocumentConverter`,
  `HybridChunker`
- `lore_mcp.collections` — `collection_db_path()`
- `lore_mcp.recipe` — `parse_recipe()`,
  `extract_source_metadata()`
- `lore_mcp.preprocess` — `clean_text()`
- `lore_mcp.store` — all database operations
- `lore_mcp.embedder` — `Embedder` type hint

---

## metadata.py — Collection output files

Generates `.json`, `.bib`, and `.md` metadata
files alongside each `.db` collection file.

### Public API

| Function | Line | Purpose |
|---|---|---|
| `generate_collection_json(db_path)` | 11 | Machine-readable metadata |
| `generate_collection_bib(db_path)` | 48 | BibTeX bibliography |
| `generate_collection_md(db_path)` | 75 | Human-readable description |
| `generate_all(db_path)` | 132 | Generate all three files |

### generate_collection_json

Reads the `meta` table and `sources` table,
computes a SHA-256 checksum of the .db file,
and writes a JSON file:

```python
sha256 = hashlib.sha256(db_file.read_bytes()).hexdigest()
```

The SHA-256 checksum covers the entire .db file.
This allows consumers to verify integrity after
download. The checksum is computed on the binary
content, not on the SQL data.

The output includes:
- `collection` — derived from the filename stem
- `model_name`, `model_dim` — from meta table
- `chunk_size`, `chunk_overlap` — from meta table
  (may be `null` for old .db files)
- `stats` — file count, chunk count, db size
- `sources` — full bibliographic metadata, with
  null values filtered out

### generate_collection_bib

BibTeX generation without any external dependency.
Each source becomes a `@misc` entry:

```python
key = Path(s["source_file"]).stem.replace(" ", "_").replace("-", "_")
```

The citation key is derived from the filename,
with spaces and hyphens replaced by underscores
for BibTeX compatibility.

Fields are conditionally included — a source
without an author simply omits the `author`
field. The `note` field carries the license
information.

The `year` field is extracted from the `date`
string:
```python
f"  year = {{{s['date'][:4] if len(s['date']) >= 4 else s['date']}}}"
```

### generate_collection_md

Human-readable Markdown. Includes a **gris
warning** when any source has
`level == "gris"`:

```python
if any(s.get("level") == "gris" for s in biblio):
    lines.extend([
        "## Notice",
        "Some sources in this collection have uncertain "
        "redistribution rights (level: gris)...",
    ])
```

This implements the "plaidoyer de bonne foi"
required by the openshift sync for gris-level
collections.

### Edge cases

- Old .db files without `chunk_size` in meta:
  outputs `"unknown"`
- Sources with no metadata fields: falls back
  to `source_file` as title
- Empty sources table: produces valid but empty
  bibliography sections

### Dependencies

- `lore_mcp.store` — `open_db()`,
  `get_all_sources()`, `list_sources()`
- Standard library only (hashlib, json, datetime,
  pathlib)

---

## eval.py — RAG evaluation and optimization

Evaluates retrieval quality and optimizes
chunking parameters, with optional RAGAS
integration for LLM-based scoring.

### Public API

| Function/Class | Purpose |
|---|---|
| `METRIC_LEVELS` | Dict of metric names by level (embedding, retrieval, ragas) |
| `check_ragas_guard(metrics, judge_url, judge_model, verify_ssl)` | Bidirectional guard: warn if judge unused, error if RAGAS without judge |
| `validate_metrics_prerequisites(metrics, judge_url, judge_model, verify_ssl)` | Fail fast if RAGAS metrics requested but prerequisites missing |
| `_probe_judge(url, timeout, verify)` | HTTP probe — fail fast if judge LLM unreachable |
| `compute_embedding_metrics(results)` | Level 1: score_spread, source_diversity (no LLM needed) |
| `_word_overlap(text_a, text_b)` | Word-level overlap ratio: \|A ∩ B\| / \|A\| |
| `compute_retrieval_metrics(contexts, gt)` | Level 2: hit, word_overlap, mrr, ndcg@5, recall@5 |
| `ndcg_at_k(relevances, k)` | Normalized Discounted Cumulative Gain at k |
| `recall_at_k(relevances, total_relevant, k)` | Recall at k: fraction of relevant items found in top-k |
| `parse_model_configs(config_path)` | Parse YAML model config file |
| `EvalConfig` | Configuration dataclass |
| `EvalConfig.from_config(config)` | Read config from LoreConfig |
| `generate_questions_from_sources(docs_dir, num_questions)` | Heading-based QA pairs from markdown source files (pre-chunking) |
| `generate_questions_from_db(db_path, n, llm)` | Extractive questions from indexed chunks (fallback) |
| `_is_good_sentence(s)` | Filter garbage sentences: min alpha ratio, min word count, skip headers |
| `_RagasEmbeddingsWrapper(embedder)` | Adapts lore-mcp Embedder to RAGAS embeddings interface |
| `evaluate_retrieval(db_path, embedder, questions, top_k)` | Score retrieval quality |
| `generate_eval_report(results, path)` | Write JSON report |
| `run_eval(db_path, embedder, config, output_path)` | Full eval pipeline |
| `_optimize_ingest(...)` | Deterministic ingestion for one optimization config |
| `run_optimize(embedder, embedders, db_dir, ...)` | Multi-model parameter optimization |

### EvalConfig

```python
@dataclass
class EvalConfig:
    llm_url: str
    llm_model: str
    num_questions: int = 50
    top_k: int = 5
    verify_ssl: bool = True
```

`from_config()` reads from a `LoreConfig`
instance. All config comes from `config.yaml`.

### Question generation

Three strategies, in priority order:

1. **Heading-based** (`generate_questions_from_sources`):
   Primary strategy (E10.27). Parses markdown source
   files, extracts `## heading` → section content
   pairs. The heading becomes the query, the section
   content is the ground truth. Independent of
   chunking — eliminates config bias. Only used
   when `docs_dir` is available.

2. **Extractive** (`_generate_extractive`):
   Fallback when source docs are unavailable.
   Selects random chunks, extracts the longest
   good sentence as both query and ground truth.
   `_is_good_sentence()` filters garbage: min 30
   chars, min 5 words, min 50% alpha ratio, skips
   markdown headers and frontmatter.

3. **RAGAS** (`_generate_with_ragas`):
   Uses `TestsetGenerator` from the ragas package.
   Requires an LLM and the optional `[eval]`
   dependency. Falls back to extractive on
   `ImportError`.

`run_optimize` prefers heading-based, falls back
to extractive. `run_eval` uses extractive from
the indexed chunks.

### Retrieval scoring

`evaluate_retrieval()` runs the full
question→embed→search→score loop:

```python
for q in questions:
    query_emb = embedder.embed(q["question"])
    results = search(db, query_emb, top_k=top_k)
    retrieved_contexts = [r["content"] for r in results]
    scores = compute_retrieval_metrics(retrieved_contexts, ground_truth)
```

`compute_retrieval_metrics()` computes five
metrics using `_word_overlap()` with
`RELEVANCE_THRESHOLD = 0.3`:

- **hit**: 1.0 if any retrieved chunk has
  word_overlap ≥ threshold with ground truth
- **word_overlap**: best overlap ratio across
  all retrieved chunks
- **mrr**: reciprocal rank of the first relevant
  chunk (1.0 = first position)
- **ndcg@5**: Normalized Discounted Cumulative
  Gain — position-weighted relevance (standard
  IR metric, BEIR default)
- **recall@5**: fraction of relevant chunks
  found in top-5

A chunk is "relevant" when its word overlap
with the ground truth exceeds the threshold:

```python
overlaps = [_word_overlap(ground_truth, ctx) for ctx in contexts]
relevances = [1.0 if ov >= RELEVANCE_THRESHOLD else 0.0 for ov in overlaps]
```

### Model specificity

Both `evaluate_retrieval()` and `run_optimize()`
include `model_name` in the output. This ensures
reports are traceable — scores
are only comparable across runs with the same
embedding model.

### _optimize_ingest (helper)

Deterministic ingestion for one optimization
configuration. Produces `opt-<size>-<overlap>.db`
in the working directory.

```python
def _optimize_ingest(db_dir_path, recipe_path,
                     docs_dir, embedder,
                     chunk_size, chunk_overlap) -> str:
    db_name = f"opt-{chunk_size}-{chunk_overlap}"
    db_path = str(db_dir_path / f"{db_name}.db")
    # ... ingest, rename if recipe used
    return db_path
```

When a recipe is used, `ingest_with_manifest`
creates a `.db` named after the collection.
`_optimize_ingest` renames it to the
deterministic name to avoid collisions between
iterations (E10.06 fix).

### run_optimize (multi-model)

The optimization loop supports single or multiple
embedding models via the `embedders` dict
(name→Embedder):

1. Index with the first model and first config
   via `_optimize_ingest()`
2. Generate questions once from that index
3. For each model:
   For each (chunk_size, overlap, top_k):
     a. `_optimize_ingest()` — deterministic .db
     b. Evaluate retrieval on the same questions
     c. Record average score with `model_name`
4. Return best config across all combinations

```python
for model_name, emb in embedders.items():
    for cs in chunk_sizes:
        for co in chunk_overlaps:
            db_path = _optimize_ingest(...)
            for tk in top_ks:
                result = evaluate_retrieval(...)
```

### Embedding metrics (level 1)

`compute_embedding_metrics()` computes metrics
that need no LLM or ground truth:

```python
def compute_embedding_metrics(results):
    scores = [r["score"] for r in results]
    sources = [r["source_file"] for r in results]
    return {
        "score_spread": max(scores) - min(scores),
        "source_diversity": len(set(sources)) / len(results),
        "result_diversity": 0.0,
    }
```

### Retrieval metrics (level 2)

`compute_retrieval_metrics()` uses word overlap
to determine relevance (threshold 0.3), then
computes five metrics:

```python
def compute_retrieval_metrics(contexts, ground_truth):
    overlaps = [_word_overlap(ground_truth, ctx) for ctx in contexts]
    relevances = [1.0 if ov >= RELEVANCE_THRESHOLD else 0.0 for ov in overlaps]
    # ... hit, word_overlap, mrr from relevances ...
    return {"hit": ..., "word_overlap": ..., "mrr": ...,
            "ndcg@5": ndcg_at_k(relevances, k=5),
            "recall@5": recall_at_k(relevances, ...)}
```

### Model config parsing

Model configurations are read from the
`embedding:` section of the config YAML:

```python
parse_model_configs("config.yaml")
# → [{"name": "nomic-v2", "mode": "builtin"}, ...]
```

### Edge cases

- No chunks in database: `generate_questions_from_db()`
  returns `[]`, and `evaluate_retrieval()` returns
  empty scores
- Ground truth is empty: `compute_retrieval_metrics()`
  returns zeros for all metrics — no crash
- All scores zero: `_average_scores()` handles
  this correctly (returns 0.0 for all metrics)
- RAGAS not installed: extractive fallback, no
  error

### Dependencies

- `lore_mcp.store` — `open_db()`, `search()`
- `lore_mcp.ingest` — `ingest_directory()`,
  `ingest_with_manifest()` (lazy import in
  `run_optimize`)
- `lore_mcp.recipe` — `parse_recipe()` (in
  `_optimize_ingest`)
- `yaml` — model config parsing
- `ragas` — optional, for LLM-based scoring
  and question generation
- Standard library (json, random, dataclasses,
  datetime, pathlib)

---

## progress.py — Output management

Controls console output across 5 levels:
quiet, progress, default, verbose, debug.
See `docs/architecture.md`.

### Public API

| Function/Class | Purpose |
|---|---|
| `configure_logging(level)` | Set log levels: `lore_mcp` at DEBUG, third-party at WARNING (debug mode); root at ERROR (quiet); root at WARNING (default/verbose/progress) |
| `output_level_from_args(args)` | Map CLI flags (`--quiet`, `--progress`, `--verbose`, `--debug`) to level string |
| `_fmt_duration(seconds)` | Human-readable duration: `45s`, `1m30s`, `1h01m` |
| `ProgressReporter(collection, models, total_configs, level, phases)` | Structured output adapted to the current level |

### ProgressReporter levels

- **quiet**: all output suppressed
- **progress**: single `\r` line with global %,
  ETA, phase number, sub-progress, model name
- **default**: boxed header, sections, results
  table with ★, summary table
- **verbose**: default + questions table
  (truncated), per-iteration milestones with
  score breakdown
- **debug**: verbose + all `logger.debug()` from
  `lore_mcp.*` modules (HTTP requests, search
  results, scores)

### Phase tracking

`begin_phase(name)` advances the phase counter
and resets the phase timer. The progress line
uses phase position to calculate global ETA:

```
77% ETA 3s | 3/3 Optimization [12/36] 33% ETA 20s nomic-embed
```

### Logging strategy

`configure_logging()` sets `lore_mcp` logger at
DEBUG while keeping third-party loggers (httpx,
httpcore, sentence_transformers, huggingface_hub,
numexpr, transformers) at WARNING. httpx is set
to INFO in debug mode to show `HTTP Request:`
summary lines.

---

## build_config.py — Unified build configuration

**Purpose:** Parse a single YAML file containing
all build parameters (embedding models, judge LLM,
metrics, optimization params).

### Public API

| Function | Signature | Line |
|----------|-----------|------|
| `BuildConfig.from_file` | `(path) -> BuildConfig` | classmethod |
| `BuildConfig.from_env` | `() -> BuildConfig` | classmethod |

### BuildConfig fields

```python
@dataclass
class BuildConfig:
    embedding_models: list[dict]
    judge_model: str
    judge_api_url: str
    judge_verify_ssl: bool
    metrics: list[str]
    chunk_sizes: list[int]
    chunk_overlaps: list[int]
    top_ks: list[int]
    num_questions: int
```

### from_file parsing

Reads a YAML file with sections `embedding_models`,
`judge`, `metrics`, `optimize`. Missing sections
use defaults.

Note: `BuildConfig` is a legacy module from the
early build workflow. Most of its functionality
is now handled by `LoreConfig` in `config.py`.

### Dependencies

- `yaml` — YAML parsing (pyyaml, transitive dep)

---

## build.py — Build workflow

Orchestrates the full pipeline from recipe to
optimized .db with metadata files. The single
entry point for production use.

### Public API

| Function | Line | Purpose |
|---|---|---|
| `validate_models(configs, embedders)` | 21 | Pre-flight: check all models are accessible |
| `run_build(recipe_path, docs_dir, output_dir, ...)` | Full pipeline: validate → optimize → index → metadata |

### validate_models

Checks every model config before heavy work
begins. Returns a list of error strings (empty
= all OK):

```python
def validate_models(configs, embedders=None):
    errors = []
    for cfg in configs:
        if mode == "api":
            if not _probe_api(url, ...):
                errors.append(f"{name}: API endpoint unreachable ({url})")
        elif embedders and name in embedders:
            pass  # already instantiated
        else:
            cache_path = Path.home() / ".cache" / "huggingface" / "hub" / f"models--{name.replace('/', '--')}"
            if not cache_path.exists():
                errors.append(f"{name}: not in HuggingFace cache, use --allow-download")
    return errors
```

Three validation paths:
- **API mode**: probe the endpoint with `_probe_api`
- **Pre-instantiated**: embedder already in the
  `embedders` dict (trusted)
- **Local model**: check HuggingFace cache directory
  exists (avoids surprise ~2 GB downloads)

All failures collected and returned at once —
the caller decides whether to abort or proceed.

### run_build

The full pipeline:

```python
def run_build(recipe_path, docs_dir, output_dir,
              embedder=None, embedders=None,
              skip_optimize=False, ...):
    # 1. Parse recipe
    recipe = parse_recipe(recipe_path)
    collection = recipe["collection"]

    # 2. Optimize (unless --skip-optimize)
    if not skip_optimize:
        optimization = _run_optimization(...)
        winning_model = optimization["best"]["model_name"]
        winning_chunk_size = optimization["best"]["chunk_size"]
        ...

    # 3. Final index with winning config
    ingest_with_manifest(manifest_path, docs_dir,
                         output_dir, final_emb, ...)

    # 4. Generate metadata files
    generate_all(final_db)

    # 5. Write build report
    report_path.write_text(json.dumps(report, ...))
    return report
```

When `skip_optimize=True`, defaults are used
(model from first embedder, chunk_size=1024,
chunk_overlap=128).

### _run_optimization

Wraps `run_optimize()` with resumability:
- Loads existing `scores.jsonl` if present
- Delegates to `eval.py:run_optimize()` for the
  actual optimization loop
- Persists scores to `scores.jsonl` for resume

### Resumability

State is persisted in `work_dir` (default:
`<output_dir>/.build-work/`):

| File | Contents | Resume behavior |
|---|---|---|
| `opt-*.db` | Per-config test databases | Config skipped if .db exists |
| `scores.jsonl` | Per-config scores | Loaded, only missing configs run |
| `<collection>.db` | Final output | Skipped unless `--force` |

`--force` flag deletes existing state and
starts fresh.

### Edge cases

- `embedders=None` and `embedder=None`: raises
  `ValueError`
- Final `.db` already exists and not `--force`:
  skips re-indexing, only regenerates metadata
- Work directory doesn't exist: created
  automatically with `mkdir(parents=True)`
- Optimization returns empty `best`: uses
  defaults (first model, 1024/128)

### Dependencies

- `lore_mcp.eval` — `run_optimize()`
- `lore_mcp.ingest` — `ingest_with_manifest()`
- `lore_mcp.recipe` — `parse_recipe()`
- `lore_mcp.metadata` — `generate_all()`
- `lore_mcp.preprocess` — `preprocess_sources()`
- `lore_mcp.store` — `open_db()`, `list_sources()`
- `lore_mcp.embedder` — `Embedder`

---

## config.py — Unified configuration

All lore-mcp configuration is centralized in the
`LoreConfig` dataclass. No environment variable
fallback — everything comes from `config.yaml`.

### Public API

| Name | Purpose |
|------|---------|
| `LoreConfig` | Dataclass with all config fields |
| `LoreConfig.from_file(path)` | Load from YAML file |
| `LoreConfig.defaults()` | Return config with all defaults |
| `LoreConfig.data_dir` | Property: XDG-compliant data directory |
| `LoreConfig.collection_db(name)` | Resolve .db path for a collection |
| `LoreConfig.get_llm(name)` | Look up model in LLM registry by name |

### Config sections in YAML

| Section | Fields |
|---------|--------|
| `database:` | `dir`, `default_collection` |
| `embedding:` | `model`, `mode`, `api_url`, `batch_size` |
| `chunking:` | `size`, `overlap` |
| `reranking:` | `model`, `api_key` |
| `llm:` | List of model entries (name, model, api_url, api_key) |
| `enrich:` | `techniques`, `models`, `prompts_file` |
| `parse:` | `ocr_engine`, `ocr_lang`, `caption_primary`, `stt_model` |
| `optimize:` | `chunk_sizes`, `chunk_overlaps`, `top_ks`, `metrics` |

Runtime flags (`force`, `output_level`,
`allow_download`) are set by CLI args, not
config.yaml.

### LLM registry pattern

Models are declared once in the `llm:` list:

```yaml
llm:
  - name: tei
    model: nomic-embed-text-v2-moe
    api_url: http://localhost:8081/v1/embeddings
  - name: ollama
    model: granite3.3:8b
    api_url: http://localhost:11434/v1/chat/completions
```

Each pipeline section references models by name:
`embedding.model: tei`, `enrich.models: [ollama]`,
`parse.caption_primary: granite-vision`.

---

## task_manager.py — Background task management

Thread-based task manager for long-running MCP
operations (build, preprocess, eval, optimize).

### Public API

| Name | Purpose |
|------|---------|
| `TaskInfo` | Dataclass: id, name, status, progress |
| `ModelRegistry` | Resource-aware model slot manager |
| `TaskManager` | Thread-based task lifecycle |
| `report_progress(message)` | Report progress from within a task thread |

### ModelRegistry

Manages GPU/CPU/remote model slots. Lazy stop:
models stay loaded until their slot is needed by
a different model. Usage counting allows
concurrent access to the same model.

```python
reg.acquire("tei", "local_gpu", llm_entry)
# ... use model ...
reg.release("tei", llm_entry)
```

### TaskManager

Wraps `threading.Thread` with lifecycle tracking:

```python
task_id = tm.start("build", lambda: run_build(...))
info = tm.status(task_id)  # TaskInfo
tm.cancel(task_id)         # sets cancel event
```

Tasks report progress via `report_progress()`,
which stores the message in the thread's
`_task_info`. The `get_task_status` MCP tool
reads this to show phase info to the LLM.

---

## checkpoint.py — Resumable pipeline state

Manages pipeline checkpoints for long-running
preprocessing. State persists across runs in
`.work/` directories.

### Public API

| Name | Purpose |
|------|---------|
| `Checkpoint(recipe_path, config_path, force?)` | Initialize checkpoint for a pipeline run |
| `phase_hash(recipe_path, config, phase)` | Deterministic hash for phase config |
| `list_states()` | List all pipeline state entries |
| `purge_state_by_hash(hash)` | Delete one state entry |
| `purge_states(max_age_days?, purge_all?)` | Bulk cleanup |

Per-phase hashing ensures that only the affected
phases re-run when config changes — e.g. changing
enrichment params doesn't re-run parsing.

---

## lint.py — Source quality analysis

Analyzes Markdown source files for RAG readiness:
text density, heading structure, noise detection.

### Public API

| Function | Purpose |
|----------|---------|
| `analyze_file(path)` | Full quality analysis returning metrics dict |
| `lint_sources(files, force?)` | Batch analysis with quality gate |
| `format_lint_report(reports)` | Human-readable report |

### Quality metrics

- `text_density` — ratio of text to total content
- `heading_depth` — max heading level used
- `heading_ratio` — headings per KB of text
- `heading_issues` — level skips detected
- `structure_score` — 0.0–1.0 composite score
- `base64_count` — embedded images detected

### Quality gate verdict

`_compute_verdict()` maps metrics to verdicts:
`EXCELLENT`, `GOOD`, `ACCEPTABLE`, `POOR`.
`POOR` blocks indexing unless `--force` is used.

## format_registry.py — Unified format detection

Single source of truth for format detection and
backend routing. Replaces the former hardcoded
`_BACKEND_MAP` and `_MIME_TO_BACKEND` dictionaries.

### Backends

Seven backends, each a processing path that
takes a file and produces markdown:

| Backend | Formats | Handler |
|---------|---------|---------|
| `markdown` | `.md` | Passthrough |
| `html` | `.html`, `.htm` | trafilatura |
| `docling` | `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.epub`, images | Docling |
| `markitdown` | `.csv`, `.json`, `.xml` | markitdown |
| `code` | `.py`, `.js`, `.ts`, `.java`, `.go`, `.c`, etc. | Passthrough → narrate |
| `audio` | `.mp3`, `.wav`, `.flac`, etc. | STT API |
| `video` | `.mp4`, `.webm`, `.mkv`, etc. | STT + frames |

### Public API

| Method | Purpose |
|--------|---------|
| `detect(filename)` | Resolve backend: content-based (puremagic) → extension → MIME |
| `is_supported(filename)` | Fast check (no I/O) for scan filtering |
| `has_structural_parser(ext)` | True if Python ast or tree-sitter available for this code extension |
| `get_treesitter(ext)` | Return `(module, language)` tuple or None |
| `list_formats()` | Full inventory with backend and parser availability |
| `apply_config(overrides)` | Apply `parse.formats` overrides from config.yaml |

### Singleton

`get_format_registry(config)` — created once,
applies config overrides on first call. All
consumers use this singleton.

`detect_format()` in `parse.py` is kept as a
facade that delegates to the registry.

### Tree-sitter detection

At init, the registry scans for installed
`tree_sitter_*` packages and builds the
language map dynamically. No hardcoded list
of available languages — availability is
determined at runtime.

### Config overrides

Users can add or modify format mappings via
`parse.formats` in `config.yaml`:

```yaml
parse:
  formats:
    .proto: markitdown
    .txt: markdown
```

Backend must be one of the 7 known types.
Empty string removes a default mapping.

## preprocess/narrate.py — Structured data narration

Transforms raw output from structured formats
(JSON, CSV, XLSX, source code) into markdown
with headings for better chunking and search.

### Public API

`narrate_structured(text, format_hint, filename)`

Dispatches based on `format_hint`:
- `"json"` → `_narrate_json()` — JSON array of
  records → headed sections per record
- `"markitdown"` / `"docling"` → `_narrate_table()`
  — add heading to table-only content
- `"code"` → `_narrate_code()` — AST-based
  structural narration

### Code narration

`_narrate_code(text, filename)` routes by
language:

| Language | Parser | Headings |
|----------|--------|----------|
| Python | `ast` (stdlib) | Module / class / method / function |
| JS/TS, C/C++, Java, Bash | tree-sitter (optional) | Class / method / function |
| Other | fallback | h1 filename only |

**Python** (`_narrate_python`): uses `ast.parse()`
to extract module docstring (→ h1), imports
(→ h2), constants (→ h2), classes with methods
(→ h2/h3), top-level functions (→ h2). Code
is preserved in fenced code blocks. Docstrings
are extracted as prose text above the code block.

**Tree-sitter** (`_narrate_treesitter`): uses
dynamically detected tree-sitter grammars.
Extracts class and function definitions with
names and preceding comments. Same output
pattern as Python narration.

**Fallback**: `# filename` heading + entire
source in a single code block. File is still
indexed but without structural chunking.
