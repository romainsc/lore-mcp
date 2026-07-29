# Configuration

All lore-mcp configuration is via environment
variables. No configuration file is required.

For architecture context, see
[`architecture.md`](architecture.md).

## Environment variables

### `LORE_DB_PATH`

Path to the SQLite database file.

- **Type:** file path (string)
- **Default:** `./lore.db`
- **Used by:** MCP server (`server.py`),
  ingestion CLI (`ingest.py`)

The file is created automatically on first
ingestion. The `.db` extension is conventional
but not enforced.

### `LORE_MODEL`

Name of the sentence-transformers embedding
model.

- **Type:** HuggingFace model identifier (string)
- **Default:** `BAAI/bge-m3`
- **Used by:** embedder (`embedder.py`)

The model is downloaded from HuggingFace Hub on
first use and cached locally
(`~/.cache/huggingface/`). Changing the model
after indexing invalidates the existing database
— the server will refuse to query with a
mismatched model (see `store.py:validate_model()`).

### `LORE_EMBED_MODE`

Embedding backend selection.

- **Type:** one of `auto`, `gpu`, `api`, `cpu`
- **Default:** `auto`
- **Used by:** embedder (`embedder.py`)

| Mode | Behavior |
|------|----------|
| `auto` | Try GPU first, fall back to CPU. API is used only if `LORE_API_URL` is set and reachable. |
| `gpu` | Force CUDA GPU. Raises error if GPU is unavailable or VRAM insufficient. |
| `api` | Use remote API exclusively. Requires `LORE_API_URL`. |
| `cpu` | Force CPU mode. Slower but always works if RAM is sufficient (~4 GB). |

In `auto` mode, the embedder evaluates GPU
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

## MCP client configuration

To use lore-mcp with an MCP client, add it to
the client's server configuration.

### Claude Code / Claude Desktop

In `.claude/settings.json` or
`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "lore": {
      "command": "lore-mcp",
      "args": [],
      "env": {
        "LORE_DB_PATH": "/path/to/your/lore.db",
        "LORE_EMBED_MODE": "auto"
      }
    }
  }
}
```

### With a remote API

```json
{
  "mcpServers": {
    "lore": {
      "command": "lore-mcp",
      "args": [],
      "env": {
        "LORE_DB_PATH": "/path/to/your/lore.db",
        "LORE_EMBED_MODE": "api",
        "LORE_API_URL": "http://localhost:8000/v1/embeddings"
      }
    }
  }
}
```

## CLI usage

### Indexing documents

```bash
lore-mcp index /path/to/your/docs/
```

This is not yet implemented as a CLI subcommand.
Currently, ingestion is done programmatically
via `lore_mcp.ingest.ingest_directory()`.

### Chunking parameters

Chunking defaults are defined in
`ingest.py` as module constants:

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `chunk_size` | 2048 | Maximum chunk size in characters |
| `chunk_overlap` | 128 | Overlap between consecutive chunks |

These values were validated by AutoRAG benchmarks
on a Red Hat corpus (see
`docs/studies/reference/research-notes.md`).

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
