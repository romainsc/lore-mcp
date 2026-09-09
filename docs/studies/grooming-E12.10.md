# Grooming E12.10 — Build integration config YAML

- **Status:** En attente validation
- **Date:** 2026-09-09

## Problem

`--preprocess` flag works in CLI but build-config
YAML does not support a `preprocess:` key. The
user cannot configure preprocessing in the YAML
alongside embedding/optimize settings.

## Solution

Add `preprocess:` key to `BuildConfig`:

```yaml
preprocess:
  enabled: true
  orig_subdir: orig
  prep_subdir: prep
  enrich: [context, qa]
  llm_model: granite-3-2-8b-instruct
```

`build_config.py:BuildConfig` reads the key.
`run_build()` uses it when `--preprocess` is
not explicitly set on CLI (CLI overrides YAML).

## DoD

1. `build_config.py` parses `preprocess:` key
2. `run_build()` uses config when CLI flag absent
3. Test: YAML config triggers preprocessing
4. Test: CLI `--preprocess` overrides YAML

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
