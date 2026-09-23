# Container usage (Podman / Docker)

lore-mcp ships a `Containerfile` for building
a standalone OCI image with all dependencies.

## Build the image

```bash
podman build -t lore-mcp .
```

## Serve (MCP server)

### stdio (Claude Desktop, Claude Code)

```bash
podman run -i --rm \
  -v ./data:/data:Z \
  lore-mcp serve --config /data/config.yaml
```

Claude Desktop configuration
(`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "lore": {
      "command": "podman",
      "args": ["run", "-i", "--rm",
               "-v", "/path/to/data:/data:Z",
               "lore-mcp", "serve",
               "--config", "/data/config.yaml"]
    }
  }
}
```

### SSE (network access)

```bash
podman run -d -p 8080:8080 \
  -v ./data:/data:Z \
  lore-mcp serve --transport sse --port 8080
```

## Preprocess

Requires access to inference services (VLM, STT,
LLM) on the host via `--network host`.

```bash
podman run --rm --network host \
  -v ./corpus:/data:Z \
  -v ./config.yaml:/app/config.yaml:Z \
  lore-mcp preprocess /data/manifest.yaml \
    --docs-base-dir /data \
    --config /app/config.yaml \
    --verbose
```

## Build

```bash
podman run --rm --network host \
  -v ./corpus:/data:Z \
  -v ./config.yaml:/app/config.yaml:Z \
  lore-mcp build /data/manifest.yaml \
    --docs-dir /data/prep \
    --output-dir /data/out \
    --config /app/config.yaml
```

## Lint

```bash
podman run --rm \
  -v ./corpus:/data:Z \
  lore-mcp lint /data/manifest.yaml --docs-dir /data
```

## Notes

- `:Z` is required on SELinux systems (Fedora,
  RHEL) to relabel volumes for container access.
  Omit on non-SELinux systems.
- `--network host` gives the container access to
  host services (inference servers on localhost).
- GPU is not supported in the base image. For GPU
  inference, use `--device nvidia.com/gpu=all`
  (Podman CDI) or `--gpus all` (Docker).
- Docker users: replace `podman` with `docker`
  and remove `:Z` from volume mounts.
