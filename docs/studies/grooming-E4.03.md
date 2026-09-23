# Grooming E4.03 — Container image (Podman/Docker)

- **Status:** Prêt
- **Date:** 2026-09-23

## Solution

OCI container image with full lore-mcp runtime.
All commands: serve, build, preprocess, eval,
lint, enrich. Data via volume mounts.

## Dockerfile

Multi-stage build:
- Builder: Python 3.13-slim + system deps + pip install
- Runtime: slim image with installed venv

System deps: tesseract-ocr, tesseract-ocr-fra,
tesseract-ocr-eng, ffmpeg.

## Usage (Podman first, Docker compatible)

```bash
# Serve (MCP stdio)
podman run -i --rm -v ./data:/data:Z \
  lore-mcp serve --config /data/config.yaml

# Serve (SSE)
podman run -d -p 8080:8080 -v ./data:/data:Z \
  lore-mcp serve --transport sse --port 8080

# Preprocess (IS on host)
podman run --rm --network host -v ./data:/data:Z \
  lore-mcp preprocess /data/manifest.yaml \
    --docs-base-dir /data --config /data/config.yaml

# Build
podman run --rm --network host -v ./data:/data:Z \
  lore-mcp build /data/manifest.yaml \
    --docs-dir /data/prep --output-dir /data/out \
    --config /data/config.yaml

# Lint
podman run --rm -v ./data:/data:Z \
  lore-mcp lint /data/manifest.yaml --docs-dir /data
```

## Claude Desktop config

```json
{
  "mcpServers": {
    "lore": {
      "command": "podman",
      "args": ["run", "-i", "--rm",
               "-v", "./data:/data:Z",
               "lore-mcp", "serve",
               "--config", "/data/config.yaml"]
    }
  }
}
```

## Notes

- `:Z` for SELinux relabel (Podman/Fedora)
- `--network host` for IS access (VLM, STT, LLM)
- GPU: `--device nvidia.com/gpu=all` (Podman CDI)
  vs `--gpus all` (Docker). Not in MVP.
- Image is CPU-only. ~5 GB with torch + docling.

## DoD

1. Containerfile (Dockerfile) multi-stage
2. `podman build` produces working image
3. serve (stdio + SSE) functional
4. build/preprocess with volume mounts
5. .containerignore (.db, corpus, .venv, .git)
6. docs/docker.md with all usage examples
7. examples/mcp-config.example.json updated
8. Tests: build image + run --help

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
