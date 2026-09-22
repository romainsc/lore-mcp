# Grooming E12.33 — Test infrastructure for subprocess phase 1

- **Status:** Prêt
- **Date:** 2026-09-22

## Problem

Since E12.31, phase 1 parse runs in a subprocess.
Tests cannot assert on phase 1 console output.
`_phase1_worker` is not tested directly.

## Solution

Test `_phase1_worker` directly (not through
subprocess). It's a pure function that reads
files and writes phase1 outputs + report JSON.
No VRAM involved for markdown parsing.

### Tests

1. Parse a markdown file → phase1-parse.md written
2. Parse produces report JSON with status
3. Missing file → error in report
4. Multiple files → all parsed
5. OCR lang from manifest propagated

No VRAM verification tests (would need GPU).

## DoD

1. `_phase1_worker` tested directly (5+ tests)
2. Report JSON structure validated
3. Phase1 output files validated
4. Error cases covered

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
