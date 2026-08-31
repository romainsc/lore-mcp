# lore-mcp

**LORE — Local Offline Retrieval Engine for MCP**

An MCP server for semantic search over your local technical documents. No cloud, no external database — just a single `.db` file on your workstation.

## What it does

- **Indexes** a directory of Markdown/text files into a portable SQLite database using vector embeddings
- **Exposes** three MCP tools (`search_docs`, `list_indexed_sources`, `list_collections`) for any MCP client (Claude Code, Claude Desktop, Cursor, etc.)
- **Runs locally** with automatic GPU/API/CPU fallback for embedding generation

## Quickstart

### 1. Install

```bash
git clone https://github.com/romainsc/lore-mcp.git
cd lore-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Check your hardware capabilities

```python
python -c "
from lore_mcp.embedder import Embedder
emb = Embedder()
report = emb.assess()
print('GPU:', report['gpu']['message'])
print('CPU:', report['cpu']['message'])
"
```

Example output:

```
GPU: NVIDIA RTX 500 Ada: 1.3/3.7 GB free, FP16 mode
CPU: 17.0 GB RAM available, CPU mode OK
```

If GPU VRAM is insufficient, the message tells you what to do (e.g. close GPU-heavy applications). If neither GPU nor CPU has enough resources, the embedding model cannot be loaded.

### 3. Index your documents

```python
python -c "
from lore_mcp.embedder import Embedder
from lore_mcp.ingest import ingest_directory

embedder = Embedder()  # auto-detects GPU/CPU
result = ingest_directory('/path/to/your/docs/', 'lore.db', embedder)
print(f'Indexed {result[\"file_count\"]} files, {result[\"chunk_count\"]} chunks')
if result['errors']:
    print(f'{len(result[\"errors\"])} errors (see details in result[\"errors\"])')
"
```

What happens:
- **First run** downloads the embedding model [nomic-ai/nomic-embed-text-v2-moe](https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe) (~2 GB). This takes a few minutes. Subsequent runs use the cache (`~/.cache/huggingface/`).
- Files are preprocessed (NUL characters and base64 image data stripped), chunked (2048 chars, 128 overlap), embedded, and stored in `lore.db`.
- Files shorter than 100 characters after preprocessing are skipped.
- If a file fails to process, the error is logged and indexing continues with the next file.

### 4. Start the MCP server and configure your client

There are two ways to connect lore-mcp to your MCP client:

#### Option A: HTTP server (recommended)

Start the server manually, then point your MCP client to its URL:

```bash
LORE_DB_PATH=/absolute/path/to/lore.db lore-mcp --transport sse
```

The server listens on `http://localhost:8000/sse`. Configure your MCP client:

