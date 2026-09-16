# Grooming E12.27 — Progressive output and VLM resilience

- **Status:** Prêt
- **Date:** 2026-09-16

## Problem

1. Pipeline keeps everything in memory until
   phase 4. If VLM or LLM crashes, nothing is
   saved to disk. No visibility on progress.
2. One VLM timeout crashes the entire pipeline.
   49 PPTX images × 2 VLM calls = 98 sequential
   calls. Icons/logos captioned uselessly.
3. No way to know which phases ran, which were
   skipped, or where a failure occurred.

## Solution

### Part A — Progressive file output

Each phase writes its result to disk with a
phase suffix. Final file has no suffix.

```
prep/
  doc.phase1-parse.md
  doc.phase2-caption.md     (only if VLM ran)
  doc.phase3-enrich.md      (or phase3-clean.md)
  doc.md                    (final, after phase 4)
```

Implementation:
- Phase 1: write `{name}.phase1-parse.md`
- Phase 2: read phase1, caption, write
  `{name}.phase2-caption.md`
- Phase 3: read latest phase file, clean+enrich,
  write `{name}.phase3-enrich.md` (or
  `phase3-clean.md` if no enrich)
- Phase 4: validate, rename to `{name}.md`,
  delete intermediate phase files

If pipeline crashes, intermediate files remain
for debugging and resumability.

### Part B — Phase announcement

Stdout at start:
```
Active phases: parse, caption (VLM: molmo-7b),
  clean+enrich (LLM: granite-8b,
  techniques: context+qa+meta)
```

Stdout at end:
```
Phases completed: parse (18/18),
  caption (3 images, 2 skipped),
  clean+enrich (18/18), write (18/18)
```

Report (`preprocess-report.json`) includes:
```json
{
  "phases": ["parse", "caption", ...],
  "vlm": "molmo-7b",
  "llm": "granite-8b",
  "enrich_techniques": ["context", "qa", "meta"]
}
```

### Part C — VLM resilience

1. **Per-image try/except**: timeout or error on
   one image → log warning, continue to next.
   Never crash the pipeline for a single image.

2. **Size filter**: skip images < 10KB raw
   (~13KB base64). These are icons, bullets,
   decorative elements. Log as skipped.

3. **Content-hash dedup**: hash base64 data
   before sending. Same image appearing N times
   → one VLM call, reuse caption for all
   occurrences. Common in PPTX (logos, headers).

4. **Circuit breaker**: after 3 consecutive VLM
   failures, stop captioning remaining images
   for this document. Log warning. Continue
   pipeline to phase 3.

## Implementation order

MVP1: Part C (VLM resilience) — unblocks testing
MVP2: Part A (progressive output)
MVP3: Part B (phase announcement)

## DoD

1. VLM timeout on one image does not crash pipeline
2. Images < 10KB skipped with log message
3. Duplicate images captioned once
4. Circuit breaker after 3 consecutive failures
5. Each phase writes to disk with phase suffix
6. Final file has no suffix after validation
7. Active phases announced at start and summarized
   at end
8. Report includes phase metadata
9. Tests for all resilience patterns
10. Existing tests still pass

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
