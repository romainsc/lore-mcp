# lore-mcp

**LORE — Local Offline Retrieval Engine for MCP**

An MCP server for semantic search over your local
documents. Preprocesses, indexes, and serves any
format — PDF, HTML, DOCX, markdown, and more. No
cloud, no external database — just a single `.db`
file on your workstation.

## What it does

- **Preprocesses** source documents in any format
  (PDF, HTML, DOCX, PPTX, XLSX, EPUB, images,
  CSV, JSON, XML, markdown) into clean markdown
- **Indexes** with vector embeddings and full-text
  search (hybrid FTS5 + vector with RRF fusion)
- **Serves** three MCP tools (`search_docs`,
  `list_indexed_sources`, `list_collections`)
  for any MCP client
- **Evaluates** retrieval quality with built-in
  RAG evaluation and parameter optimization
- **Runs locally** with automatic GPU/API/CPU
  fallback for embedding generation

## Quickstart

### 1. Install

```bash
git clone https://github.com/romainsc/lore-mcp.git
cd lore-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[parse]"
```

Install extras by need:
- `pip install -e .` — core (markdown only)
- `pip install -e ".[html]"` — add HTML support
  (trafilatura)
- `pip install -e ".[pdf]"` — add PDF/DOCX/PPTX
  support (Docling)
- `pip install -e ".[parse]"` — all format support
- `pip install -e ".[eval]"` — RAG evaluation
  (RAGAS)

### 2. Create a config file

```yaml
# config.yaml
database:
  path: ./lore.db

embedding:
  model: nomic-ai/nomic-embed-text-v2-moe
  mode: builtin    # builtin, builtin:gpu, builtin:cpu, api

chunking:
  chunk_size: 1024
  chunk_overlap: 128
```

See [`docs/configuration.md`](docs/configuration.md)
for all options.

### 3. Create a manifest

```yaml
# manifest.yaml
collection: my-docs
level: libre

sources:
  - title: Architecture Guide
    license: Apache-2.0
    orig: architecture.pdf

  - title: API Reference
    orig: api-ref.html

  - url: https://example.com/guide.md
```

The manifest declares sources abstractly. `orig`
is the source file in its native format. `path`
(output filename) is generated automatically.

### 4. Preprocess and build

```bash
# Preprocess: convert + clean sources
lore-mcp preprocess manifest.yaml \
  --config config.yaml \
  --docs-base-dir /path/to/corpus/ \
  --orig-subdir orig \
  --prep-subdir prep

# Build: index preprocessed sources
lore-mcp build manifest-prep.yaml \
  --config config.yaml \
  --docs-dir /path/to/corpus/prep/ \
  --output-dir /path/to/output/ \
  --skip-optimize
```

Or combine both in one step:

```bash
lore-mcp build manifest.yaml \
  --config config.yaml \
  --docs-dir /path/to/corpus/orig/ \
  --output-dir /path/to/output/ \
  --preprocess --skip-optimize
```

### 5. Start the MCP server

#### Option A: HTTP server (recommended)

```bash
lore-mcp --config config.yaml --transport sse
```

```json
{
  "mcpServers": {
    "lore": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

#### Option B: subprocess (stdio)

```json
{
  "mcpServers": {
    "lore": {
      "command": "/path/to/.venv/bin/lore-mcp",
      "args": ["--config", "/path/to/config.yaml"]
    }
  }
}
```

### 6. Use from your MCP client

```
search_docs("how to configure authentication")
search_docs("deployment", top_k=10, collection="docs-libre")
list_indexed_sources()
list_collections()
```

Search uses hybrid retrieval (vector + FTS5
full-text) with Reciprocal Rank Fusion for
better keyword matching alongside semantic
similarity.

## CLI commands

| Command | Purpose |
|---------|---------|
| `lore-mcp` | Start MCP server |
| `lore-mcp preprocess` | Convert and clean sources |
| `lore-mcp build` | Index sources into .db |
| `lore-mcp lint` | Analyze source quality |
| `lore-mcp eval` | Evaluate retrieval quality |
| `lore-mcp optimize` | Auto-optimize parameters |
| `lore-mcp enrich` | LLM enrichment (context, Q&A) |

All commands accept `--config config.yaml`.

## Architecture

Uses [nomic-ai/nomic-embed-text-v2-moe](https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe)
for embeddings (768 dimensions, multilingual,
Apache 2.0) and [sqlite-vec](https://github.com/asg017/sqlite-vec)
for vector storage. Hybrid search combines
vector KNN with FTS5 full-text via RRF fusion.

Preprocessing uses
[trafilatura](https://github.com/adbar/trafilatura)
(HTML, Apache 2.0),
[Docling](https://github.com/DS4SD/docling)
(PDF/DOCX, MIT), and
[markitdown](https://github.com/microsoft/markitdown)
(CSV/JSON/XML, MIT).

See [`docs/architecture.md`](docs/architecture.md)
for the full design.

## Roadmap

### Done

- [x] SQLite + sqlite-vec storage with model
  validation
- [x] Embedding with GPU/API/CPU fallback
- [x] MCP server (search_docs,
  list_indexed_sources, list_collections)
- [x] Multi-collection support with license
  classification
- [x] Preprocessing tool (multi-format parsing,
  clean, dedup, PII detection, quality gate)
- [x] LLM enrichment (contextual retrieval,
  Q&A mode)
- [x] Hybrid search (FTS5 + vector + RRF fusion)
- [x] RAG evaluation and parameter optimization
- [x] Build workflow (manifest + config →
  optimized .db + metadata)
- [x] Unified config.yaml (no env vars)
- [x] MarkdownTextSplitter (structure-aware
  chunking)
- [x] 379+ tests (TDD)

### Next

- [ ] Documentation reorganization
- [ ] Reranking (cross-encoder)
- [ ] Adjacent-chunk / parent-child retrieval
- [ ] End-to-end parameter optimization
- [ ] CI/CD with GitHub Actions
- [ ] pip install lore-mcp (PyPI)
- [ ] Docker image

## AI-assisted development

This project is developed with AI assistance
(Claude, Anthropic). All AI-assisted content is
marked with `Assisted-by` and `Co-Authored-By`
trailers in commits. Every contribution is
reviewed, tested, and validated by a human.

See [`docs/ai-guidelines.md`](docs/ai-guidelines.md).

## License

[AGPL-3.0-or-later](LICENSE) — see
[`docs/adr/001-license-gpl-v3.md`](docs/adr/001-license-gpl-v3.md)
for the rationale.

Copyright (C) 2026 Romain Chantereau
