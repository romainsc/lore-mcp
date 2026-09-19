# Grooming E12.35 — Judge prompt robustness + keep intermediates

- **Status:** Prêt
- **Date:** 2026-09-19

## Problem

1. Judge LLM selected a Molmo caption containing
   repetition loops (3.7K of repeated text) over
   the 12K OCR complete text
2. Phase2 files cleaned up by default —
   impossible to diagnose after the fact

## Solution

### Part A — Judge prompt robustness

The judge must detect repetition itself — no
heuristic pre-filter. Improve the prompt with
explicit criteria:

```
You are evaluating image descriptions from
multiple sources. Pick the BEST candidate.

Criteria (in priority order):
1. No repetition: reject any candidate that
   contains repeated text blocks or loops
2. Completeness: the candidate that preserves
   the most content from the source wins
3. Source language: prefer candidates in the
   original language of the document (do not
   prefer a translation over the original)
4. Faithfulness: no hallucinated or fabricated
   content
5. Structure: clear, well-organized for search
   indexing

Candidates:
--- ocr (12942 chars) ---
[preview]
--- granite-vision (850 chars) ---
[full text]
--- molmo-7b (3733 chars) ---
[preview]

Reply with ONLY the candidate name and a
one-sentence rationale.
Do NOT reproduce the candidate text.
```

Key changes from current prompt:
- Priority order (repetition first)
- Source language preference (FR document →
  prefer FR candidate)
- Char count shown per candidate (helps judge
  assess completeness)

### Part B — Keep intermediates (option)

New CLI option `--keep-intermediates` (default:
off). When enabled, phase files are NOT cleaned
up in phase 4.

Config: `preprocess.keep_intermediates: true`

Used for testing and diagnosis. Default behavior
unchanged.

## DoD

1. Judge prompt includes anti-repetition +
   completeness + source language criteria
2. Char count shown per candidate in judge prompt
3. `--keep-intermediates` CLI + config option
4. DUDH test: judge selects OCR or granite-vision
   (not a looping candidate)
5. Default behavior unchanged (files cleaned)
6. Tests pass

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
