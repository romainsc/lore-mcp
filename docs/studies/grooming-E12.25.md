# Grooming E12.25 — Inference service lifecycle

- **Status:** Prêt
- **Date:** 2026-09-15

## Solution

Config `start`/`stop` commands per model in llm
registry. Health check after start. Stop in
finally block.

```yaml
llm:
  - name: molmo-7b
    model: allenai/Molmo2-O-7B
    api_url: http://127.0.0.1:8090/v1
    start: "ollama run molmo2"
    stop: "ollama stop molmo2"
```

## DoD

1. `start`/`stop` optional fields in llm registry
2. Health check after start (poll /health or
   /v1/models, configurable timeout)
3. Stop in finally (even on error)
4. No start/stop = verify accessibility only

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
