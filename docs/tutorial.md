# Tutorial — Running lore-mcp

This guide covers three ways to run lore-mcp
for embedding generation, and how to use the
build workflow to produce optimized collections.

For parameter reference, see
[`configuration.md`](configuration.md).
For design rationale, see
[`architecture.md`](architecture.md).

## 1. Builtin mode (simplest)

lore-mcp loads the embedding model directly in
its Python process via sentence-transformers.
No external service needed.

### GPU auto-detection

```bash
export LORE_EMBED_MODE=builtin  # default
export LORE_MODEL=nomic-ai/nomic-embed-text-v2-moe

python -c "
from lore_mcp.embedder import Embedder
emb = Embedder()
report = emb.assess()
print('GPU:', report['gpu']['message'])
print('CPU:', report['cpu']['message'])
"
```

If GPU VRAM is sufficient, the model loads on
GPU automatically. Otherwise, it falls back to
CPU.

### Force GPU or CPU

```bash
export LORE_EMBED_MODE=builtin:gpu   # crash if GPU unavailable
export LORE_EMBED_MODE=builtin:cpu   # always CPU
```

### First run

The model is downloaded from HuggingFace on first
use (~1 GB for Nomic v2 MoE). Subsequent runs
use the cache (`~/.cache/huggingface/`).

### Indexing with builtin

```python
from lore_mcp.embedder import Embedder
from lore_mcp.ingest import ingest_with_manifest

emb = Embedder()  # builtin mode, auto GPU/CPU
result = ingest_with_manifest(
    "manifest.yaml", "/path/to/docs/",
    "/path/to/output/", emb
)
```

## 2. TEI containers (production)

For persistent embedding services, run
HuggingFace Text Embeddings Inference (TEI)
containers. lore-mcp connects via API.

### Nomic v2 MoE (project default, Level 2)

```bash
podman run -d --name tei-nomic \
  -p 8081:80 \
  ghcr.io/huggingface/text-embeddings-inference:120-1.9.3 \
  --model-id nomic-ai/nomic-embed-text-v2-moe \
  --dtype float16
```

### Granite R2 311M (Red Hat alternative, Level 3)

```bash
podman run -d --name tei-granite \
  -p 8082:80 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id ibm-granite/granite-embedding-311m-multilingual-r2 \
  --dtype float16
```

### bge-m3 (historical reference, Level 4)

> **Derogation required.** bge-m3 is Level 4
> (opaque training data) per the project's free
> AI policy. Use only as a benchmark baseline.
> See [`adr/005-default-model-nomic.md`](adr/005-default-model-nomic.md).

```bash
podman run -d --name tei-bge \
  -p 8083:80 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
  --model-id BAAI/bge-m3 \
  --dtype float16
```

### GPU note

On a single GPU, run one TEI container at a time.
Stop the previous before starting the next:

```bash
podman stop tei-nomic && podman rm tei-nomic
podman run -d --name tei-granite ...
```

For CPU mode, add `--device cpu`:

```bash
podman run -d --name tei-nomic-cpu \
  -p 8081:80 \
  ghcr.io/huggingface/text-embeddings-inference:120-1.9.3 \
  --model-id nomic-ai/nomic-embed-text-v2-moe \
  --device cpu
```

### Connecting lore-mcp to TEI

```bash
export LORE_EMBED_MODE=api
export LORE_API_URL=http://localhost:8081/v1/embeddings
export LORE_MODEL=nomic-ai/nomic-embed-text-v2-moe
```

### Self-signed certificates (OpenShift)

For TEI endpoints behind OpenShift internal CA:

```bash
export LORE_API_VERIFY=false
# or
export LORE_API_CA_BUNDLE=/path/to/ca.pem
```

## 3. Remote API

lore-mcp can use any OpenAI-compatible embedding
endpoint — vLLM, Llama Stack, TEI on another
machine, cloud providers.

```bash
export LORE_EMBED_MODE=api
export LORE_API_URL=https://vllm-bge.example.com/v1/embeddings
export LORE_MODEL=BAAI/bge-m3
export LORE_API_VERIFY=false  # if self-signed cert
```

## 4. Build workflow

The `build` command combines optimization,
indexing, and metadata generation.

### Minimal build (no optimization)

```bash
lore-mcp build manifest.yaml \
  --docs-dir /path/to/sources/ \
  --output-dir /path/to/output/ \
  --skip-optimize
```

Produces: `.db` + `.json` + `.bib` + `.md` +
`build-report.json`.

### Build with optimization

```bash
lore-mcp build manifest.yaml \
  --docs-dir /path/to/sources/ \
  --output-dir /path/to/output/ \
  --models models.yaml
```

### Build with unified config

```bash
lore-mcp build manifest.yaml \
  --docs-dir /path/to/sources/ \
  --output-dir /path/to/output/ \
  --config build-config.yaml
```

Where `build-config.yaml`:

```yaml
embedding_models:
  - name: nomic-ai/nomic-embed-text-v2-moe
    mode: api
    api_url: http://localhost:8081/v1/embeddings
  - name: ibm-granite/granite-embedding-311m-multilingual-r2
    mode: api
    api_url: http://localhost:8082/v1/embeddings

judge:
  model: ibm-granite/granite-3.3-8b-instruct
  api_url: http://localhost:11434/v1

metrics:
  - score_spread
  - source_diversity
  - mrr

optimize:
  chunk_sizes: [512, 1024, 2048]
  chunk_overlaps: [64, 128]
  top_ks: [3, 5, 10]
  num_questions: 50
```

### Multi-model comparison

```bash
lore-mcp optimize \
  --source-dir /path/to/docs/ \
  --models "nomic-ai/nomic-embed-text-v2-moe,ibm-granite/granite-embedding-311m-multilingual-r2" \
  --output comparison-report.json
```

Or with TEI endpoints:

```bash
lore-mcp optimize \
  --source-dir /path/to/docs/ \
  --models models.yaml \
  --output comparison-report.json
```

### Resumability

If a build is interrupted, re-run the same
command — completed optimization configs are
skipped. Use `--force` to start fresh.

## 5. MCP server

### SSE (recommended)

```bash
LORE_DB_PATH=/path/to/collection.db \
  lore-mcp --transport sse
```

Client connects to `http://localhost:8000/sse`.

### stdio (subprocess)

```json
{
  "mcpServers": {
    "lore": {
      "command": "/path/to/.venv/bin/lore-mcp",
      "env": {
        "LORE_DB_PATH": "/path/to/collection.db"
      }
    }
  }
}
```
