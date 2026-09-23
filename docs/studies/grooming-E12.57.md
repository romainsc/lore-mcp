# Grooming E12.57 — Standardize API URL convention

- **Status:** Prêt
- **Date:** 2026-09-23

## Problem

Code hardcodes path appending in 6 places:
`if not url.endswith("/chat/completions"): url += ...`
Inconsistent: embedding probe doesn't append,
VLM/STT/enrich do. Breaks when api_url is already
complete or uses non-OpenAI paths.

## Convention

`api_url` in the registry is the **full endpoint
URL**. The code uses it as-is. No path appending.

```yaml
llm:
  - name: nomic-embed
    api_url: http://host:8082/v1/embeddings
  - name: granite-vision
    api_url: http://host:8092/v1/chat/completions
  - name: canary-stt
    api_url: http://host:8093/v1/audio/transcriptions
  - name: granite-8b
    api_url: https://maas.example.com/v1/chat/completions
```

### Health check

`health_url` optional in registry. Default:
derived from api_url by stripping path after
host:port and appending `/health`.

```
http://host:8082/v1/embeddings → http://host:8082/health
```

Override for non-standard services:
```yaml
  - name: ollama
    api_url: http://host:11434/v1/chat/completions
    health_url: http://host:11434/
```

## Changes

Remove all hardcoded path appending:

| File | Line pattern | Remove |
|------|-------------|--------|
| enrich.py | `if not url.endswith("/chat/completions")` | ✓ |
| parse.py ×4 | `if not url.endswith("/chat/completions")` | ✓ |
| parse.py ×1 | `if not url.endswith("/audio/transcriptions")` | ✓ |

Update _health_url to support health_url field.

## DoD

1. api_url used as-is everywhere (no path append)
2. Remove 6 hardcoded path appending blocks
3. health_url optional in registry
4. Config updated with full endpoint URLs
5. Tests
6. Documentation updated

## Sources

- vLLM: /v1/* standard
- TEI: /embed (native) + /v1/embeddings (compat)
- Ollama: /api/* (native) + /v1/* (compat)
- Health: /health quasi-standard (except Ollama)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
