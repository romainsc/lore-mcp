# API Reference — lore-mcp

Exhaustive documentation of every public and internal
function, class, and constant. For design rationale,
see [`architecture.md`](architecture.md). For usage
examples, see [`tutorial.md`](tutorial.md).

---

## store.py — SQLite + sqlite-vec storage backend

**Imports:** `sqlite3`, `datetime` (timezone-aware
timestamps), `sqlite_vec` (extension loader),
`serialize_float32` (vector serialization).

### Constants

*(none — all configuration is via function
parameters)*

### `open_db(path: str) -> sqlite3.Connection`

**Lines 10–16.** Open a SQLite database file and
load the sqlite-vec extension.

```python
def open_db(path: str) -> sqlite3.Connection:
    db = sqlite3.connect(path)
    db.enable_load_extension(True)
    sqlite_vec.load(db)
    db.enable_load_extension(False)
    return db
```

- **`path`** — file path to the `.db` file.
  Created if it doesn't exist.
- **Returns** — `sqlite3.Connection` with
  sqlite-vec loaded and extension loading
  re-disabled (security).
- **Side effects** — creates the file on disk if
  absent.
- **No exceptions** beyond standard SQLite errors.

**Detail:** `enable_load_extension(True)` is
required before `sqlite_vec.load()`, which calls
`conn.load_extension(path_to_vec0_binary)`.
Extension loading is immediately re-disabled
after to prevent SQL injection via
`load_extension()`.

---

### `create_tables(db, model_name, model_dim, chunk_size=None, chunk_overlap=None) -> None`

**Lines 19–82.** Create all tables (`chunks_vec`,
`chunks`, `sources`, `meta`) if they don't exist.
Populate `meta` with model and chunking info.

```python
def create_tables(
    db: sqlite3.Connection,
    model_name: str,
    model_dim: int,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> None:
```

- **`db`** — open connection from `open_db()`.
- **`model_name`** — HuggingFace model identifier
  (e.g. `"nomic-ai/nomic-embed-text-v2-moe"`).
  Stored in `meta` table for validation.
- **`model_dim`** — embedding dimension (e.g.
  `768`). Used in the `vec0` DDL. Must be a
  positive integer.
- **`chunk_size`** — optional. If provided,
  stored in `meta` for traceability.
- **`chunk_overlap`** — optional. Same.
- **Returns** — `None`.
- **Raises** — `ValueError` if `model_dim` is
  not a positive integer (line 27–28).
- **Side effects** — creates 4 tables, inserts
  3–5 `meta` rows, commits.

**Detail — tables created:**

1. **`chunks_vec`** (line 29–32): sqlite-vec
   virtual table.
   ```sql
   CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec
   USING vec0(
     embedding float[{model_dim}]
     distance_metric=cosine
   )
   ```
   The `model_dim` is interpolated via f-string.
   This is safe because it's validated as a
   positive integer on line 27. The
   `distance_metric=cosine` is set at table
   creation and cannot be changed later.

2. **`chunks`** (lines 33–41): regular table
   with `id TEXT PRIMARY KEY`, `source_file`,
   `chunk_index`, `content`, `metadata` (JSON
   default `'{}'`).

3. **`sources`** (lines 42–53): bibliographic
   metadata per source file. All columns except
   `source_file` are nullable. `extra TEXT
   DEFAULT '{}'` for future extensibility.

4. **`meta`** (lines 54–59): key-value store.
   Populated with `model_name`, `model_dim`,
   `created_at` (UTC ISO format). Optional:
   `chunk_size`, `chunk_overlap`.

**Detail — `INSERT OR IGNORE`** (lines 60–81):
meta rows are only inserted if not already
present. This makes `create_tables` idempotent —
calling it twice doesn't overwrite existing meta.

---

### `validate_model(db, model_name, model_dim) -> None`

**Lines 85–99.** Check that the current model
matches the one stored in the database.

```python
def validate_model(db, model_name, model_dim):
    meta = dict(db.execute(
        "SELECT key, value FROM meta"
    ).fetchall())
    stored_name = meta.get("model_name")
    stored_dim = meta.get("model_dim")
    if stored_name and stored_name != model_name:
        raise ValueError(...)
    if stored_dim and int(stored_dim) != model_dim:
        raise ValueError(...)
```

- **`db`** — connection with `meta` table.
- **`model_name`** — current model to validate.
- **`model_dim`** — current dimension.
- **Returns** — `None` (passes silently if OK).
- **Raises** — `ValueError` with descriptive
  message on mismatch.

**Detail:** `stored_dim` is stored as string in
meta (line 66: `str(model_dim)`), so it's cast
back to `int` for comparison (line 95). The
`and` guard (`if stored_name and ...`) handles
empty databases where meta might not be
populated yet.

---

### `upsert_source(db, source_file, title=None, author=None, url=None, date=None, license=None, level=None) -> None`

**Lines 102–125.** Insert or update bibliographic
metadata for a source file.

```python
db.execute(
    "INSERT INTO sources(...) VALUES (?, ...) "
    "ON CONFLICT(source_file) DO UPDATE SET "
    "title=COALESCE(excluded.title, sources.title), "
    ...
)
```

- **`source_file`** — primary key in `sources`.
- **All other params** — optional. Only non-None
  values overwrite existing data (via `COALESCE`).
- **Returns** — `None`.
- **Side effects** — commits.

**Detail — `COALESCE` pattern** (lines 116–122):
`COALESCE(excluded.title, sources.title)` means:
use the new value if provided, otherwise keep
the existing value. This allows incremental
updates — calling `upsert_source(db, "f.md",
title="New")` updates only the title, leaving
author/url/etc. untouched.

---

### `get_source(db, source_file) -> dict | None`

**Lines 128–135.** Retrieve bibliographic metadata
for one source file.

- **Returns** — `dict` with all columns, or
  `None` if not found.
- **Detail:** temporarily sets `db.row_factory =
  sqlite3.Row` to get named columns, then resets
  to `None` (lines 130, 134).

---

### `get_all_sources(db) -> list[dict]`

**Lines 138–143.** Retrieve all source metadata,
ordered by `source_file`.

- **Returns** — list of dicts, empty if no
  sources.

---

### `insert_chunk(db, chunk_id, source_file, chunk_index, content, embedding) -> None`

**Lines 146–165.** Insert a single chunk with its
embedding vector.

```python
cur = db.execute(
    "INSERT OR IGNORE INTO chunks(...) "
    "VALUES (?, ?, ?, ?)",
    (chunk_id, source_file, chunk_index, content),
)
if cur.rowcount > 0:
    db.execute(
        "INSERT INTO chunks_vec(rowid, embedding) "
        "VALUES (?, ?)",
        (cur.lastrowid, serialize_float32(embedding)),
    )
db.commit()
```

- **`chunk_id`** — deterministic ID (SHA-256
  hash). Duplicates are silently ignored
  (`INSERT OR IGNORE`).
- **`embedding`** — `list[float]`, serialized to
  binary BLOB via `serialize_float32()`.
- **Side effects** — commits.

**Detail — rowid synchronization** (lines
155–164): The regular table is inserted first.
`cur.lastrowid` captures the auto-generated
SQLite rowid. This rowid is then used as the
explicit rowid for the `chunks_vec` virtual
table, ensuring the two tables can be JOINed.

**Detail — `cur.rowcount > 0`** (line 160):
If the chunk already exists (duplicate ID), the
`INSERT OR IGNORE` is a no-op and `rowcount` is
0. In that case, we skip the vec0 insert to
avoid orphaned vectors.

---

### `insert_chunks(db, chunks, embeddings) -> None`

**Lines 168–185.** Batch-insert multiple chunks.

- **`chunks`** — list of dicts with keys `id`,
  `source_file`, `chunk_index`, `content`.
- **`embeddings`** — parallel list of
  `list[float]`.
- **Side effects** — single commit at the end
  (line 185).

Same rowid synchronization pattern as
`insert_chunk`, applied in a loop. The single
commit at the end (vs per-row commit) makes this
a transaction — all-or-nothing.

