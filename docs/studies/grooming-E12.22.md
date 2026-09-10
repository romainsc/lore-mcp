# Grooming E12.22 — Untreated files report

- **Status:** Prêt
- **Date:** 2026-09-10

## Solution

Write `preprocess-report.json` to output dir.
Exit code 1 if any files not treated. Warnings
(PII, duplicates) do not change exit code.

### Report format

```json
{
  "ok": ["doc1.md", "doc2.md"],
  "missing": ["gone.md"],
  "error": [{"file": "bad.xyz", "message": "..."}],
  "pii": [{"file": "doc1.md", "findings": [...]}],
  "duplicates": [{"file": "doc2.md", "type": "..."}]
}
```

### Exit codes

- 0: all files treated (ok)
- 1: at least one file not treated (missing,
  error, fetch failed, quality gate failed)

PII and duplicate warnings = exit 0.

## DoD

1. `preprocess-report.json` written automatically
2. `sys.exit(1)` if untreated files
3. Warnings (PII, duplicates) = exit 0
4. Machine-readable for pipeline integration

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
