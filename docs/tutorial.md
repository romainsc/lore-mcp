# Tutorial — Running lore-mcp

This guide covers the full workflow: preprocessing
sources, building optimized collections, and
serving via MCP. All configuration is done through
a `config.yaml` file.

For parameter reference, see
[`configuration.md`](configuration.md).
For design rationale, see
[`architecture.md`](architecture.md).

## 1. Installation

```bash
pip install lore-mcp

# Multi-format parsing (PDF, HTML, DOCX)
pip install lore-mcp[parse]

# Or install specific format support
pip install lore-mcp[html]   # HTML via trafilatura
pip install lore-mcp[pdf]    # PDF/DOCX via Docling
```

## 2. Configuration

All settings are in a single `config.yaml` file.
No environment variables.

```yaml
# config.yaml
database:
  path: ./my-collection.db

embedding:
  model: nomic-ai/nomic-embed-text-v2-moe
  mode: builtin        # builtin, builtin:gpu, builtin:cpu, api

chunking:
  chunk_size: 1024
  chunk_overlap: 128

llm:
  model: granite-3-2-8b-instruct
  api_url: https://my-llm-endpoint/v1
  api_key: sk-...      # optional
```

Pass `--config config.yaml` to any command.

### Embedding modes

| Mode | Config | Use case |
|------|--------|----------|
| Builtin GPU | `mode: builtin` or `mode: builtin:gpu` | Local GPU, fastest |
| Builtin CPU | `mode: builtin:cpu` | No GPU, slower |
| Remote API | `mode: api` | TEI, vLLM, cloud |

For API mode, add:

```yaml
embedding:
  model: nomic-ai/nomic-embed-text-v2-moe
  mode: api
  api_url: http://127.0.0.1:8081/v1/embeddings
  api_verify: false    # if self-signed cert
```

### First run

The embedding model is downloaded from HuggingFace
on first use (~1 GB for Nomic v2 MoE). Subsequent
runs use the cache (`~/.cache/huggingface/`).

## 3. TEI containers (production embedding)

For persistent embedding services, run
HuggingFace Text Embeddings Inference (TEI)
containers. lore-mcp connects via API mode.

### GPU prerequisites

TEI GPU requires the NVIDIA Container Toolkit
and CDI (Container Device Interface) for Podman.

**1. Install nvidia-container-toolkit:**

```bash
sudo dnf install nvidia-container-toolkit
```

**2. Generate CDI specs:**

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
```

**3. Choose the TEI image tag by GPU
architecture:**

| GPU arch | Compute cap. | TEI tag |
|----------|-------------|---------|
| Ada Lovelace (RTX 40xx, RTX 500 Ada) | sm_89 | `89-latest` |
| Blackwell (RTX 50xx) | sm_120 | `120-1.9.3` |
| Other / unknown | — | `latest` (CPU fallback) |

> **CUDA 13.x note:** drivers 610+ ship CUDA
> 13.3. The `1.9.3` tag (CUDA 12.x) is
> incompatible. Use the architecture-specific tag.

### Nomic v2 MoE (project default, Level 2)

```bash
podman run --rm -d --name tei-nomic \
  --device nvidia.com/gpu=all \
  --security-opt=label=disable \
  -v ~/.cache/huggingface:/data \
  -e HF_HUB_DISABLE_TELEMETRY=1 \
  -p 8081:80 \
  ghcr.io/huggingface/text-embeddings-inference:89-latest \
  --model-id nomic-ai/nomic-embed-text-v2-moe \
  --port 80
```

### Granite R2 311M (Red Hat alternative, Level 3)

```bash
podman run --rm -d --name tei-granite \
  --device nvidia.com/gpu=all \
  --security-opt=label=disable \
  -v ~/.cache/huggingface:/data \
  -e HF_HUB_DISABLE_TELEMETRY=1 \
  -p 8082:80 \
  ghcr.io/huggingface/text-embeddings-inference:89-latest \
  --model-id ibm-granite/granite-embedding-multilingual-r2-311m \
  --port 80