---

### `search(db, query_embedding, top_k=5) -> list[dict]`

**Lines 188–223.** KNN search with bibliographic
metadata.

```python
rows = db.execute("""
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
""", (serialize_float32(query_embedding), top_k))
```

- **`query_embedding`** — `list[float]`,
  serialized for the MATCH clause.
- **`top_k`** — number of results (default 5).
- **Returns** — list of dicts with keys:
  `content`, `source_file`, `score`, `title`,
  `author`, `url`, `license`.

**Detail — CTE pattern** (lines 196–201):
The `knn` CTE runs the KNN search in the vec0
virtual table, returning rowids and distances.
The outer query JOINs back to `chunks` (for
content) and `sources` (for bibliographic
metadata). Two `LEFT JOIN`s ensure results are
returned even without a `sources` entry
(backward compat).

**Detail — score conversion** (line 216):
`score = 1.0 - row[2]`. sqlite-vec cosine
distance is in `[0, 2]` (0 = identical). This
converts to similarity in `[-1, 1]`.

---

### `list_sources(db) -> list[dict]`

**Lines 226–232.** List indexed files with chunk
counts.

- **Returns** — list of `{"source_file": str,
  "count": int}`, ordered alphabetically.

---

## embedder.py — Embedding engine

**Imports:** `logging`, `os`, `pathlib.Path`.
`torch` imported with try/except (set to `None`
if unavailable).

### Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `FP32_VRAM_GB` | `2.8` | Minimum free VRAM (GB) for FP32 loading |
| `FP16_VRAM_GB` | `1.5` | Minimum free VRAM (GB) for FP16 loading |
| `CPU_RAM_MIN_GB` | `4.0` | Minimum available RAM (GB) for CPU loading |
| `DEFAULT_MODEL` | `"nomic-ai/nomic-embed-text-v2-moe"` | Default embedding model (Level 2 libre) |
| `FATAL_STATUS_CODES` | `{401, 403, 404}` | HTTP codes that trigger immediate failure (no retry) |
| `RETRIABLE_STATUS_CODES` | `{429, 500, 502, 503}` | HTTP codes that trigger retry with exponential backoff |

---

### `assess_gpu() -> dict`

**Lines 21–57.** Evaluate GPU capabilities.

- **Returns** — dict with keys:
  - `available` (bool)
  - `gpu_name` (str, if available)
  - `vram_free_gb` (float)
  - `vram_total_gb` (float)
  - `recommended_dtype` (`"float32"` or
    `"float16"`, if available)
  - `message` (str, always present —
    actionable when unavailable)

**Decision tree:**
1. Lines 23–24: if `torch` is None or CUDA not
   available → `{"available": False}`.
2. Lines 26–31: read VRAM via
   `torch.cuda.mem_get_info(0)`, compute
   capability via `get_device_capability(0)`.
   FP16 supported if `major >= 7` (Volta+).
3. Lines 33–41: free VRAM ≥ 2.8 GB → FP32.
4. Lines 42–50: free VRAM ≥ 1.5 GB and FP16
   supported → FP16.
5. Lines 52–57: insufficient VRAM → actionable
   message suggesting to free VRAM.

---

### `assess_cpu() -> dict`

**Lines 60–73.** Evaluate CPU capabilities.

- **Returns** — dict with `available`, `ram_available_gb`, `message`.

Calls `_get_available_ram_gb()`. Available if
RAM ≥ `CPU_RAM_MIN_GB` (4.0 GB).

---

### `_get_available_ram_gb() -> float`

**Lines 76–89.** Internal. Read available RAM.

**Strategy:**
1. Lines 78–83: try `/proc/meminfo`
   (`MemAvailable` line). Linux-specific.
   Value is in KB, converted to GB via
   `/ (1024**2)`.
2. Lines 85–88: fallback to `psutil.virtual_memory().available`.
3. Line 89: if both fail, returns `0.0`.

---

### `_probe_api(url, model, timeout=5.0, verify=True) -> bool`

**Lines 92–104.** Internal. Check if an embedding
API endpoint is reachable.

Sends a POST to `url` with `{"model": model,
"input": ["test"]}`. Returns `True` if status
200, `False` on any exception (timeout, connect
error, HTTP error).

- **`verify`** — SSL verification. Set `False`
  for self-signed certs.

---

### `_parse_mode(mode: str) -> tuple[str, str | None]`

**Lines 107–120.** Internal. Parse mode string
into `(backend, device_override)`.

| Input | Returns |
|-------|---------|
| `"builtin"` | `("builtin", None)` |
| `"builtin:gpu"` | `("builtin", "cuda")` |
| `"builtin:cpu"` | `("builtin", "cpu")` |
| `"api"` | `("api", None)` |
| anything else | raises `ValueError` |

---

### `class Embedder`

**Lines 123–270.** Main embedding engine.

#### `__init__(self, model_name=DEFAULT_MODEL, mode="builtin", api_url=None, api_model=None)`

**Lines 130–151.**

- Calls `_parse_mode(mode)` to validate and
  parse mode (line 137).
- Raises `ValueError` if `mode="api"` without
  `api_url` (line 138–139).
- Sets `self.api_verify` and `self.api_ca_bundle`
  from env vars (lines 146–147).
- `self._model = None` — lazy loading.
- `self._api_dim = None` — cached API dimension.

**Instance attributes:**

| Attribute | Type | Source |
|-----------|------|--------|
| `model_name` | str | parameter |
| `mode` | str | parameter (raw string) |
| `_backend` | str | from `_parse_mode` |
| `_device_override` | str \| None | from `_parse_mode` |
| `api_url` | str \| None | parameter |
| `api_model` | str | parameter or `model_name` |
| `api_verify` | bool | `LORE_API_VERIFY` env |
| `api_ca_bundle` | str \| None | `LORE_API_CA_BUNDLE` env |
| `_model` | SentenceTransformer \| None | lazy loaded |
| `_device` | str \| None | set on load |
| `_dtype` | torch.dtype \| None | set on load |
| `_api_dim` | int \| None | cached from API probe |

#### `model_dim -> int` (property)

**Lines 153–161.** Returns the embedding
dimension.

- API backend: probes the API via
  `_probe_api_dim()` (one-shot, cached in
  `_api_dim`).
- Builtin backend: calls `_ensure_loaded()` then
  `self._model.get_embedding_dimension()`.
- **Side effect:** may trigger model download
  (~1 GB) on first access in builtin mode.

#### `_probe_api_dim(self) -> int`

**Lines 163–166.** Embeds the string `"test"` via
the API and returns the length of the resulting
vector.

#### `assess(self) -> dict`

**Lines 168–179.** Returns a report of available
backends: `{"gpu": {...}, "api": {...}, "cpu":
{...}}`.

If `self.api_url` is set, probes the endpoint
with SSL settings from `_get_api_verify()`.

#### `embed(self, text: str) -> list[float]`

**Lines 181–187.** Embed a single text.

- API: delegates to `_embed_api([text])[0]`.
- Builtin: `self._model.encode(text,
  normalize_embeddings=True).tolist()`.
- **Always** passes `normalize_embeddings=True`
  for L2-normalized output.

#### `embed_batch(self, texts: list[str]) -> list[list[float]]`

**Lines 189–195.** Embed multiple texts.

Same pattern as `embed` but returns 2D list.

#### `unload(self) -> None`

**Lines 198–206.** Free model memory. Principle:
leave the place as you found it.

```python
def unload(self) -> None:
    if self._model is not None:
        del self._model
        self._model = None
        gc.collect()
        if torch and torch.cuda.is_available():
            torch.cuda.empty_cache()
    self._api_dim = None
```

- Deletes the model object.
- `gc.collect()` forces Python to release tensor
  references immediately (E10.16). Without this,
  `del` marks for GC but tensors may still occupy
  VRAM when `empty_cache()` runs.
- `torch.cuda.empty_cache()` releases the CUDA
  memory blocks back to the allocator.
