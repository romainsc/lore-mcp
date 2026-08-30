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
| `search` | `(db, query_embedding, top_k=5) -> list[dict]` | KNN search with biblio JOIN |
| `list_sources` | `(db) -> list[dict]` | Files with chunk counts |

### Extension loading pattern (lines 10–16)

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

### Rowid synchronization pattern (lines 155–165)

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

### Upsert source with COALESCE (lines 102–125)

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

### Search with LEFT JOIN (lines 188–223)

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
LEFT JOIN chunks c ON c.rowid = knn.rowid
LEFT JOIN sources s ON s.source_file = c.source_file
ORDER BY knn.distance
```

Two LEFT JOINs: `knn → chunks` (by rowid) and
`chunks → sources` (by source_file). The second
JOIN is LEFT because sources metadata is optional
— old `.db` files without a `sources` table, or
chunks without a corresponding source entry,
still return results with `NULL` title/author.

### Model dimension validation (lines 27–28)

```python
if not isinstance(model_dim, int) or model_dim <= 0:
    raise ValueError(...)
```

`model_dim` is interpolated into DDL via f-string
(line 31: `float[{model_dim}]`). This validation
prevents SQL injection and malformed vec0 tables
from non-positive dimensions.

### Edge cases

- **Duplicate chunk IDs**: silently ignored via
  `INSERT OR IGNORE` — idempotent ingestion
- **Missing sources table in old DBs**: the
  `LEFT JOIN sources` returns `NULL` fields
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

### torch import guard (lines 7–10)

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
calling any CUDA API (line 23).

### VRAM decision tree (lines 21–57)

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

### RAM detection fallback chain (lines 76–89)

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

### Lazy loading pattern (lines 178–184)

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

### API dimension probe (lines 134–147)

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

### SSL verification (lines 225–229)

```python
def _get_api_verify(self):
    if self.api_ca_bundle:
        return self.api_ca_bundle
    return self.api_verify
```

`httpx.post(verify=...)` accepts `bool` or a
path string. When `LORE_API_CA_BUNDLE` is set,
it takes precedence (returns the path). Otherwise
`LORE_API_VERIFY` controls verification on/off.

### Edge cases

- **No torch installed**: `assess_gpu()` returns
  `available: False`, API mode still works
- **No CUDA GPU**: same, falls back to CPU in
  auto mode
- **API endpoint unreachable**: `_probe_api`
  catches all exceptions, returns `False`
- **Self-signed certificates**: `LORE_API_VERIFY=
  false` disables verification
- **FP16 on old GPU**: compute capability < 7
  means no FP16 support — falls to unavailable
  even with enough VRAM

---

## collections.py — Multi-collection management

Routes operations across a directory of
independent `.db` files, each representing a
named collection with a license level tag.

### Public API

| Function | Signature | Purpose |
|----------|-----------|---------|
| `build_collection_name` | `(theme, level) -> str` | Construct `theme-level` name |
| `collection_db_path` | `(db_dir, name) -> str` | Full path to `name.db` |
| `discover_collections` | `(db_dir) -> list[dict]` | Scan directory, return metadata per collection |
| `search_collection` | `(db_dir, collection, query_emb, top_k)` | Search one collection |
| `search_across` | `(db_dir, query_emb, top_k)` | Search all, merge by score |

### Filename parsing (lines 23–30)

```python
def _parse_name(filename: str) -> dict:
    name = filename.removesuffix(".db")
    known_levels = {"nda", "libre", "restreint", "gris"}
    parts = name.rsplit("-", 1)
    if len(parts) == 2 and parts[1] in known_levels:
        return {"theme": parts[0], "level": parts[1]}
    return {"theme": name, "level": ""}
```

`rsplit("-", 1)` splits on the **last** hyphen,
so `ia-serving-libre` correctly parses as
theme=`ia-serving`, level=`libre`. Only the four
known levels are recognized — unknown suffixes
leave `level` empty.

### Cross-corpus merge (lines 81–100)

```python
def search_across(db_dir, query_embedding, top_k=5):
    all_results = []
    for f in Path(db_dir).glob("*.db"):
        try:
            db = open_db(str(f))
            results = search(db, query_embedding, top_k=top_k)
            db.close()
            name = f.stem
            for r in results:
                r["collection"] = name
            all_results.extend(results)
        except Exception:
            continue
    all_results.sort(key=lambda r: r["score"], reverse=True)
    return all_results[:top_k]