```

### GPU notes

**Multi-model:** two TEI containers can run
simultaneously on different ports (8081/8082).

**localhost vs 127.0.0.1:** use `127.0.0.1` in
API URLs. `localhost` may resolve to IPv6 `::1`.

## 4. Preprocessing

Before building, preprocess your sources to
convert formats, clean content, and generate
an enriched manifest.

### Basic preprocess

```bash
lore-mcp preprocess manifest.yaml \
  --docs-base-dir /corpus/ \
  --orig-subdir raw/ \
  --prep-subdir clean/ \
  --config config.yaml
```

This:
1. Converts formats (PDF→md via Docling,
   HTML→md via trafilatura)
2. Cleans content (NFC, HTML strip, images→alt)
3. Detects duplicates (SHA-256 + MinHash, report)
4. Warns on PII (emails, IPs, API keys)
5. Validates quality (lint gate)
6. Produces enriched manifest (`manifest-prep.yaml`)

### With LLM enrichment

```bash
lore-mcp preprocess manifest.yaml \
  --docs-base-dir /corpus/ \
  --orig-subdir raw/ \
  --prep-subdir clean/ \
  --enrich context,qa \
  --config config.yaml
```

### Standalone enrichment

```bash
lore-mcp enrich manifest-prep.yaml \
  --docs-dir /corpus/clean/ \
  --output-dir /corpus/enriched/ \
  --enrich context,qa \
  --config config.yaml
```

See [preprocessing guide](preprocessing.md) for
best practices. Source quality has ~60% impact on
retrieval results.

## 5. Build workflow

The `build` command combines optimization,
indexing, and metadata generation.

### Minimal build (no optimization)

```bash
lore-mcp build manifest-prep.yaml \
  --docs-dir /corpus/clean/ \
  --output-dir /path/to/output/ \
  --skip-optimize \
  --config config.yaml
```

Produces: `.db` + `.json` + `.bib` + `.md` +
`build-report.json`.

### Build with optimization

```bash
lore-mcp build manifest-prep.yaml \
  --docs-dir /corpus/clean/ \
  --output-dir /path/to/output/ \
  --config config.yaml
```

Where `config.yaml` includes optimization params:

```yaml
embedding:
  model: nomic-ai/nomic-embed-text-v2-moe
  mode: builtin

llm:
  model: granite-3-2-8b-instruct
  api_url: http://127.0.0.1:11434/v1

optimize:
  chunk_sizes: [512, 1024, 2048]
  chunk_overlaps: [64, 128]
  top_ks: [3, 5, 10]
  num_questions: 50
```

### Build with integrated preprocess

```bash
lore-mcp build manifest.yaml \
  --docs-dir /corpus/ \
  --output-dir /path/to/output/ \
  --preprocess \
  --config config.yaml
```

### Output control

```bash
# Progress bar
lore-mcp build ... --progress

# Verbose (questions, per-iteration scores)
lore-mcp build ... --verbose

# Debug (HTTP requests, internals)
lore-mcp build ... --debug
```

### Resumability

If a build is interrupted, re-run the same
command — completed optimization configs are
skipped. Use `--force` to start fresh.

## 6. Quality check

```bash
lore-mcp lint manifest-prep.yaml \
  --docs-dir /corpus/clean/
```

Reports text density, heading count, noise
sections, and verdict (good/warn/poor) per file.

## 7. MCP server

### SSE (recommended)

```bash
lore-mcp --transport sse --config config.yaml
```

Client connects to `http://localhost:8000/sse`.

### stdio (subprocess)

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

### Search

The server exposes hybrid search (vector + FTS5
with RRF fusion). Both indexes are populated
automatically during build. No configuration
needed — hybrid search is always active when
FTS5 data exists.