- Resets `_api_dim` so it's re-probed if needed.
- Called by `run_optimize()` between models and
  at end, and by `run_build()` before final
  reindex and after indexation.
- Next call to `embed()` will re-trigger lazy
  loading.

#### `_ensure_loaded(self) -> None`

**Lines 206–212.** Lazy loading gate.

- If `_model` is already loaded, returns.
- If backend is `api`, returns (no local model).
- Otherwise calls `_load_local_model()`.

#### `_load_local_model(self) -> None`

**Lines 214–228.** Load sentence-transformers
model.

- Imports `SentenceTransformer` lazily (line
  216) to avoid import-time delay.
- Calls `_select_device_dtype()` for device and
  dtype.
- Passes `model_kwargs={"torch_dtype": dtype}` if
  dtype is not None (FP16).

#### `_select_device_dtype(self) -> tuple`

**Lines 230–242.** Pick device and dtype.

- `_device_override == "cuda"`: force GPU, call
  `_gpu_dtype()` for FP16/FP32.
- `_device_override == "cpu"`: force CPU, no
  dtype override.
- `None` (builtin default): assess GPU, use it
  if available, otherwise CPU.

#### `_gpu_dtype(self)`

**Lines 244–251.** Determine dtype for forced GPU.

- Calls `assess_gpu()`. If unavailable, raises
  `RuntimeError` with the assessment message.
- If `recommended_dtype == "float16"`, returns
  `torch.float16`. Otherwise `None` (FP32).

#### `_get_api_verify(self)`

**Lines 253–257.** Return SSL verify setting.

- If `api_ca_bundle` is set, returns the path
  (httpx uses it as CA file).
- Otherwise returns the boolean `api_verify`.

#### `_embed_api(self, texts: list[str]) -> list[list[float]]`

**Line 261.** Delegates to `_embed_api_with_retry`.

```python
def _embed_api(self, texts):
    return _embed_api_with_retry(self, texts)
```

### `class EmbeddingAPIError(Exception)`

**Line 266.** Raised when the embedding API fails
after all retries. Distinguishes API failures from
file-level errors in the ingest pipeline.

### `_embed_api_with_retry(embedder, texts, max_retries=3, base_delay=0.1)`

**Lines 274–350.** Core resilience function for
API embedding.

**Parameters:**
- `embedder` — Embedder instance (for api_url,
  api_model, SSL config)
- `texts` — list of strings to embed
- `max_retries` — max retry attempts per error
  (default 3)
- `base_delay` — initial backoff delay in seconds
  (default 0.1, doubles each retry)

**Behavior by HTTP status:**

| Status | Action |
|--------|--------|
| 200 | Success — extract embeddings, advance |
| 401, 403, 404 | `EmbeddingAPIError` immediately (no retry) |
| 422 | Halve `current_batch_size`, retry (until batch=1) |
| 429, 500, 502, 503 | Exponential backoff, retry up to `max_retries` |
| Timeout | Exponential backoff, retry |
| Connection error | Exponential backoff, retry |

**Batch reduction on 422:**
```python
if resp.status_code == 422 and current_batch_size > 1:
    current_batch_size = max(1, current_batch_size // 2)
    break  # retry with smaller batch
```

**Backoff with Retry-After:**
```python
delay = base_delay * (2 ** attempt)
retry_after = resp.headers.get("Retry-After")
if retry_after:
    delay = max(delay, float(retry_after))
```

**Return:** `list[list[float]]` — one embedding
per input text, in order. Indices are tracked via
`remaining` list to handle batch splitting
correctly.

**Raises:** `EmbeddingAPIError` when retries
exhausted or fatal status code received.

---

## collections.py — Multi-collection management

**Imports:** `os`, `pathlib.Path`,
`lore_mcp.store` (open_db, list_sources, search).

### Constants

*(none)*

---

### `build_collection_name(theme: str, level: str) -> str`

**Lines 13–15.** Concatenate theme and level with
a hyphen.

```python
return f"{theme}-{level}"
```

Example: `build_collection_name("ia", "libre")`
→ `"ia-libre"`.

---

### `collection_db_path(db_dir: str, name: str) -> str`

**Lines 18–20.** Return the full path to a named
collection's `.db` file.

```python
return str(Path(db_dir) / f"{name}.db")
```

---

### `_parse_name(filename: str) -> dict`

**Lines 23–30.** Internal. Extract theme and level
from a `.db` filename.

```python
name = filename.removesuffix(".db")
known_levels = {"nda", "libre", "restreint", "gris"}
parts = name.rsplit("-", 1)
if len(parts) == 2 and parts[1] in known_levels:
    return {"theme": parts[0], "level": parts[1]}
return {"theme": name, "level": ""}
```

- Uses `rsplit("-", 1)` to split on the **last**
  hyphen, so `"ia-serving-libre"` → theme
  `"ia-serving"`, level `"libre"`.
- Unknown levels (e.g. `"ia-custom.db"`) →
  theme `"ia-custom"`, level `""`.

---

### `discover_collections(db_dir: str) -> list[dict]`

**Lines 33–62.** Scan a directory for `.db` files
and return metadata for each.

- **Returns** — list of dicts with keys: `name`,
  `theme`, `level`, `chunk_count`, `file_count`,
  `chunk_size`, `chunk_overlap`, `model_name`,
  `model_dim`, `path`.
- Non-directory input → `[]` (line 36–37).
- Corrupt `.db` files → silently skipped (line
  60–61).

**Detail:** Opens each `.db`, reads `list_sources`
for counts, reads `meta` table directly (line 45)
for chunk params and model info. Closes the
connection immediately after reading.

---

### `search_collection(db_dir, collection, query_embedding, top_k=5) -> list[dict]`

**Lines 65–80.** Search within one named
collection.

- **Raises** `FileNotFoundError` if the `.db`
  file doesn't exist (line 73–74).
- Adds `"collection"` key to each result dict
  (line 78–79).
- Opens and closes the connection per call.

---

### `search_across(db_dir, query_embedding, top_k=5) -> list[dict]`

**Lines 83–102.** Search across ALL collections.

```python
all_results = []
for f in Path(db_dir).glob("*.db"):
    db = open_db(str(f))
    results = search(db, query_embedding, top_k=top_k)
    db.close()
    for r in results:
        r["collection"] = name
    all_results.extend(results)
all_results.sort(key=lambda r: r["score"], reverse=True)
return all_results[:top_k]
```

- Each `.db` runs its own KNN with `top_k`
  results → up to `N × top_k` results collected.
- Sorted by descending score (line 101).
- Truncated to `top_k` (line 102).
- Corrupt files silently skipped (line 99–100).

---

## manifest.py — Manifest parsing and metadata extraction

**Imports:** `re`, `pathlib.Path`, `yaml`.

### Constants

*(none)*

---

### `parse_manifest(manifest_path: str) -> dict`

**Lines 9–17.** Parse a YAML collection manifest.

- **Returns** — dict with keys: `collection`
  (str), `level` (str), `sources` (list of
  dicts).
- Missing keys default to `""` or `[]`.

---

### `extract_source_metadata(text: str, filename: str) -> dict`

**Lines 20–40.** Extract bibliographic metadata
from Markdown text.

**Extraction cascade:**
1. Lines 24–30: try YAML front matter via
   `_extract_front_matter()`. If found, populate
   title, author, url, date, license.
2. Lines 32–35: if no title from front matter,
   try first `#` heading via
   `_extract_first_heading()`.
3. Lines 37–38: if still no title, use the
   filename stem (e.g. `"my-doc.md"` →
   `"my-doc"`).

- **Returns** — dict with keys: `title`,
  `author`, `url`, `date`, `license`. All
  nullable except `title` (always has a value).

---

### `_extract_front_matter(text: str) -> dict | None`

**Lines 43–51.** Internal. Extract YAML front
matter delimited by `---`.

```python
match = re.match(
    r"^---\s*\n(.*?)\n---\s*\n",
    text, re.DOTALL
)
```

