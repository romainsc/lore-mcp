# Grooming E12.21 — URL list input

- **Status:** Prêt
- **Date:** 2026-09-10

## Solution

Detect `urls.txt` in `--docs-base-dir` during
preprocess. If present, fetch each URL into
`orig-subdir`. Sources added to enriched manifest.
No CLI parameter — convention-based detection.

Optional. Absence = no change.

## DoD

1. Detect `urls.txt` in docs-base-dir
2. Fetch into orig-subdir
3. Add to enriched manifest
4. Optional — no change if absent

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
