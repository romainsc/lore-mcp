# Grooming E2.03 — CI/CD with GitHub Actions

- **Status:** Prêt
- **Date:** 2026-09-22

## Problem

No CI — tests run only locally. No automated
validation on push or PR.

## Solution

GitHub Actions workflow running pytest on every
push and pull request.

## Constraints

- ~430 tests, some subprocess-based (~5 min)
- No GPU in CI (CUDA tests already skipped)
- Dependencies: sqlite-vec, sentence-transformers,
  docling, tesseract
- Python 3.14 (may need deadsnakes PPA or
  3.13 fallback)

## Workflow

```yaml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - checkout
      - setup-python 3.14 (or 3.13 fallback)
      - apt install tesseract-ocr tesseract-ocr-fra
      - pip install -e ".[parse,enrich,eval]"
      - pip install pytest
      - pytest
```

## Risks

- Python 3.14 availability in setup-python
- Docling heavy deps (torch CPU, onnxruntime)
  → long build, cache pip
- Subprocess tests may timeout in CI

## DoD

1. pytest passes in CI on every push
2. Status badge in README
3. No silently skipped tests (except GPU)

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