- `re.DOTALL` makes `.` match newlines.
- `(.*?)` is non-greedy to stop at the first
  closing `---`.
- Returns the parsed YAML dict, or `None` if
  no front matter or YAML parse error (line
  50–51).

---

### `_extract_first_heading(text: str) -> str | None`

**Lines 54–60.** Internal. Find the first line
matching `^# (.+)$`.

- Iterates line by line (line 56).
- Returns the heading text stripped of `# `
  prefix, or `None`.

---

## build_config.py — Unified build configuration

**Imports:** `os`, `dataclasses` (dataclass,
field), `pathlib.Path`, `yaml`.

### Constants

*(none)*

---

### `class BuildConfig`

**Lines 10–51.** Dataclass holding all build
parameters.

#### Fields

| Field | Type | Default |
|-------|------|---------|
| `embedding_models` | `list[dict]` | `[]` |
| `judge_model` | `str` | `""` |
| `judge_api_url` | `str` | `""` |
| `judge_verify_ssl` | `bool` | `True` |
| `metrics` | `list[str]` | `["score_spread", "source_diversity", "result_diversity"]` |
| `chunk_sizes` | `list[int]` | `[512, 1024, 2048]` |
| `chunk_overlaps` | `list[int]` | `[64, 128]` |
| `top_ks` | `list[int]` | `[3, 5, 10]` |
| `num_questions` | `int` | `50` |
| `default_model` | `str` | `""` |
| `default_chunk_size` | `int` | `1024` |
| `default_chunk_overlap` | `int` | `128` |

The `default_*` fields are used when
`--skip-optimize` is set — they specify the
fixed parameters instead of searching.
Read from the `defaults:` section in the YAML.

#### `from_file(cls, path: str) -> BuildConfig`

**Lines 23–42.** Class method. Parse a YAML file.

```python
with open(path, encoding="utf-8") as f:
    data = yaml.safe_load(f) or {}
judge = data.get("judge", {})
optimize = data.get("optimize", {})
```

Maps YAML sections to fields:
- `embedding_models` → top-level list
- `judge.model`, `judge.api_url`,
  `judge.verify_ssl` → judge fields
- `metrics` → top-level list
- `optimize.chunk_sizes`, `.chunk_overlaps`,
  `.top_ks`, `.num_questions` → optimize fields

Missing sections use class-level defaults.

#### `from_env(cls) -> BuildConfig`

**Lines 44–51.** Class method. Fallback when no
config file.

Reads `LORE_LLM_URL`, `LORE_LLM_MODEL`,
`LORE_API_VERIFY` from env vars. All other
fields use dataclass defaults.
## server.py

MCP server exposing search tools and CLI entry point.

### Module-level constants and globals

| Name | Value | Purpose |
|------|-------|---------|
| `mcp` | `MCPServer("lore-mcp")` | MCP server instance, tools are registered on it via `@mcp.tool()` |
| `_embedder` | `None` | Cached Embedder singleton, populated by `_get_embedder()` |
| `_single_db` | `None` | Cached SQLite connection for single-collection mode |
| `_init_lock` | `threading.Lock()` | Prevents race condition on lazy init of `_embedder` and `_single_db` under concurrent SSE requests |
| `logger` | `logging.getLogger(__name__)` | Module logger |

### `_get_db_dir() -> str | None`

Returns the value of `LORE_DB_DIR` environment variable, or `None` if not set. Used to determine if the server operates in multi-collection mode.

```python
def _get_db_dir() -> str | None:
    return os.environ.get("LORE_DB_DIR")
```

### `_get_db_path() -> str`

Returns `LORE_DB_PATH` for single-collection mode, defaulting to `"./lore.db"`.

```python
def _get_db_path() -> str:
    return os.environ.get("LORE_DB_PATH", "./lore.db")
```

### `_is_multi_collection() -> bool`

Returns `True` if `LORE_DB_DIR` is set. This determines whether the server uses single-collection mode (`LORE_DB_PATH`) or multi-collection mode (`LORE_DB_DIR`).

```python
def _is_multi_collection() -> bool:
    return _get_db_dir() is not None
```

### `_get_single_db() -> sqlite3.Connection`

Lazy-loads and caches a single database connection for single-collection mode. Uses `_init_lock` to prevent duplicate connections under concurrent requests.

```python
def _get_single_db():
    global _single_db
    with _init_lock:
        if _single_db is None:
            _single_db = open_db(_get_db_path())
    return _single_db
```

- **Side effect:** Opens and caches a SQLite connection on first call.
- **Thread safety:** `_init_lock` ensures only one connection is created even under concurrent SSE requests.
- **Connection lifecycle:** Never closed — persists for the server's lifetime. This is intentional: SQLite supports concurrent reads from a single connection.

### `_get_embedder() -> Embedder`

Lazy-loads the Embedder from environment variables. Thread-safe via `_init_lock`.

```python
def _get_embedder():
    global _embedder
    with _init_lock:
        if _embedder is None:
            _embedder = Embedder(
                model_name=os.environ.get("LORE_MODEL", "BAAI/bge-m3"),
                mode=os.environ.get("LORE_EMBED_MODE", "builtin"),
                api_url=os.environ.get("LORE_API_URL"),
                api_model=os.environ.get("LORE_API_MODEL"),
            )
    return _embedder
```

- **Side effect:** Creates Embedder singleton on first call. The model itself is NOT loaded here (lazy loading in Embedder).
- **Note:** The default `LORE_MODEL` here still says `"BAAI/bge-m3"` but the `Embedder` class default is `nomic-ai/nomic-embed-text-v2-moe`. If `LORE_MODEL` env var is not set, this function overrides the Embedder default with `"BAAI/bge-m3"`. This is a potential inconsistency — the env var default and the Embedder default diverge.

### `format_search_results(results: list[dict], backend: str) -> str`

Formats a list of search result dicts into a human-readable string for MCP tool output.

**Parameters:**
- `results` — list of dicts with keys: `content`, `source_file`, `score`, and optionally `collection`, `title`, `author`, `license`
- `backend` — embedding backend name displayed in the header (e.g. `"builtin"`, `"api"`)

**Returns:** Formatted string with header, one section per result separated by `---`.

```python
def format_search_results(results: list[dict], backend: str) -> str:
    if not results:
        return "0 results."
    parts = []
    for r in results:
        collection = r.get("collection", "")
        prefix = f"[{collection}:{r['source_file']}]" if collection else f"[{r['source_file']}]"
        biblio_parts = []
        if r.get("title"):
            biblio_parts.append(f"Title: {r['title']}")
        if r.get("author"):
            biblio_parts.append(f"Author: {r['author']}")
        if r.get("license"):
            biblio_parts.append(f"License: {r['license']}")
        biblio = " | ".join(biblio_parts)
        header = f"{prefix} (score: {r['score']:.4f})"
        if biblio:
            header += f"\n  {biblio}"
        parts.append(f"{header}\n{r['content']}")
    header = f"{len(results)} result(s) (embedding: {backend})"
    return header + "\n\n---\n\n".join([""] + parts)
```

- Line 72-73: If `collection` key exists and is non-empty, prefix includes collection name (`[docs-libre:intro.md]`). Otherwise just `[intro.md]`.
- Lines 74-81: Bibliographic metadata (title, author, license) appended if present. These come from the `sources` table joined in `store.search()`.
- Line 87: The empty string `""` in `[""] + parts` creates a leading `\n\n---\n\n` separator before the first result.

### `format_sources(sources: list[dict]) -> str`

Formats source listing for MCP output.

**Parameters:**
- `sources` — list of dicts with `source_file` and `count` keys

**Returns:** String with total counts header and per-file listing.

```python
def format_sources(sources: list[dict]) -> str:
    if not sources:
        return "0 chunks, 0 files."
    total = sum(s["count"] for s in sources)
    lines = [f"{total} chunks, {len(sources)} file(s)\n"]
    for s in sources:
        lines.append(f"  {s['source_file']}: {s['count']}")
    return "\n".join(lines)
```

### `format_collections(collections: list[dict]) -> str`

