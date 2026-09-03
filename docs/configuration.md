# Configuration

All lore-mcp configuration is via environment
variables. No configuration file is required.

For architecture context, see
[`architecture.md`](architecture.md).

## Environment variables

### `LORE_DB_PATH`

Path to the SQLite database file
(single-collection mode).

- **Type:** file path (string)
- **Default:** `./lore.db`
- **Used by:** MCP server (`server.py`),
  ingestion (`ingest.py`)

The file is created automatically on first
ingestion. Mutually exclusive with `LORE_DB_DIR`.

### `LORE_DB_DIR`

Path to a directory of `.db` files
(multi-collection mode).

- **Type:** directory path (string)
- **Default:** *(none)*
- **Used by:** MCP server (`server.py`),
  collections (`collections.py`)

When set, the server operates in multi-collection
mode: `search_docs` can search across all
collections or within a specific one,
`list_collections` lists available collections.
Files follow the naming convention
`<theme>-<level>.db` (see
`docs/architecture.md`, Collections layer).

Takes precedence over `LORE_DB_PATH`.

### `LORE_MODEL`

Name of the sentence-transformers embedding
model.

- **Type:** HuggingFace model identifier (string)
- **Default:** `nomic-ai/nomic-embed-text-v2-moe`
- **Used by:** embedder (`embedder.py`)

The model is downloaded from HuggingFace Hub on
first use and cached locally
(`~/.cache/huggingface/`). Changing the model
after indexing invalidates the existing database
— the server will refuse to query with a
mismatched model (see `store.py:validate_model()`).

### `LORE_EMBED_MODE`

Embedding backend selection.

- **Type:** one of `builtin`, `builtin:gpu`, `builtin:cpu`, `api`
- **Default:** `builtin`
- **Used by:** embedder (`embedder.py`)

| Mode | Behavior |
|------|----------|
| `builtin` | In-process via sentence-transformers, auto GPU/CPU based on VRAM assessment. |
| `builtin:gpu` | Force CUDA GPU. Raises error if unavailable or VRAM insufficient. |
| `builtin:cpu` | Force CPU. Slower but always works if RAM sufficient (~4 GB). |
| `api` | External HTTP endpoint (TEI, vLLM). Requires `LORE_API_URL`. |

In `builtin` mode, the embedder evaluates GPU
capabilities (VRAM, compute capability) before
deciding. See `embedder.py:assess_gpu()` for the
decision logic.

### `LORE_API_URL`

URL of a remote OpenAI-compatible embedding
endpoint.

- **Type:** URL (string)
- **Default:** *(none)*
- **Required when:** `LORE_EMBED_MODE=api`
- **Used by:** embedder (`embedder.py`)

Must implement the `/v1/embeddings` API (POST).
Compatible services: vLLM, Llama Stack, any
OpenAI-compatible embedding server.

Example: `http://localhost:8000/v1/embeddings`

### `LORE_API_MODEL`

Model name to pass to the remote API.

- **Type:** string
- **Default:** same as `LORE_MODEL`
- **Used by:** embedder (`embedder.py`)

Some API servers use different model identifiers
than HuggingFace (e.g. `BAAI/bge-m3-embedding`
instead of `BAAI/bge-m3`).

### `LORE_API_VERIFY`

SSL certificate verification for API calls.

- **Type:** `true` or `false`
- **Default:** `true`
- **Used by:** embedder (`embedder.py`)

Set to `false` to disable SSL verification when
the API endpoint uses a self-signed certificate
(e.g. OpenShift internal CA).

### `LORE_API_CA_BUNDLE`

Path to a custom CA certificate bundle for API
calls.

- **Type:** file path (string)
- **Default:** *(none — uses system CA store)*
- **Used by:** embedder (`embedder.py`)

Takes precedence over `LORE_API_VERIFY`. Use
this to trust a specific CA without disabling
verification entirely.

### `LORE_CHUNK_SIZE`

Maximum chunk size in characters for ingestion.

- **Type:** integer
- **Default:** `1024`
- **Used by:** ingest (`ingest.py:get_chunk_config()`)

Changed from 2048 to 1024 based on AutoRAG E1.08
benchmarks (+13% answer_correctness with bge-m3).

### `LORE_CHUNK_OVERLAP`

Overlap between consecutive chunks in characters.

- **Type:** integer
- **Default:** `128`
- **Used by:** ingest (`ingest.py:get_chunk_config()`)

## MCP transport

lore-mcp supports two MCP transport modes
(see `server.py:main()`):

### HTTP/SSE (recommended)

Start the server manually, clients connect via
URL. No PATH or virtualenv issues.

```bash
# Single-collection:
LORE_DB_PATH=/path/to/lore.db lore-mcp --transport sse

# Multi-collection:
LORE_DB_DIR=/path/to/collections/ lore-mcp --transport sse
```