```

Each collection is queried independently with
the full `top_k`, so up to `N × top_k` results
are collected before the final merge and
truncation. The `try/except` per collection
ensures a corrupt `.db` file doesn't abort the
entire search.

The `collection` key is added to each result so
the caller knows which `.db` it came from.

### Discovery with meta reading (lines 33–60)

`discover_collections` opens each `.db`, reads
the `meta` table for `chunk_size`/`chunk_overlap`,
and counts chunks via `list_sources()`. This is
an O(N) scan of all `.db` files — acceptable for
< 100 collections. For larger deployments, a
directory-level cache could be added.

### Edge cases

- **Empty directory**: returns `[]`
- **Non-directory path**: returns `[]`
- **Corrupt .db file**: silently skipped in
  both `discover_collections` and `search_across`
- **Missing collection**: `search_collection`
  raises `FileNotFoundError` with the expected
  path
- **Hyphen-free filenames**: parsed with empty
  `level` (e.g. `general.db` → theme=`general`)

---

## manifest.py — Manifest parsing and metadata extraction

Parses YAML collection manifests and extracts
bibliographic metadata from Markdown front matter
when no manifest is available.

### Public API

| Function | Signature | Purpose |
|----------|-----------|---------|
| `parse_manifest` | `(manifest_path) -> dict` | Parse YAML manifest file |
| `extract_source_metadata` | `(text, filename) -> dict` | Extract biblio from Markdown |

### Manifest format (lines 9–17)

```python
def parse_manifest(manifest_path: str) -> dict:
    with open(manifest_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {
        "collection": data.get("collection", ""),
        "level": data.get("level", ""),
        "sources": data.get("sources", []),
    }
```

Minimal extraction — only the three fields
that lore-mcp uses. Additional keys in the YAML
are silently ignored, allowing manifests to carry
consumer-specific metadata without breaking
lore-mcp.

Expected input format:
```yaml
collection: docs-libre
level: libre
sources:
  - path: intro.md
    title: Introduction
    author: RC
    license: CC-BY-SA-4.0
```

### Metadata extraction cascade (lines 20–40)

```python
def extract_source_metadata(text, filename):
    meta = {"title": None, "author": None, ...}
    fm = _extract_front_matter(text)  # try YAML front matter
    if fm:
        meta["title"] = fm.get("title")
        ...
    if not meta["title"]:
        heading = _extract_first_heading(text)  # try # heading
        ...
    if not meta["title"]:
        meta["title"] = Path(filename).stem     # fallback to filename
    return meta
```

Three-level cascade for title:
1. YAML front matter (`---\ntitle: ...\n---`)
2. First `#` heading in the Markdown
3. Filename stem (e.g. `my-doc.md` → `my-doc`)

Author, URL, date, license are only extracted
from front matter — there's no heuristic for
these fields from plain Markdown.

### Front matter regex (lines 43–51)

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
- **Empty manifest sources list**: returns empty
  `sources: []`

---

<!-- Part 2 continues with: ingest.py, server.py, metadata.py, eval.py -->
## server.py — MCP server and CLI entry point

Exposes MCP tools to clients and provides the CLI
entry point with subcommands (`eval`, `optimize`).

### Public API

| Function/Class | Line | Purpose |
|---|---|---|
| `format_search_results(results, backend)` | 66 | Format KNN results as LLM-readable text |
| `format_sources(sources)` | 90 | Format source listing as text |
| `format_collections(collections)` | 101 | Format collection listing with chunk info |
| `search_docs(query, top_k, collection)` | 118 | MCP tool: semantic search |
| `list_indexed_sources(collection)` | 145 | MCP tool: list files with chunk counts |
| `list_collections()` | 180 | MCP tool: list available collections |
| `main()` | 191 | CLI entry point (serve / eval / optimize) |

### Module-level state and thread safety

The server maintains two cached objects: the
embedder and the single-collection database
connection. Both are protected by a
`threading.Lock` (line 25):

```python
_embedder = None          # line 23
_single_db = None         # line 24
_init_lock = threading.Lock()  # line 25
```

The lock prevents a race condition under SSE
transport where concurrent requests could both
see `None` and create duplicate instances. This
was identified and fixed during the code review
(resource leak finding #3).

### Lazy initialization pattern

`_get_embedder()` (line 52) and `_get_single_db()`
(line 43) follow the same pattern:

```python
def _get_single_db():
    global _single_db
    with _init_lock:
        if _single_db is None:
            _single_db = open_db(_get_db_path())
    return _single_db
```

The lock is acquired, the check-and-create is
atomic, and the connection is reused for all
subsequent requests. This is critical because
`open_db()` loads the sqlite-vec extension, which
takes measurable time on first call.

### Two operating modes

The server determines its mode by checking
`LORE_DB_DIR` (line 38-40):

```python
def _is_multi_collection() -> bool:
    return _get_db_dir() is not None
```

In **single-collection mode**, the database
connection is cached in `_single_db` and reused.
In **multi-collection mode**, connections are
opened per-request and closed with `try/finally`
(line 155-159, 163-171) to prevent resource leaks.

### search_docs flow (lines 117-141)

1. Lazy-load the embedder
2. Embed the query text
3. Branch on mode:
   - Multi-collection with `collection` param:
     `search_collection()` — single .db
   - Multi-collection without param:
     `search_across()` — all .db files merged
   - Single-collection: `_get_single_db()` →
     `validate_model()` → `search()`
4. Format and return as text

Model validation (line 138) runs only in single-
collection mode — in multi-collection, each .db
validates its own model in `search_collection()`.

### format_search_results (lines 66-87)

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

### CLI subcommands (lines 191-276)

`main()` uses `argparse` with subparsers:

- No subcommand → `mcp.run(transport=...)` (MCP server)
- `eval` → `_run_eval()` (line 234)
- `optimize` → `_run_optimize()` (line 252)

The `optimize` subcommand uses a mutually
exclusive group (line 216) to enforce either
`--source-dir` or `--manifest`, not both:

```python
opt_group = optimize_parser.add_mutually_exclusive_group(required=True)
opt_group.add_argument("--source-dir", ...)
opt_group.add_argument("--manifest", ...)
```

### Edge cases

- Empty query string: `embedder.embed("")` works
  but returns low-quality embeddings — no
  validation (acceptable, the LLM client is
  responsible)
- `LORE_DB_DIR` set but directory empty:
  `search_across()` returns `[]`, formatted as
  "0 results."
- Multi-collection `list_indexed_sources` without
  collection: prefixes source files with
  `{collection_stem}/` (line 168) to disambiguate
  across collections

### Dependencies

- `mcp.server.MCPServer` — MCP SDK v2
- `lore_mcp.collections` — multi-collection logic
- `lore_mcp.embedder` — query-time embedding
- `lore_mcp.store` — database operations
- `lore_mcp.eval` — eval/optimize (lazy import in
  `_run_eval` and `_run_optimize`)

---

## ingest.py — Ingestion pipeline

Preprocesses, chunks, and indexes Markdown files
into SQLite with optional manifest-driven
bibliographic metadata.

### Public API

| Function | Line | Purpose |
|---|---|---|
| `get_chunk_config()` | 31 | Read chunk params from env vars |
| `preprocess(text)` | 38 | Strip NUL and base64 lines |
| `chunk_document(text, source_file, ...)` | 46 | Split text into chunks with deterministic IDs |
| `ingest_directory(dir_path, db_path, embedder, ...)` | 101 | Index a directory of .md files |
| `ingest_with_manifest(manifest_path, docs_dir, db_dir, embedder, ...)` | 144 | Manifest-driven indexing |

### Constants (lines 23-28)

```python
DEFAULT_CHUNK_SIZE = 1024    # changed from 2048 per E1.08 benchmark
DEFAULT_CHUNK_OVERLAP = 128
EMBED_BATCH_SIZE = 64
MIN_DOC_LENGTH = 100
```

`DEFAULT_CHUNK_SIZE` was changed from 2048 to
1024 in E6.04, based on AutoRAG benchmark results
showing +13% answer_correctness with bge-m3.

`MIN_DOC_LENGTH` (100 chars) skips trivially short
documents that would produce meaningless chunks
(e.g. a file with just "TODO").

### preprocess (lines 38-43)

```python
def preprocess(text: str) -> str:
    text = text.replace("\x00", "")
    return "\n".join(
        line for line in text.split("\n") if "base64," not in line
    )
```

Two operations:
1. **NUL stripping**: PDF-converted files may
   contain `\x00` bytes that crash SQLite inserts.
   Unconditional.
2. **base64 line removal**: Docling PDF→Markdown
   conversion embeds images as base64. A 70 KB
   document can become 1 MB. Lines containing
   `base64,` are removed entirely.

The check `"base64," not in line` is a substring
match, not a regex. This is intentional — it's
fast, and the only legitimate occurrence of
"base64," in Markdown is in data URIs.

### Deterministic chunk IDs (lines 60-63)

```python
chunk_id = hashlib.sha256(
    f"{source_file}:{i}:{part[:64]}".encode()
).hexdigest()[:16]
```

Three components make the ID:
- `source_file` — file-level uniqueness
- `i` — position within file
- `part[:64]` — content-based (detects edits)

Truncated to 16 hex chars (64 bits). The
probability of collision is negligible for the
expected scale (< 1M chunks).

This enables idempotent ingestion: `INSERT OR
IGNORE` in `store.py:insert_chunk()` skips
already-indexed chunks. Re-running ingestion on
an unchanged file is a no-op.

### _ingest_file (lines 73-98)

Internal function that processes a single file:

```python
def _ingest_file(db, md_file, rel, embedder,
                 chunk_size, chunk_overlap,
                 source_meta=None):
    text = md_file.read_text(encoding="utf-8")
    raw_text = text         # keep pre-preprocessed text
    text = preprocess(text)
    if len(text.strip()) < MIN_DOC_LENGTH:
        return 0
```

Why `raw_text`? The front matter YAML must be
extracted from the original text (before base64
stripping), because `preprocess()` could remove
lines that are part of the YAML block.

The `source_meta` parameter allows manifest-driven
ingestion to pass explicit metadata, bypassing
front matter extraction (line 85-89).

### Batch embedding (lines 92-96)

```python
for batch_start in range(0, len(chunks), EMBED_BATCH_SIZE):
    batch = chunks[batch_start : batch_start + EMBED_BATCH_SIZE]
    texts = [c["content"] for c in batch]
    embeddings = embedder.embed_batch(texts)
    insert_chunks(db, batch, embeddings)
```

Chunks are embedded in batches of 64. Each batch
is committed to the database immediately via
`insert_chunks()`. This means a crash mid-
ingestion loses at most 64 chunks, not the
entire run.

### ingest_directory (lines 101-141)

The standard entry point. Key pattern:

```python
for md_file in md_files:
    try:
        # ... process file
    except Exception as e:
        errors.append({"file": str(md_file), "error": str(e)})
```

Per-file error handling ensures a single corrupt
file doesn't abort the entire run. Errors are
collected in the return dict, not raised.

When `collection` and `db_dir` are both provided
(line 115-116), the output path is computed from
the collection name via `collection_db_path()`.

### ingest_with_manifest (lines 144-192)

Manifest-driven entry point. Reads a YAML
manifest via `parse_manifest()`, then iterates
over `manifest["sources"]` instead of globbing
`*.md`. Each source entry provides explicit
metadata:

```python
source_meta = {k: v for k, v in source_entry.items()}
source_meta.setdefault("level", level)  # inherit collection level
```

Files listed in the manifest but not found on
disk are reported as errors (line 176) but don't
abort the run.

### Dependencies

- `langchain_text_splitters.RecursiveCharacterTextSplitter`
- `lore_mcp.collections` — `collection_db_path()`
- `lore_mcp.manifest` — `parse_manifest()`,
  `extract_source_metadata()`
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

### generate_collection_json (lines 11-45)

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
  null values filtered out (line 38)

### generate_collection_bib (lines 48-72)

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
string (line 65):
```python
f"  year = {{{s['date'][:4] if len(s['date']) >= 4 else s['date']}}}"
```

### generate_collection_md (lines 75-129)

Human-readable Markdown. Includes a **gris
warning** (lines 117-125) when any source has
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
  outputs `"unknown"` (line 96-97)
- Sources with no metadata fields: falls back
  to `source_file` as title (line 111)
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

| Function/Class | Line | Purpose |
|---|---|---|
| `EvalConfig` | 18 | Configuration dataclass |
| `EvalConfig.from_env()` | 28 | Read config from env vars |
| `generate_questions_from_db(db_path, n, llm)` | 40 | Generate eval questions |
| `evaluate_retrieval(db_path, embedder, questions, top_k)` | 103 | Score retrieval quality |
| `generate_eval_report(results, path)` | 193 | Write JSON report |
| `run_eval(db_path, embedder, config, output_path)` | 203 | Full eval pipeline |
| `run_optimize(embedder, db_dir, ...)` | 223 | Parameter optimization |

### EvalConfig (lines 18-37)

```python
@dataclass
class EvalConfig:
    llm_url: str
    llm_model: str
    num_questions: int = 50
    top_k: int = 5
    verify_ssl: bool = True
```

`from_env()` raises `ValueError` if
`LORE_LLM_URL` is not set. This is the only
mandatory env var — all others have defaults.

### Question generation (lines 40-100)

Two strategies, chosen at runtime:

1. **Extractive** (`_generate_extractive`, line
   69): No external dependency. Selects random
   chunks, extracts the longest sentence, wraps
   it in a question template:
   ```python
   key_sentence = max(sentences, key=len)
   question = f"What does the documentation say about: {key_sentence[:80]}?"
   ```
   Ground truth is the key sentence itself. This
   tests whether the retrieval system can find the
   chunk the question was derived from.

2. **RAGAS** (`_generate_with_ragas`, line 86):
   Uses `TestsetGenerator` from the ragas package.
   Requires an LLM and the optional `[eval]`
   dependency. Falls back to extractive on
   `ImportError` (line 63-64).

The fallback is silent — a log message at INFO
level. This design means `lore-mcp eval` works
out of the box without RAGAS, producing basic
but usable results.

### Retrieval scoring (lines 103-176)

`evaluate_retrieval()` runs the full
question→embed→search→score loop:

```python
for q in questions:
    query_emb = embedder.embed(q["question"])
    results = search(db, query_emb, top_k=top_k)
    retrieved_contexts = [r["content"] for r in results]
    scores = _score_retrieval(question, retrieved_contexts, ground_truth)
```

`_score_retrieval()` (line 149) computes two
metrics:

- **hit** (line 162): Binary — 1.0 if the ground
  truth string appears as a substring in any
  retrieved context. Simple but effective for
  extractive questions.
- **word_overlap** (line 164-168): Fraction of
  ground truth words found in the best matching
  context. More nuanced than `hit` — partial
  matches score > 0.

```python
gt_words = set(gt_lower.split())
best_overlap = max(
    len(gt_words & set(ctx.lower().split())) / len(gt_words)
    for ctx in retrieved
)
```

### Model specificity

Both `evaluate_retrieval()` and `run_optimize()`
include `model_name` in the output (lines 141,
297). This ensures reports are traceable — scores
are only comparable across runs with the same
embedding model.

### run_optimize (lines 223-297)

The optimization loop:

1. Index with the first chunk_size/overlap
   configuration
2. Generate questions once from that index
3. For each (chunk_size, overlap, top_k)
   combination:
   a. Re-index (with manifest or directory)
   b. Evaluate retrieval on the same questions
   c. Record average score
4. Return the best configuration

When `manifest_path` is provided (line 253-256,
273-278), `ingest_with_manifest()` is used
instead of `ingest_directory()`, preserving
bibliographic metadata in each temporary .db.

```python
if manifest_path and effective_docs_dir:
    ingest_with_manifest(manifest_path, effective_docs_dir, str(db_dir_path),
                         embedder, chunk_size=cs, chunk_overlap=co)
```

### Edge cases

- No chunks in database: `generate_questions_from_db()`
  returns `[]`, and `evaluate_retrieval()` returns
  empty scores
- Ground truth is empty: `_score_retrieval()`
  returns `{"hit": 0.0}` — no crash
- All scores zero: `_average_scores()` handles
  this correctly (returns 0.0 for all metrics)
- RAGAS not installed: extractive fallback, no
  error

### Dependencies

- `lore_mcp.store` — `open_db()`, `search()`,
  `list_sources()`, `get_all_sources()`
- `lore_mcp.ingest` — `ingest_directory()`,
  `ingest_with_manifest()` (lazy import in
  `run_optimize`)
- `ragas` — optional, for LLM-based scoring
  and question generation
- Standard library (json, random, dataclasses,
  datetime, pathlib)