Formats collection listing with model info, chunk params, and level tags.

**Parameters:**
- `collections` — list of dicts from `discover_collections()` with keys: `name`, `level`, `chunk_count`, `file_count`, `model_name`, `model_dim`, `chunk_size`, `chunk_overlap`

**Returns:** Multi-line string.

```python
def format_collections(collections: list[dict]) -> str:
    if not collections:
        return "No collections found."
    total_chunks = sum(c["chunk_count"] for c in collections)
    total_files = sum(c["file_count"] for c in collections)
    lines = [f"{len(collections)} collection(s), {total_chunks} chunks, {total_files} files\n"]
    for c in collections:
        level = f" [{c['level']}]" if c["level"] else ""
        model_info = ""
        if c.get("model_name"):
            dim = c.get("model_dim", "?")
            model_info = f" model: {c['model_name']} ({dim}d)"
        chunk_info = ""
        if c.get("chunk_size"):
            chunk_info = f" chunk: {c['chunk_size']}/{c.get('chunk_overlap', '?')}"
        params = f" ({model_info.strip()},{chunk_info})" if model_info or chunk_info else ""
        lines.append(f"  {c['name']}{level}: {c['chunk_count']} chunks, {c['file_count']} files{params}")
    return "\n".join(lines)
```

- Lines 111-116: Model info and chunk params are only included if present in the dict. Old `.db` files without these meta keys will show no params.

### `search_docs(query: str, top_k: int = 5, collection: str = "") -> str`

MCP tool. Semantic search over indexed documents.

**Parameters:**
- `query` — natural language search query
- `top_k` — maximum number of results (default 5)
- `collection` — collection name for multi-collection mode (empty = search all)

**Returns:** Formatted search results string.

**Behavior:**
1. Lazy-loads embedder via `_get_embedder()`
2. Embeds the query via `embedder.embed(query)`
3. If multi-collection mode:
   - With `collection`: searches that single collection
   - Without: searches across all collections, merges by score
4. If single-collection: uses cached `_get_single_db()`, validates model, searches
5. Formats results via `format_search_results()`

**Side effects:** May trigger model download on first call (lazy loading).

### `list_indexed_sources(collection: str = "") -> str`

MCP tool. Lists all indexed files with chunk counts.

**Parameters:**
- `collection` — optional collection name in multi-collection mode

**Behavior:**
- Multi-collection + specific collection: opens that `.db`, reads sources, closes
- Multi-collection + no collection: iterates all `.db` files, prefixes source names with collection stem
- Single-collection: uses cached connection

**Resource management:** In multi-collection mode, database connections are opened and closed with `try/finally` to prevent leaks.

### `list_collections() -> str`

MCP tool. Lists available collections with metadata.

Returns "Single-collection mode" message if `LORE_DB_DIR` is not set. Otherwise calls `discover_collections()` and formats with `format_collections()`.

### `main() -> None`

CLI entry point. Parses subcommands via argparse.

**Subcommands:**

| Subcommand | Handler | Description |
|------------|---------|-------------|
| *(none)* | `mcp.run(transport=...)` | Start MCP server (default) |
| `eval` | `_run_eval(args)` | Evaluate retrieval quality |
| `optimize` | `_run_optimize(args)` | Optimize chunking params |
| `build` | `_run_build(args)` | Full build pipeline |

**`eval` arguments:** `--db`, `--num-questions`, `--top-k`, `--output`

**`optimize` arguments:** `--source-dir` | `--manifest` (mutually exclusive, required), `--docs-dir`, `--db-dir`, `--num-questions`, `--models`, `--config`, `--output`

**`build` arguments:** `manifest` (positional), `--docs-dir` (required), `--output-dir` (required), `--models`, `--config`, `--skip-optimize`, `--num-questions`, `--allow-download`, `--force`

### `_load_embedders_from_config_or_args(args) -> tuple[dict | None, BuildConfig | None]`

**Lines 275–304.** Shared helper for build and
optimize subcommands. Builds embedders dict from
`--config` (BuildConfig YAML), `--models`
(comma-separated or YAML), or returns None.

**Priority:** `--config` > `--models` > default
embedder.

```python
def _load_embedders_from_config_or_args(args):
    if getattr(args, "config", None):
        build_config = BuildConfig.from_file(args.config)
        configs = build_config.embedding_models
    elif getattr(args, "models", None):
        # parse from file or CLI string
    return embedders, build_config
```

### `_run_eval(args) -> None`

Creates `EvalConfig` from env, overrides `num_questions` and `top_k` from args, calls `run_eval()`, prints scores.

### `_run_optimize(args) -> None`

Parses `--models` (YAML file or comma-separated string), creates Embedder per model, calls `run_optimize()`, prints best config.

- Lines 282-283: If `args.models` is a path to an existing file, parses as YAML. Otherwise splits as comma-separated model names.
- Lines 288-290: Each model config creates a separate Embedder with the specified mode and API URL.

### `_run_build(args) -> None`

Full build workflow via CLI.

1. Parses model configs (same YAML/CLI logic as `_run_optimize`)
2. Pre-flight validation via `validate_models()` — unless `--allow-download` is set
3. Calls `run_build()` with all parameters
4. Prints summary

---

## ingest.py

Ingestion pipeline: preprocessing, chunking, indexing.

### Module-level constants

| Name | Value | Purpose |
|------|-------|---------|
| `DEFAULT_CHUNK_SIZE` | `1024` | Default chunk size in characters. Changed from 2048 per AutoRAG E1.08 benchmark |
| `DEFAULT_CHUNK_OVERLAP` | `128` | Default overlap between consecutive chunks |
| `EMBED_BATCH_SIZE` | `64` | Number of chunks embedded per batch |
| `MIN_DOC_LENGTH` | `100` | Documents shorter than this after preprocessing are skipped |
| `MD_SEPARATORS` | `["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""]` | Markdown-aware separators for RecursiveCharacterTextSplitter, tried in order |

### `class ConsecutiveErrorThreshold`

**Lines 31–49.** Stops the build if too many files
fail consecutively — indicates a systemic problem
(server down, auth expired, etc.).

```python
class ConsecutiveErrorThreshold:
    def __init__(self, max_consecutive: int = 3):
        self.max_consecutive = max_consecutive
        self._count = 0
        self.errors: list[dict] = []
```

**Methods:**

- `record_error(file, error)` — increments
  counter, appends to `self.errors`. Raises
  `RuntimeError` if `_count >= max_consecutive`.
- `record_success()` — resets `_count` to 0.

The counter resets on any successful file. Only
consecutive failures trigger the threshold.

### `get_chunk_config() -> tuple[int, int]`

Reads `LORE_CHUNK_SIZE` and `LORE_CHUNK_OVERLAP`
from environment variables, falling back to
module defaults.

```python
def get_chunk_config() -> tuple[int, int]:
    size = int(os.environ.get("LORE_CHUNK_SIZE", str(DEFAULT_CHUNK_SIZE)))
    overlap = int(os.environ.get("LORE_CHUNK_OVERLAP", str(DEFAULT_CHUNK_OVERLAP)))
    return size, overlap
```

**Returns:** `(chunk_size, chunk_overlap)` as
integers.

### `get_batch_size() -> int`

**Line 59.** Reads `LORE_BATCH_SIZE` from
environment variable, falling back to
`EMBED_BATCH_SIZE` (64).

```python
def get_batch_size() -> int:
    return int(os.environ.get("LORE_BATCH_SIZE", str(EMBED_BATCH_SIZE)))
```

Used in `_ingest_file` to control embedding
batch size. Set to 32 or lower for TEI endpoints
that have batch limits.

### `preprocess(text: str) -> str`

Cleans raw Markdown text before chunking.

```python
def preprocess(text: str) -> str:
    text = text.replace("\x00", "")
    return "\n".join(
        line for line in text.split("\n") if "base64," not in line
    )
```

