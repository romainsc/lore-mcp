# Grooming E10.10 — Rename mode `auto` → `builtin`

- **Status:** Grooming — en attente de validation
- **Date:** 2026-08-31

## Context

`LORE_EMBED_MODE=auto` is misleading — it suggests
automatic selection across all backends. In reality
it loads the model in-process via sentence-transformers
and picks GPU or CPU based on hardware.

The name should convey "lore-mcp does it itself"
— the embedding engine is built into lore-mcp.

## New modes

| Mode | Meaning |
|------|---------|
| `builtin` | In-process via sentence-transformers, auto-detects GPU/CPU (default) |
| `builtin:gpu` | In-process, force GPU (crash if unavailable) |
| `builtin:cpu` | In-process, force CPU |
| `api` | External HTTP endpoint |

`auto`, `gpu`, `cpu` are **removed** — no
backward compat, still in dev (v0.1.0-dev).

## Implementation

### Parsing (embedder.py)

```python
def _parse_mode(mode: str) -> tuple[str, str | None]:
    """Parse mode into (backend, device_override)."""
    if mode == "api":
        return ("api", None)
    if mode == "builtin":
        return ("builtin", None)
    if mode == "builtin:gpu":
        return ("builtin", "cuda")
    if mode == "builtin:cpu":
        return ("builtin", "cpu")
    raise ValueError(
        f"Unknown mode '{mode}'. "
        f"Valid: builtin, builtin:gpu, builtin:cpu, api"
    )
```

### Impact on _select_device_dtype

Current `gpu`/`cpu`/`auto` branches become:
- `builtin` → assess_gpu(), fallback CPU
- `builtin:gpu` → force CUDA, raise if unavailable
- `builtin:cpu` → force CPU

### Files to change

- `src/lore_mcp/embedder.py`: mode parsing,
  _select_device_dtype, assess(), embed()
- `src/lore_mcp/server.py`: default mode in
  _get_embedder, backend display in search_docs
- `src/lore_mcp/eval.py`: parse_model_configs_from_cli
  default mode
- `tests/`: all `mode="auto"` → `mode="builtin"`,
  all `mode="cpu"` → `mode="builtin:cpu"`,
  all `mode="gpu"` → `mode="builtin:gpu"`
- `CLAUDE.md`: env var table
- `docs/configuration.md`: LORE_EMBED_MODE section
- `docs/architecture.md`: fallback chain, modes
- `docs/code-guide.md`: embedder section
- `README.md`: env var table

## DoD

1. All `auto`/`gpu`/`cpu` references replaced
2. `_parse_mode()` with validation
3. `Embedder(mode="auto")` raises ValueError
4. Tests updated and passing
5. Documentation updated
6. EPUBs regenerated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