Client configuration:
```json
{
  "mcpServers": {
    "lore": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### stdio (subprocess)

The MCP client spawns the server as a
subprocess. Requires the absolute path to the
binary in the virtualenv.

```json
{
  "mcpServers": {
    "lore": {
      "command": "/path/to/.venv/bin/lore-mcp",
      "args": [],
      "env": {
        "LORE_DB_PATH": "/path/to/lore.db"
      }
    }
  }
}
```

### With a remote embedding API

Add `LORE_EMBED_MODE` and `LORE_API_URL` to the
environment, regardless of transport mode:

```json
{
  "env": {
    "LORE_EMBED_MODE": "api",
    "LORE_API_URL": "http://localhost:8000/v1/embeddings"
  }
}
```

## Concurrency

SQLite supports concurrent reads but serializes
writes. In practice:
- Multiple MCP clients can query the same `.db`
  file concurrently (read-only, no issue).
- Do not run ingestion while the server is
  querying — SQLite will handle locking, but
  long writes can block reads.
- The `.db` file uses WAL mode when supported,
  which improves concurrent read performance.

## CLI output flags

The `eval`, `optimize`, and `build` subcommands
accept mutually exclusive output flags
(see `progress.py`):

| Flag | Level | Behavior |
|------|-------|----------|
| *(none)* | `default` | Header, sections, results table with ★, summary. |
| `--quiet` | `quiet` | No console output. |
| `--progress` | `progress` | Single overwriting line: global % + ETA, phase n/total, sub-progress %, model name. |
| `--verbose` | `verbose` | Default + truncated questions table, per-iteration milestones with per-metric scores. |
| `--debug` | `debug` | Verbose + HTTP request content (URL, model, batch, full input texts), response details. Only `lore_mcp` loggers at DEBUG; third-party (httpx, sentence_transformers) stay at WARNING. |

Example:

```bash
lore-mcp build manifest.yaml \
  --docs-dir /path/to/sources/ \
  --output-dir /path/to/output/ \
  --config build-config.yaml \
  --verbose
```

### `--num-questions`

Total number of evaluation questions sampled
across all documents (not per document).

| Subcommand | Default |
|------------|---------|
| `eval` | 50 |
| `optimize` | 30 |
| `build` | 50 |

CLI `--num-questions` takes precedence over the
`optimize.num_questions` value in build config.

## CLI usage

### Indexing documents

Ingestion is currently done programmatically
via `lore_mcp.ingest.ingest_directory()`.
A `lore-mcp index` subcommand is planned.

### Chunking parameters

Configurable via environment variables or
`ingest_directory()` parameters.

| Variable | Default | Purpose |
|----------|---------|---------|
| `LORE_CHUNK_SIZE` | `1024` | Maximum chunk size in characters |
| `LORE_CHUNK_OVERLAP` | `128` | Overlap between consecutive chunks |

The default chunk_size was changed from 2048 to
1024 based on AutoRAG E1.08 benchmarks
(+13% answer_correctness with bge-m3 1024d,
recursive 1024/128 vs 2048/128). See
`docs/studies/reference/research-notes.md`.

Chunk parameters are stored in the `meta` table
of each `.db` file for traceability. In multi-
collection mode, `list_collections()` displays
the chunk_size/overlap per collection.

See `ingest.py:get_chunk_config()` for the
env var reading logic.

## Collection manifest

For production indexing with bibliographic
metadata, use a YAML manifest:

```yaml
collection: ia-libre
level: libre
sources:
  - path: intro.md
    title: "Introduction to AI Serving"
    author: "Romain Chantereau"
    url: "https://..."
    license: "CC-BY-SA-4.0"
  - path: config.md
    title: "Configuration Guide"
```

The manifest specifies:
- `collection`: name → output `.db` filename
- `level`: redistribution level (nda/libre/restreint/gris)
- `sources`: list of files with optional biblio
  metadata (title, author, url, date, license)

Without a manifest, `ingest_directory()` extracts
metadata from YAML front matter in each Markdown
file.

See `manifest.py:parse_manifest()` and
`ingest.py:ingest_with_manifest()`.

## Output metadata files

After ingestion, call `metadata.generate_all(db_path)`
to produce three files alongside the `.db`:

- `<collection>.json` — machine-readable metadata
- `<collection>.bib` — BibTeX bibliography
- `<collection>.md` — human-readable description

See `metadata.py` and
[`architecture.md`](architecture.md).

## RAG evaluation

### `LORE_LLM_URL`

URL of a chat-capable LLM endpoint for RAGAS
evaluation metrics.

- **Type:** URL (string)
- **Default:** *(none — required for `lore-mcp eval`)*
- **Used by:** eval (`eval.py`)

Must implement the OpenAI-compatible chat API.
Compatible services: vLLM, Llama Stack, Ollama.

### `LORE_LLM_MODEL`

Model name for the judge LLM.

- **Type:** string
- **Default:** `granite-8b-instruct`
- **Used by:** eval (`eval.py`)

RAGAS metrics require both `LORE_LLM_URL` and
`LORE_LLM_MODEL`. Without RAGAS installed
(`pip install lore-mcp[eval]`), basic text-overlap
scoring is used (no LLM needed).

In build config YAML, the judge section supports
`verify_ssl` for self-signed endpoints:

```yaml
judge:
  model: granite-8b-instruct
  api_url: https://llm.internal/v1
  verify_ssl: false
```

- **`verify_ssl`**: boolean, default `true`. Set
  to `false` for self-signed certificates.

When RAGAS metrics are requested, lore-mcp probes
the judge endpoint at startup
(`eval.py:_probe_judge()`). If unreachable, a
`ConnectionError` is raised immediately (fail
fast) instead of silently failing per-question.

For usage examples, see [`tutorial.md`](tutorial.md).

## Embedding model requirements

The default model (BAAI/bge-m3) produces:

- **1024 dimensions** (float32)
- **L2-normalized** vectors (unit length)
- **Multilingual** support (EN, FR, ZH, …)
- **Max 8192 tokens** per input

Any sentence-transformers-compatible model can
be used via `LORE_MODEL`, but changing the model
invalidates the existing index. The vec0 virtual
table dimension is set at creation time and
cannot be changed.

### Resource requirements

| Backend | bge-m3 (FP32) | bge-m3 (FP16) | Latency |
|---------|---------------|---------------|---------|
| GPU | ~2.8 GB VRAM | ~1.5 GB VRAM | ~20ms/query |
| CPU | ~4 GB RAM | (no benefit) | ~200ms/query |
| API | N/A | N/A | network-dependent |

See `embedder.py:assess_gpu()` and
`embedder.py:assess_cpu()` for the capability
detection logic.