**Operations:**
1. Strip NUL characters (`\x00`) — some PDF-converted documents contain these, which crash SQLite inserts.
2. Remove lines containing `base64,` — Docling PDF-to-Markdown conversion embeds base64 images that bloat chunks with binary noise.

**Returns:** Cleaned text. May be shorter than input.

### `chunk_document(text: str, source_file: str, chunk_size: int = 1024, chunk_overlap: int = 128) -> list[dict]`

Splits text into chunks with deterministic IDs.

**Parameters:**
- `text` — preprocessed document text
- `source_file` — relative path of the source file (used in chunk ID and stored in DB)
- `chunk_size` — maximum chunk size in characters
- `chunk_overlap` — overlap between consecutive chunks

**Returns:** List of dicts, each with keys `id`, `source_file`, `chunk_index`, `content`.

```python
def chunk_document(text, source_file, chunk_size=DEFAULT_CHUNK_SIZE,
                   chunk_overlap=DEFAULT_CHUNK_OVERLAP):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        separators=MD_SEPARATORS,
    )
    parts = splitter.split_text(text)
    chunks = []
    for i, part in enumerate(parts):
        chunk_id = hashlib.sha256(
            f"{source_file}:{i}:{part[:64]}".encode()
        ).hexdigest()[:16]
        chunks.append({
            "id": chunk_id, "source_file": source_file,
            "chunk_index": i, "content": part,
        })
    return chunks
```

- Lines 61-63: Chunk ID is `sha256(source_file:index:first_64_chars)` truncated to 16 hex chars. This makes IDs deterministic — re-indexing the same file produces the same IDs, enabling idempotent `INSERT OR IGNORE`.
- The first 64 characters of content are included so that editing a file changes the IDs of modified chunks, while unchanged chunks keep their IDs.

### `_ingest_file(db, md_file: Path, rel: str, embedder: Embedder, chunk_size: int, chunk_overlap: int, source_meta: dict | None = None) -> int`

Internal: ingests a single file into the database.

**Parameters:**
- `db` — open SQLite connection
- `md_file` — Path to the Markdown file
- `rel` — relative path string (used as `source_file` in DB)
- `embedder` — Embedder instance for generating embeddings
- `chunk_size`, `chunk_overlap` — chunking parameters
- `source_meta` — bibliographic metadata dict (from manifest). If None, metadata is extracted from front matter.

**Returns:** Number of chunks inserted (0 if document too short).

**Behavior:**
1. Reads file as UTF-8
2. Preprocesses (NUL, base64)
3. Skips if < 100 chars after preprocessing
4. Upserts source metadata (from manifest or extracted from front matter)
5. Chunks the document
6. Embeds in batches of 64
7. Inserts chunks into DB

### `ingest_directory(dir_path: str, db_path: str, embedder: Embedder, chunk_size: int = 1024, chunk_overlap: int = 128, collection: str | None = None, db_dir: str | None = None) -> dict`

Indexes a directory of Markdown files.

**Parameters:**
- `dir_path` — root directory to scan for `*.md` files
- `db_path` — output SQLite database path
- `embedder` — Embedder instance
- `chunk_size`, `chunk_overlap` — chunking parameters
- `collection` — if provided with `db_dir`, the `.db` filename is determined by collection name
- `db_dir` — directory for the output `.db` file (used with `collection`)

**Returns:** Dict with `file_count`, `chunk_count`, `errors`.

**Behavior:**
1. If `collection` and `db_dir`: resolves `db_path` via `collection_db_path()`
2. Opens DB, creates tables (with chunk params in meta)
3. Validates model against stored meta
4. Recursively finds `*.md` files
5. For each file: `_ingest_file()` with front matter extraction
6. Errors collected per-file (does not abort on failure)
7. Closes DB

### `ingest_with_manifest(manifest_path: str, docs_dir: str, db_dir: str, embedder: Embedder, chunk_size: int = 1024, chunk_overlap: int = 128) -> dict`

Indexes files listed in a YAML manifest into a named collection.

**Parameters:**
- `manifest_path` — path to the YAML manifest
- `docs_dir` — root directory where source files are located
- `db_dir` — directory for the output `.db` file
- `embedder` — Embedder instance
- `chunk_size`, `chunk_overlap` — chunking parameters

**Returns:** Dict with `file_count`, `chunk_count`, `errors`.

**Behavior:**
1. Parses manifest (collection name, level, sources with biblio metadata)
2. Resolves `.db` path from collection name via `collection_db_path()`
3. Creates tables with model and chunk metadata
4. For each source in manifest:
   - Sets default level from manifest if not per-source
   - Calls `_ingest_file()` with source_meta from manifest
   - Missing files reported as errors (not exceptions)
5. Closes DB

---

## metadata.py

Collection output files: `.json`, `.bib`, `.md`.

### `generate_collection_json(db_path: str) -> str`

Generates a JSON metadata file alongside the `.db` file.

**Parameters:**
- `db_path` — path to the `.db` file

**Returns:** Path to the generated `.json` file.

**Output content:**
```json
{
  "collection": "name",
  "model_name": "...",
  "model_dim": 768,
  "chunk_size": 1024,
  "chunk_overlap": 128,
  "created_at": "...",
  "generated_at": "...",
  "stats": { "file_count": N, "chunk_count": N, "db_size_bytes": N },
  "sha256": "...",
  "sources": [...]
}
```

```python
def generate_collection_json(db_path: str) -> str:
    db = open_db(db_path)
    meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
    sources = list_sources(db)
    biblio = get_all_sources(db)
    db.close()

    db_file = Path(db_path)
    sha256 = hashlib.sha256(db_file.read_bytes()).hexdigest()
    collection_name = db_file.stem
    # ... builds data dict, writes JSON
```

- Line 20: SHA-256 checksum of the entire `.db` file for integrity verification.
- Line 21: Collection name derived from the filename stem (e.g. `docs-libre.db` → `docs-libre`).
- Lines 37-39: Sources list filters out `None` values to keep the JSON clean.

### `generate_collection_bib(db_path: str) -> str`

Generates a BibTeX bibliography file alongside the `.db` file. One `@misc` entry per source.

**Returns:** Path to the generated `.bib` file.

```python
def generate_collection_bib(db_path: str) -> str:
    db = open_db(db_path)
    biblio = get_all_sources(db)
    db.close()

    entries = []
    for s in biblio:
        key = Path(s["source_file"]).stem.replace(" ", "_").replace("-", "_")
        fields = []
        if s.get("author"):
            fields.append(f"  author = {{{s['author']}}}")
        # ... builds BibTeX entry
```

- Line 56: BibTeX key sanitized from filename stem: spaces and hyphens replaced with underscores.
- Line 65: Year extracted from first 4 characters of date field.
- Line 67: License stored in the `note` field (standard BibTeX practice for non-standard metadata).
- No external dependency — BibTeX is generated as plain text.

### `generate_collection_md(db_path: str) -> str`

Generates a human-readable Markdown description.

**Returns:** Path to the generated `.md` file.

**Output structure:**
- `# <collection_name>` heading
- Parameters section (model, dims, chunk size/overlap, date)
- Statistics (files, chunks, DB size)
- Sources list (title — author (license) [url])
- Notice section if any source has `level == "gris"`

```python
    if any(s.get("level") == "gris" for s in biblio):
        lines.extend([
            "", "## Notice", "",
            "Some sources in this collection have uncertain redistribution rights..."
        ])
```

- Lines 117-124: The gris-level notice is automatically appended only when at least one source has `level == "gris"`. This is the plaidoyer de bonne foi.

### `generate_all(db_path: str) -> dict`

Convenience function that generates all three files.

```python
def generate_all(db_path: str) -> dict:
    return {
        "json": generate_collection_json(db_path),
        "bib": generate_collection_bib(db_path),
        "md": generate_collection_md(db_path),
    }
```

**Returns:** Dict mapping format → output path.

---

## eval.py

RAG evaluation: testset generation, retrieval scoring, optimization.

### Module-level constants

