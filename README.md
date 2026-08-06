# lore-mcp

**LORE — Local Offline Retrieval Engine for MCP**

An MCP server for semantic search over your local technical documents. No cloud, no external database — just a single `.db` file on your workstation.

## What it does

- **Indexes** a directory of Markdown/text files into a portable SQLite database using vector embeddings
- **Exposes** two MCP tools (`search_docs`, `list_sources`) for any MCP client (Claude Code, Claude Desktop, Cursor, etc.)
- **Runs locally** with automatic GPU/API/CPU fallback for embedding generation

## Quickstart

### 1. Install

```bash
git clone https://github.com/romainsc/lore-mcp.git
cd lore-mcp
pip install -e .
```

### 2. Index your documents

```python
from lore_mcp.embedder import Embedder
from lore_mcp.ingest import ingest_directory

embedder = Embedder()  # auto-detects GPU/CPU
result = ingest_directory("/path/to/your/docs/", "lore.db", embedder)
print(f"Indexed {result['file_count']} files, {result['chunk_count']} chunks")
```

The first run downloads the embedding model (~2 GB). Subsequent runs use the cache.

### 3. Configure your MCP client

Copy [`examples/mcp-config.example.json`](examples/mcp-config.example.json) or add manually to your client configuration:

**Claude Code** (`.claude/settings.json`):
```json
{
  "mcpServers": {
    "lore": {
      "command": "lore-mcp",
      "args": [],
      "env": {
        "LORE_DB_PATH": "/absolute/path/to/lore.db"
      }
    }
  }
}
```

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "lore": {
      "command": "lore-mcp",
      "args": [],
      "env": {
        "LORE_DB_PATH": "/absolute/path/to/lore.db"
      }
    }
  }
}
```

### 4. Search

Once configured, your MCP client can use:

- `search_docs("your query")` — semantic search, returns the 5 most relevant passages with scores and sources
- `search_docs("your query", top_k=10)` — return more results
- `list_indexed_sources()` — list all indexed files with chunk counts

### Environment variables

| Variable | Role | Default |
|----------|------|---------|
| `LORE_DB_PATH` | SQLite database file path | `./lore.db` |
| `LORE_MODEL` | Embedding model name | `BAAI/bge-m3` |
| `LORE_EMBED_MODE` | Mode: `auto`, `gpu`, `api`, `cpu` | `auto` |
| `LORE_API_URL` | Remote `/v1/embeddings` URL | *(required if mode=api)* |
| `LORE_API_MODEL` | Model name for remote API | same as `LORE_MODEL` |

See [`docs/configuration.md`](docs/configuration.md) for the full reference.

## Architecture

lore-mcp uses [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) for embeddings (1024 dimensions, multilingual) and [sqlite-vec](https://github.com/asg017/sqlite-vec) for vector storage in a single `.db` file.

Embedding generation falls back automatically: local GPU (CUDA) → remote API (OpenAI-compatible) → local CPU.

See [`docs/architecture.md`](docs/architecture.md) for the full design documentation.

## Roadmap

### Done

- [x] SQLite + sqlite-vec storage backend with model validation
- [x] Embedding with GPU/API/CPU fallback and capability assessment
- [x] MCP server (`search_docs`, `list_indexed_sources`)
- [x] Ingestion pipeline (preprocessing, chunking, batch indexing)
- [x] Unit and integration tests (60 tests, TDD)
- [x] Architecture and configuration documentation

### Next

- [ ] CI/CD with GitHub Actions
- [ ] README quickstart with working examples
- [ ] Example corpus and sample database
- [ ] `pip install lore-mcp` (PyPI)

### Future

- [ ] Incremental re-indexing
- [ ] Metadata filtering
- [ ] Hybrid search (vector + keyword)
- [ ] Image captioning during ingestion
- [ ] Docker image

## AI-assisted development

This project is developed with AI assistance (Claude, Anthropic). All AI-assisted content is marked with `Assisted-by` and `Co-Authored-By` trailers in commits. Every contribution — human or AI-assisted — is reviewed, tested, and validated by a human before being committed.

See [`docs/ai-guidelines.md`](docs/ai-guidelines.md) for the full guidelines.

## License

[GPL-3.0-or-later](LICENSE) — see [`docs/adr/001-license-gpl-v3.md`](docs/adr/001-license-gpl-v3.md) for the rationale.

Copyright (C) 2026 Romain Chantereau
