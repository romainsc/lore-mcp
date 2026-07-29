# lore-mcp

**LORE — Local Offline Retrieval Engine for MCP**

An MCP server for semantic search over your local technical documents. No cloud, no external database — just a single `.db` file on your workstation.

## What it does

- **Indexes** a directory of Markdown/text files into a portable SQLite database using vector embeddings
- **Exposes** two MCP tools (`search_docs`, `list_sources`) for any MCP client (Claude Code, Claude Desktop, Cursor, etc.)
- **Runs locally** with automatic GPU/API/CPU fallback for embedding generation

## Status

Early development. See the [backlog](#roadmap) for planned features.

## Quickstart

### Prerequisites

- Python ≥ 3.10
- (Optional) NVIDIA GPU with CUDA for faster embeddings

### Installation

```bash
pip install lore-mcp
```

> **Note:** not yet published on PyPI. For now, install from source:
> ```bash
> git clone https://github.com/rchanter/lore-mcp.git
> cd lore-mcp
> pip install -e .
> ```

### Configure your MCP client

Add to your MCP client configuration (e.g. `.claude/settings.json`):

```json
{
  "mcpServers": {
    "lore": {
      "command": "lore-mcp",
      "args": []
    }
  }
}
```

### Index your documents

```bash
lore-mcp index /path/to/your/docs/
```

### Search

Once configured, your MCP client can use:
- `search_docs("your query", top_k=5)` — semantic search over indexed documents
- `list_sources()` — list all indexed files with chunk counts

### Environment variables

| Variable | Role | Default |
|----------|------|---------|
| `LORE_DB_PATH` | SQLite database file path | `./lore.db` |
| `LORE_MODEL` | Embedding model name | `BAAI/bge-m3` |
| `LORE_EMBED_MODE` | Mode: `auto`, `gpu`, `api`, `cpu` | `auto` |
| `LORE_API_URL` | Remote `/v1/embeddings` URL | *(required if mode=api)* |
| `LORE_API_MODEL` | Model name for remote API | same as `LORE_MODEL` |

## Architecture

lore-mcp uses [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) for embeddings (1024 dimensions, multilingual) and [sqlite-vec](https://github.com/asg017/sqlite-vec) for vector storage in a single `.db` file.

Embedding generation falls back automatically: local GPU (CUDA) → remote API (OpenAI-compatible) → local CPU.

See `docs/` for detailed documentation (coming with MVP).

## Roadmap

### MVP (v0.1.0)

- [ ] SQLite + sqlite-vec storage backend
- [ ] Embedding with GPU/API/CPU fallback
- [ ] MCP server (`search_docs`, `list_sources`)
- [ ] CLI ingestion tool
- [ ] Tests (TDD)

### Post-MVP

- [ ] Example corpus and sample database
- [ ] Incremental re-indexing
- [ ] Metadata filtering
- [ ] Hybrid search (vector + keyword)
- [ ] Image captioning during ingestion
- [ ] Docker image

## AI-assisted development

This project is developed with AI assistance (Claude, Anthropic). All AI-assisted content is marked with `Co-Authored-By` trailers in commits. Every contribution — human or AI-assisted — is reviewed, tested, and validated by a human before being committed.

See [`docs/ai-guidelines.md`](docs/ai-guidelines.md) for the full guidelines.

## License

[GPL-3.0-or-later](LICENSE) — see [`docs/adr/001-license-gpl-v3.md`](docs/adr/001-license-gpl-v3.md) for the rationale.

Copyright (C) 2026 Romain Chantereau
