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
  --orig-dir raw/ \
  --prep-dir clean/ \
  --config config.yaml
```

This:
1. Converts formats (PDF→md via Docling,
   HTML→md via trafilatura, audio→md via STT,
   video→md+frames via STT+ffmpeg)
2. Cleans content (NFC, HTML strip, images→alt,
   collapse repeated characters)
3. Detects duplicates (SHA-256 + MinHash, report)
4. Warns on PII (emails, IPs, API keys)
5. Validates quality (lint gate with structure
   scoring)
6. Produces enriched manifest (`manifest-prep.yaml`)

### With LLM enrichment

```bash
lore-mcp preprocess manifest.yaml \
  --docs-base-dir /corpus/ \
  --orig-dir raw/ \
  --prep-dir clean/ \
  --enrich context,qa,meta \
  --config config.yaml
```

### Audio and video sources

Audio (.mp3, .wav, .opus) and video (.mp4, .webm)
files are transcribed via STT (configured as
`parse.stt_model` in config). Video frames are
extracted at scene changes and captioned by VLM.

The `lang` field in the manifest sets the
transcription language:

```yaml
sources:
  - orig: talk.opus
    lang: eng
  - orig: conference.webm
    lang: fra
    video_frame_strategy: ocr  # scene|interval|hybrid|ocr
```

Frame extraction strategies:
- `scene` (default): ffmpeg scene change detection
- `interval`: fixed interval (every N seconds)
- `hybrid`: scene + interval merged
- `ocr`: OCR-guided — keeps only frames where
  slide content changes (best for filmed
  presentations)

URL sources require `--allow-download`:

```bash
lore-mcp preprocess manifest.yaml \
  --docs-base-dir /corpus/ \
  --allow-download \
  --config config.yaml
```

### YouTube / platform video download (yt-dlp)

For YouTube and other video platforms, use a URL
in the manifest — no manual download needed.
If captions are available (auto-generated or
manual), lore-mcp downloads them and skips the
STT service entirely.

```yaml
sources:
  - url: https://www.youtube.com/watch?v=eEBv0STiYhI
    lang: en
  - url: https://www.youtube.com/watch?v=WYszRcHzqw8
    lang: fr
```

Requires the `[video]` extra:
```bash
pip install -e ".[video]"  # installs yt-dlp
```

Files are named by video ID (short, unique) —
full title is stored in the enriched manifest.
`--allow-download` is required.

### Pipeline state management

Pipeline state (checkpoint, intermediates) is
stored in `~/.local/state/lore-mcp/`. Manage
with:

```bash
# List all states
lore-mcp state --list

# Purge a specific state
lore-mcp state --purge <hash-prefix>

# Purge old states (> 7 days)
lore-mcp state --purge --older-than 7

# Purge all
lore-mcp state --purge --all
```

### Keep intermediate files

```bash
lore-mcp preprocess manifest.yaml \
  --docs-base-dir /corpus/ \
  --intermediates-dir /corpus/intermediates/ \
  --config config.yaml
```

Saves phase files (`.phase1-parse.md`,
`.caption-*.md`, `.phase3-enrich.md`) to the
specified directory for diagnosis. Without this
flag, intermediates go to
`~/.local/state/lore-mcp/` and are cleaned up
after success.

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

Where `config.yaml` includes models in the
unified registry and optimization params:

```yaml
llm:
  - name: nomic-embed
    model: nomic-ai/nomic-embed-text-v2-moe
    api_url: http://127.0.0.1:8082/v1/embeddings
    start: podman run -d --name tei-nomic ...
    stop: podman stop tei-nomic

embedding:
  model: nomic-embed   # references llm registry
  mode: api

optimize:
  chunk_sizes: [512, 1024, 2048]
  chunk_overlaps: [64, 128]
  top_ks: [3, 5, 10]
  num_questions: 50
```

All models (embedding, VLM, STT, LLM) are in the
`llm:` registry with start/stop lifecycle.
Specialized sections reference them by name.
Services are auto-started and auto-stopped.

### Full pipeline (preprocess + optimize + build)

```bash
lore-mcp build manifest.yaml \
  --docs-dir /corpus/ \
  --output-dir /output/ \
  --preprocess \
  --orig-dir raw/ \
  --prep-dir prep/ \
  --intermediates-dir /output/intermediates/ \
  --allow-download \
  --config config.yaml
```

Single command: preprocess → optimize → build.
Produces: `.db` + `.json` + `.bib` + `.md` +
`manifest-prep.yaml` + intermediate files.

### Declarative DB sync

Subsequent builds are incremental: unchanged
sources are skipped (SHA-256 hash comparison),
changed sources are re-indexed, sources removed
from the manifest are purged. `--force` rebuilds
everything.

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
