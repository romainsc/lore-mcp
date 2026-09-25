# Design: Service Lifecycle (Start/Stop)

## Context

lore-mcp uses external inference services (TEI for
embeddings, VLM for captioning, STT for transcription)
managed via start/stop commands in the LLM registry
(config.yaml).

## Lifecycle contract

1. **Start**: unconditional execution of the `start`
   command. Called once per service per process lifetime.
   The command is responsible for cleanup (e.g.,
   `podman rm -f <name>; podman run ...`).

2. **Wait for ready**: `_wait_for_health` polls the
   `/health` endpoint until 200 OK or timeout. Known
   limitation: some services (TEI) return 200 before
   the model is ready for inference (~10-15s gap).

3. **Use**: API calls with retry on transient errors
   (ReadError, RemoteProtocolError, TimeoutException,
   ConnectError). Initial probe (`_probe_api_dim`)
   uses linear retry (2s × 15 = 30s) to cover the
   health-to-ready gap.

4. **Stop**: unconditional execution of the `stop`
   command. Called on process exit (atexit), on
   failure after retry exhaustion, or on Ctrl+C.

## Invariants

- **Start once**: `_service_started` flag in
  `_get_embedder` ensures `start_service` is called
  exactly once. If embedder creation fails, subsequent
  calls skip start but retry embedder creation.

- **Stop on failure**: if all retries exhausted,
  `stop_service` is called to clean up the container.

- **No check-before-start**: the start command runs
  unconditionally. It's the user's responsibility to
  provide idempotent start commands (e.g., with
  `podman rm -f` prefix).

- **Signal safety**: signal handlers registered only
  in main thread (MCP serve runs tools in anyio
  worker threads where signal.signal fails).

## CLI vs MCP serve

| Aspect | CLI (build, preprocess) | MCP serve |
|--------|------------------------|-----------|
| Thread | Main thread | anyio worker thread |
| Lifecycle | start → use → stop per command | start on first query, stop on exit |
| Retry | Exception = process exit | Exception = return error, retry on next call |
| Signal | handlers registered | handlers skipped (threading guard) |

## Known issues

- TEI `/health` returns 200 before model is ready
  for inference. Mitigated by probe retries.
- IS provider fix requested: health should return
  200 only after a test inference succeeds.
