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

### GPU prerequisites

TEI GPU requires the NVIDIA Container Toolkit
and CDI (Container Device Interface) for Podman.

**1. Install nvidia-container-toolkit:**

```bash
# Fedora / RHEL
sudo dnf install nvidia-container-toolkit
```

**2. Generate CDI specs:**

```bash
sudo nvidia-ctk cdi generate --output=/etc/cdi/nvidia.yaml
```

Without this step, Podman errors with
`unresolvable CDI devices`.

**3. Choose the TEI image tag by GPU
architecture:**

| GPU arch | Compute cap. | TEI tag |
|----------|-------------|---------|
| Ada Lovelace (RTX 40xx, RTX 500 Ada) | sm_89 | `89-latest` |
| Blackwell (RTX 50xx) | sm_120 | `120-1.9.3` |
| Other / unknown | — | `latest` (CPU fallback) |

Using the wrong tag causes
`CUDA_ERROR_SYSTEM_DRIVER_MISMATCH` — TEI falls
back to CPU (10× slower).

> **CUDA 13.x note:** drivers 610+ ship CUDA
> 13.3. The `1.9.3` tag (CUDA 12.x) is
> incompatible. Use the architecture-specific
> tag (`89-latest`, `120-1.9.3`).

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

API: `http://127.0.0.1:8081/v1/embeddings`

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

API: `http://127.0.0.1:8082/v1/embeddings`

### bge-m3 (historical reference, Level 4)

> **Derogation required.** bge-m3 is Level 4
> (opaque training data) per the project's free
> AI policy. Use only as a benchmark baseline.
> See [`adr/005-default-model-nomic.md`](adr/005-default-model-nomic.md).

```bash
podman run --rm -d --name tei-bge \
  --device nvidia.com/gpu=all \
  --security-opt=label=disable \
  -v ~/.cache/huggingface:/data \
  -e HF_HUB_DISABLE_TELEMETRY=1 \
  -p 8083:80 \
  ghcr.io/huggingface/text-embeddings-inference:89-latest \
  --model-id BAAI/bge-m3 \
  --port 80
```

### GPU notes

**Multi-model:** two TEI containers can run
simultaneously on different ports (8081/8082).
The GPU time-slices between them. Estimated
VRAM: Nomic ~1.2 GB + Granite R2 ~0.8 GB =
~2 GB on a 4 GB GPU (RTX 500 Ada).

**localhost vs 127.0.0.1:** use `127.0.0.1` in
API URLs. `localhost` may resolve to IPv6 `::1`,
causing connection refused.

**HuggingFace cache:** the `-v
~/.cache/huggingface:/data` mount avoids
re-downloading models (~1 GB) on each container
start.

For CPU mode (no GPU or fallback):

```bash
podman run --rm -d --name tei-nomic-cpu \
  -p 8081:80 \
  ghcr.io/huggingface/text-embeddings-inference:latest \
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