```json
{
  "mcpServers": {
    "lore": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

No path issues — the server runs in its own environment.

#### Option B: subprocess (stdio)

The MCP client launches the server as a subprocess. Requires the absolute path to the virtualenv binary:

```json
{
  "mcpServers": {
    "lore": {
      "command": "/absolute/path/to/lore-mcp/.venv/bin/lore-mcp",
      "args": [],
      "env": {
        "LORE_DB_PATH": "/absolute/path/to/lore.db"
      }
    }
  }
}
```

> **Note:** use absolute paths — the MCP client does not inherit your shell's virtualenv or working directory.

See [`docs/configuration.md`](docs/configuration.md) for all environment variables and options.

### 5. Use from your MCP client

Once configured, your MCP client has three tools:

**Semantic search:**
```
search_docs("how to configure authentication")
```
Returns the 5 most relevant passages with similarity scores and source files.

**Search with more results or within a collection:**
```
search_docs("deployment troubleshooting", top_k=10)
search_docs("embedding models", collection="docs-libre")
```

**List indexed files:**
```
list_indexed_sources()
```
Returns all indexed files with chunk counts.

**List collections** (multi-collection mode):
```
list_collections()
```
Returns available `.db` collections with chunk and file counts.

### 6. Verify it works

From Claude Code, ask a question about your indexed documents. Claude will automatically call `search_docs` to find relevant passages and answer based on your local corpus.

If the server doesn't start, check:
- The `command` path points to the `lore-mcp` executable in your virtualenv
- The `LORE_DB_PATH` points to an existing `.db` file
- The virtualenv has all dependencies installed (`pip install -e .`)

## Environment variables

| Variable | Role | Default |
|----------|------|---------|
| `LORE_DB_PATH` | SQLite database file path | `./lore.db` |
| `LORE_MODEL` | Embedding model name | `nomic-ai/nomic-embed-text-v2-moe` |
| `LORE_EMBED_MODE` | Mode: `builtin`, `builtin:gpu`, `builtin:cpu`, `api` | `builtin` |
| `LORE_API_URL` | Remote `/v1/embeddings` URL | *(required if mode=api)* |
| `LORE_API_MODEL` | Model name for remote API | same as `LORE_MODEL` |
| `LORE_DB_DIR` | Directory of `.db` files (multi-collection) | *(none)* |
| `LORE_API_VERIFY` | SSL verification for API (`true`/`false`) | `true` |
| `LORE_API_CA_BUNDLE` | Custom CA certificate path | *(system CA)* |
| `LORE_CHUNK_SIZE` | Chunk size in characters | `1024` |
| `LORE_CHUNK_OVERLAP` | Chunk overlap in characters | `128` |
| `LORE_LLM_URL` | Chat LLM endpoint for eval | *(required for eval)* |
| `LORE_LLM_MODEL` | Judge model name | `granite-8b-instruct` |

See [`docs/configuration.md`](docs/configuration.md) for the full reference.

## Architecture

lore-mcp uses [nomic-ai/nomic-embed-text-v2-moe](https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe) for embeddings (1024 dimensions, multilingual) and [sqlite-vec](https://github.com/asg017/sqlite-vec) for vector storage in a single `.db` file.

Embedding generation falls back automatically: local GPU (CUDA) → remote API (OpenAI-compatible) → local CPU.

See [`docs/architecture.md`](docs/architecture.md) for the full design documentation.

## Roadmap

### Done

- [x] SQLite + sqlite-vec storage backend with model validation
- [x] Embedding with GPU/API/CPU fallback and capability assessment
- [x] MCP server (`search_docs`, `list_indexed_sources`)
- [x] Ingestion pipeline (preprocessing, chunking, batch indexing)
- [x] Unit and integration tests (165 tests, TDD)
- [x] Architecture and configuration documentation
- [x] README quickstart tutorial
- [x] Multi-collection support with license classification

### Next

- [ ] CI/CD with GitHub Actions
- [ ] Example corpus and sample database
- [ ] `pip install lore-mcp` (PyPI)
- [ ] CLI `lore-mcp index` subcommand
- [ ] RAG evaluation (`lore-mcp eval` + `lore-mcp optimize`)
- [ ] Build workflow (`lore-mcp build manifest.yaml --models models.yaml`)

### Future

- [ ] Per-source result cap (reduce redundancy)
- [ ] Incremental re-indexing
- [ ] Metadata filtering
- [ ] Hybrid search (vector + keyword)
- [ ] Image captioning during ingestion
- [ ] Docker image

## AI-assisted development

This project is developed with AI assistance (Claude, Anthropic). All AI-assisted content is marked with `Assisted-by` and `Co-Authored-By` trailers in commits. Every contribution — human or AI-assisted — is reviewed, tested, and validated by a human before being committed.

See [`docs/ai-guidelines.md`](docs/ai-guidelines.md) for the full guidelines.

## License

[AGPL-3.0-or-later](LICENSE) — see [`docs/adr/001-license-gpl-v3.md`](docs/adr/001-license-gpl-v3.md) for the rationale.

Copyright (C) 2026 Romain Chantereau