| Name | Value | Purpose |
|------|-------|---------|
| `METRIC_LEVELS` | `{"embedding": [...], "retrieval": [...], "ragas": [...]}` | Available metrics by level. Level 1 (embedding): `score_spread`, `source_diversity`, `result_diversity`. Level 2 (retrieval): `hit`, `word_overlap`, `mrr`. Level 3 (ragas): `faithfulness`, `context_recall`, `answer_correctness`. |
| `RAGAS_METRIC_NAMES` | `set(METRIC_LEVELS["ragas"])` | Set of RAGAS metric names for fast lookup in validation. |

### `validate_metrics_prerequisites(metrics, judge_url, judge_model) -> None`

**Lines 26–48.** Fail fast if RAGAS metrics are
requested but prerequisites are missing. RAGAS
metrics are **never activated implicitly** — they
must be explicitly listed.

**Parameters:**
- `metrics` — list of metric names to validate
- `judge_url` — judge LLM endpoint URL
- `judge_model` — judge LLM model name

**Raises:**
- `ValueError` if RAGAS metrics requested but no
  judge LLM configured
- `ImportError` if RAGAS metrics requested but
  `ragas` package not installed

```python
def validate_metrics_prerequisites(
    metrics, judge_url, judge_model,
) -> None:
    requested_ragas = [m for m in metrics if m in RAGAS_METRIC_NAMES]
    if not requested_ragas:
        return
    if not judge_url or not judge_model:
        raise ValueError(...)
    try:
        import ragas
    except ImportError:
        raise ImportError(...)
```

- Non-RAGAS metrics pass through without
  validation — they need no LLM.

### `compute_embedding_metrics(results: list[dict]) -> dict`

Level 1 metrics — no LLM, no ground truth needed.

**Parameters:**
- `results` — list of search result dicts with `score` and `source_file` keys

**Returns:** Dict with `score_spread`, `source_diversity`, `result_diversity`.

```python
def compute_embedding_metrics(results: list[dict]) -> dict:
    if not results:
        return {"score_spread": 0.0, "source_diversity": 0.0, "result_diversity": 0.0}
    scores = [r["score"] for r in results]
    sources = [r["source_file"] for r in results]
    return {
        "score_spread": round(max(scores) - min(scores), 4),
        "source_diversity": round(len(set(sources)) / len(results), 4),
        "result_diversity": 0.0,
    }
```

- `score_spread`: difference between highest and lowest score. Higher = more discriminating embedding.
- `source_diversity`: fraction of unique source files in results. 1.0 = all from different files, 0.0 = all from same file.
- `result_diversity`: placeholder (0.0) — pairwise cosine diversity not yet implemented.

### `compute_retrieval_metrics(contexts: list[str], ground_truth: str) -> dict`

Level 2 metrics — requires ground truth, no LLM.

**Parameters:**
- `contexts` — list of retrieved text chunks (ordered by relevance)
- `ground_truth` — expected answer text

**Returns:** Dict with `hit`, `word_overlap`, `mrr`.

```python
def compute_retrieval_metrics(contexts: list[str], ground_truth: str) -> dict:
    if not ground_truth or not contexts:
        return {"hit": 0.0, "word_overlap": 0.0, "mrr": 0.0}
    gt_lower = ground_truth.lower()
    hit = 1.0 if any(gt_lower in ctx.lower() for ctx in contexts) else 0.0
    mrr = 0.0
    for i, ctx in enumerate(contexts):
        if gt_lower in ctx.lower():
            mrr = 1.0 / (i + 1)
            break
    # ... word overlap computation
```

- `hit`: 1.0 if the ground truth text appears as a substring in any context, 0.0 otherwise.
- `mrr` (Mean Reciprocal Rank): `1/(rank of first matching context)`. If ground truth is in the first result: 1.0. In the second: 0.5. Not found: 0.0.
- `word_overlap`: fraction of ground truth words found in the best matching context. Uses set intersection of lowercased words.

### `parse_model_configs(config_path: str) -> list[dict]`

Parses a YAML file containing model configurations under a `models` key.

```python
def parse_model_configs(config_path: str) -> list[dict]:
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("models", [])
```

**Returns:** List of dicts, each with at least `name` and optionally `mode`, `api_url`, `api_model`.

### `parse_model_configs_from_cli(models_str: str) -> list[dict]`

Parses comma-separated model names from CLI into config dicts with `mode: "builtin"`.

```python
def parse_model_configs_from_cli(models_str: str) -> list[dict]:
    return [{"name": m.strip(), "mode": "builtin"} for m in models_str.split(",") if m.strip()]
```

### `class EvalConfig`

Dataclass holding evaluation configuration.

**Fields:**
- `llm_url: str` — URL of the judge LLM endpoint
- `llm_model: str` — model name for the judge
- `num_questions: int = 50` — number of evaluation questions
- `top_k: int = 5` — retrieval depth
- `verify_ssl: bool = True` — SSL verification for API calls

**`from_env() -> EvalConfig`** — classmethod that reads `LORE_LLM_URL` (required), `LORE_LLM_MODEL` (default `granite-8b-instruct`), `LORE_API_VERIFY` from environment.

**Raises:** `ValueError` if `LORE_LLM_URL` is not set.

### `generate_questions_from_db(db_path: str, num_questions: int = 50, llm=None) -> list[dict]`

Generates evaluation questions from indexed chunks.

**Parameters:**
- `db_path` — path to the `.db` file
- `num_questions` — target number of questions
- `llm` — optional LLM instance for RAGAS TestsetGenerator

**Returns:** List of dicts with `question`, `ground_truth`, `contexts`, `source_file`.

**Behavior:**
1. Reads random chunks from the database (3× `num_questions` to have selection margin)
2. If `llm` is provided, attempts RAGAS generation. Falls back to extractive on `ImportError`.
3. Extractive generation: picks the longest sentence from each chunk as ground truth, wraps it as a question.

### `_generate_extractive(chunks: list, num_questions: int) -> list[dict]`

Internal. Generates questions by extracting key sentences.

```python
def _generate_extractive(chunks, num_questions):
    selected = random.sample(chunks, min(num_questions, len(chunks)))
    for content, source_file in selected:
        sentences = [s.strip() for s in content.split(".") if len(s.strip()) > 20]
        if sentences:
            key_sentence = max(sentences, key=len)
            # ... creates question dict
```

- Line 127: `random.sample` selects without replacement. If fewer chunks than requested, uses all.
- Line 129: Filters sentences shorter than 20 chars (removes fragments).
- Line 131: Longest sentence chosen as key — it's most likely to be informative.

### `_generate_with_ragas(chunks: list, num_questions: int, llm) -> list[dict]`

Internal. Generates questions using RAGAS TestsetGenerator. Requires `ragas` package.

### `evaluate_retrieval(db_path: str, embedder, questions: list[dict], top_k: int = 5) -> dict`

Evaluates retrieval quality on a set of questions.

**Parameters:**
- `db_path` — path to the `.db` file to evaluate
- `embedder` — Embedder instance (used to embed questions)
- `questions` — list of question dicts from `generate_questions_from_db()`
- `top_k` — number of results to retrieve per question

**Returns:** Dict with `db_path`, `model_name`, `num_questions`, `top_k`, `scores` (averages), `details` (per-question).

**Behavior:**
1. Opens the database
2. For each question: embeds query, searches, scores retrieved contexts against ground truth
3. Averages scores across all questions

### `_score_retrieval(question: str, retrieved: list[str], ground_truth: str) -> dict`

Internal. Scores a single question's retrieval quality using text overlap.

Returns `{"hit": 0.0}` if no ground truth or no retrieved contexts. Otherwise returns `hit` and `word_overlap`.

### `_average_scores(details: list[dict]) -> dict`

Internal. Computes per-metric averages across all question details. Handles heterogeneous score keys (some questions may have different metrics).

### `generate_eval_report(results: dict, output_path: str) -> str`

Writes evaluation results to a JSON file. Adds `generated_at` timestamp.

### `run_eval(db_path: str, embedder, config: EvalConfig, output_path: str | None = None) -> dict`

Full evaluation pipeline: generate questions → retrieve → score → report.

### `_optimize_ingest(db_dir_path, manifest_path, docs_dir, embedder, chunk_size, chunk_overlap) -> str`

Internal helper for optimization. Indexes one configuration into a deterministic `.db` path.

```python
def _optimize_ingest(db_dir_path, manifest_path, docs_dir, embedder,
                     chunk_size, chunk_overlap):
    db_name = f"opt-{chunk_size}-{chunk_overlap}"
    db_path = str(db_dir_path / f"{db_name}.db")

    if Path(db_path).exists():
        Path(db_path).unlink()

    if manifest_path and docs_dir:
        ingest_with_manifest(...)
        # Rename manifest-named .db to deterministic name
        collection = parse_manifest(manifest_path)["collection"]
        manifest_db = str(db_dir_path / f"{collection}.db")
        if Path(manifest_db).exists() and manifest_db != db_path:
            Path(manifest_db).rename(db_path)
    elif docs_dir:
        ingest_directory(docs_dir, db_path, embedder, ...)

    return db_path
```

- Line 289-290: Deterministic name `opt-<size>-<overlap>.db` prevents collision when manifest always produces the same collection-named `.db` (E10.06 fix).
- Line 292-293: Deletes existing `.db` to ensure clean state.
- Lines 300-304: When using a manifest, `ingest_with_manifest` creates a `.db` named after the collection. The rename moves it to the deterministic name.

### `run_optimize(embedder=None, embedders=None, db_dir="./optimize-dbs", source_dir=None, manifest_path=None, docs_dir=None, chunk_sizes=None, chunk_overlaps=None, top_ks=None, num_questions=30) -> dict`

Multi-model optimization: varies models × chunk_size × overlap × top_k.

**Parameters:**
- `embedder` — single Embedder (used if `embedders` not provided)
- `embedders` — dict of `{model_name: Embedder}` for multi-model
- `db_dir` — working directory for temp `.db` files
- `source_dir` — source docs directory (mutually exclusive with `manifest_path`)
- `manifest_path` — YAML manifest path
- `docs_dir` — docs directory (used with `manifest_path`)
- `chunk_sizes`, `chunk_overlaps`, `top_ks` — parameter grids (defaults: [512,1024,2048], [64,128], [3,5,10])
- `num_questions` — number of eval questions

**Returns:** Dict with `best` (winning config) and `all` (all configs with scores).

**Raises:** `ValueError` if neither `embedder` nor `embedders` provided.

**Behavior:**
1. If single embedder, wraps in `{name: embedder}` dict
2. Indexes first config, generates questions once
3. Iterates: for each model → for each chunk_size → for each overlap → for each top_k
4. Calls `unload()` on previous embedder when switching models (E10.11)
5. Tracks best config by average score
6. **Cleanup (E10.16):** calls `unload()` on ALL
   embedders at end of optimization (lines 420-421).
   Leave the place as you found it.

- Lines 390-391: `prev_emb.unload()` called when switching to a different model.
- Lines 420-421: final cleanup — all embedders unloaded before returning.

---

## build.py

Build workflow: manifest + models → optimized .db + metadata.

### Module-level constants

| Name | Value | Purpose |
|------|-------|---------|
| `QUESTIONS_FILE` | `"questions.json"` | Filename for persisted evaluation questions (resumability) |
| `SCORES_FILE` | `"scores.jsonl"` | Filename for persisted per-config scores (resumability) |

### `validate_models(configs: list[dict], embedders: dict | None = None) -> list[str]`

Pre-flight validation of all model configurations.

**Parameters:**
- `configs` — list of model config dicts with `name`, `mode`, optionally `api_url`
- `embedders` — optional dict of already-created Embedders (for mock testing)

**Returns:** List of error strings. Empty list = all models valid.

```python
def validate_models(configs, embedders=None):
    from lore_mcp.embedder import _probe_api
    errors = []
    for cfg in configs:
        name = cfg["name"]
        mode = cfg.get("mode", "builtin")
        if mode == "api":
            url = cfg.get("api_url")
            if not url:
                errors.append(f"{name}: mode=api but no api_url")
                continue
            if not _probe_api(url, cfg.get("api_model", name), verify=False):
                errors.append(f"{name}: API endpoint unreachable ({url})")
        elif embedders and name in embedders:
            pass  # Already created, skip validation
        else:
            cache_path = Path.home() / ".cache" / "huggingface" / "hub" / f"models--{name.replace('/', '--')}"
            if not cache_path.exists():
                errors.append(f"{name}: not in HuggingFace cache, use --allow-download")
    return errors
```

- Line 37: API probing uses `verify=False` to handle self-signed certs during validation.
- Line 42: HuggingFace cache path convention: `models--<org>--<model>` (slashes replaced with `--`).
- All errors collected, not short-circuited — user sees all problems at once.

### `run_build(manifest_path: str, docs_dir: str, output_dir: str, embedder=None, embedders=None, skip_optimize=False, chunk_sizes=None, chunk_overlaps=None, top_ks=None, num_questions=50, work_dir=None, force=False) -> dict`

Full build pipeline.

**Parameters:**
- `manifest_path` — YAML manifest path
- `docs_dir` — source documents directory
- `output_dir` — output directory for `.db` + metadata
- `embedder` / `embedders` — single or multi-model
- `skip_optimize` — if True, skips optimization, uses defaults
- `chunk_sizes`, `chunk_overlaps`, `top_ks` — optimization grids
- `num_questions` — eval questions count
- `work_dir` — working directory for temp files (default: `<output_dir>/.build-work`)
- `force` — if True, ignores existing cached state

**Returns:** Build report dict with `collection`, `model_name`, `chunk_size`, `chunk_overlap`, `file_count`, `chunk_count`, `optimization`, `resumed`.

**Side effects:**
- Creates `output_dir` if it doesn't exist
- Creates work directory
- Writes `.db`, `.json`, `.bib`, `.md` in output directory
- Writes `build-report.json` in output directory

**Behavior:**
1. Parses manifest to get collection name
2. Creates embedders dict if single embedder provided
3. If not `skip_optimize`: runs optimization, reads winning config
4. **Cleanup (E10.16):** unloads ALL embedders
   (line 102-103) to free VRAM before final reindex
5. Indexes final `.db` with winning model + chunk params
6. **Cleanup (E10.16):** unloads final embedder
   (line 118) after indexation — leave the place
   as you found it
7. Generates metadata files
8. Writes build report

```python
    if not skip_optimize:
        optimization = _run_optimization(...)
        best = optimization.get("best", {})
        if best:
            winning_model = best.get("model_name", winning_model)
            winning_chunk_size = best.get("chunk_size", winning_chunk_size)
            winning_chunk_overlap = best.get("chunk_overlap", winning_chunk_overlap)

    final_db = str(output_path / f"{collection}.db")
    final_emb = embedders[winning_model]
```

- Line 79: Default `winning_model` is the first key in `embedders` dict — used when `skip_optimize` is True.
- Lines 105-106: If final `.db` already exists and `force` is False, skips re-indexing. This is part of resumability.

### `_run_optimization(manifest_path, docs_dir, embedders, work_dir, chunk_sizes, chunk_overlaps, top_ks, num_questions, force) -> dict`

Internal. Runs optimization with resumability support.

**Behavior:**
1. Checks for existing `scores.jsonl` in work directory
2. If found and not `force`: loads existing scores, sets `resumed=True`
3. Calls `run_optimize()` from eval module
4. Writes all scores to `scores.jsonl`

```python
    if not force and scores_path.exists():
        existing_scores = [
            json.loads(line)
            for line in scores_path.read_text().strip().split("\n")
            if line.strip()
        ]
        resumed = True
```

- Lines 161-167: `scores.jsonl` is a JSON Lines file — one JSON object per line. Each line is a config result from `run_optimize()`.
- The current implementation loads existing scores for reporting `resumed=True` but re-runs the full optimization. True skip-completed-configs resumability would require comparing existing scores against the requested grid — this is a simplification.
