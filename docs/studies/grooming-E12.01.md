# Grooming E12.01 — Preprocessing tool design

- **Status:** Validé
- **Date:** 2026-09-07
- **Context:** Platform self-service tooling,
  E14.17 recommendations, E3.06 preprocessing
  guide

## Problem

lore-mcp documents preprocessing best practices
(docs/preprocessing.md) but provides minimal
tooling to apply them. The current `preprocess()`
(ingest.py:64) only handles NUL characters and
image→alt text replacement. Consumers must
manually clean their sources before indexing.

## Existing code

- `preprocess()` in `ingest.py:64` — NUL strip,
  image→alt text regex
- `lint.py` — source quality analysis (density,
  noise, headings, verdict)
- `_ingest_file()` in `ingest.py:99` — calls
  preprocess() then chunks
- `run_build()` in `build.py:49` — full build
  pipeline (no preprocessing stage)

## Solution

CLI subcommand `lore-mcp preprocess` implementing
RAG pipeline steps 1-3 (parse, clean, deduplicate).

### Architecture

```
Raw sources           Preprocessed markdown
(md/pdf/html/docx)    (clean, ready for build)
      │                        ▲
      ▼                        │
┌─────────────────────────────────────────┐
│           lore-mcp preprocess           │
│                                         │
│  1. Parse ──▶ 2. Clean ──▶ 3. Dedup    │
│       │            │            │       │
│   Docling      NFC norm     SHA-256     │
│  trafilatura   HTML strip   MinHash     │
│  (passthru     img→alt      Embedder    │
│   for .md)     PII warn     (semantic)  │
│   LLM tier 3   table tag               │
│                                         │
│  4. Validate (lint quality gate)        │
│  5. Enrich (opt-in, LLM)               │
└─────────────────────────────────────────┘

LLM usage (per E14.17 study):
- Step 1 tier 3: LLM for complex documents
  (Salesforce pattern: text → Docling → LLM)
- Step 3: Embedder for semantic dedup (cosine)
- Step 5: Claude for contextual retrieval, Q&A
  mode, proposition indexing, summaries
- Steps 2, 4: no LLM (regex, heuristics, lint)
```

### Pipeline steps

**Step 1 — Parse** (E12.03, depends on E6.06):
Convert non-markdown sources to markdown.
- `.md` files: passthrough (no conversion)
- `.pdf`, `.docx`: Docling (MIT, 97.9%)
- `.html`: trafilatura (GPL-3.0+, F1 0.966)
- 3-tier cascade (Salesforce/AWS Bedrock, E14.17):
  - Tier 1: plain markdown (no conversion)
  - Tier 2: Docling (structured PDF/DOCX)
  - Tier 3: LLM (complex docs, image-heavy —
    opt-in, requires LORE_LLM_URL or Claude)
- Output: one `.md` file per source

**Step 2 — Clean** (E12.02):
Normalize and sanitize text.
- Unicode NFC normalization
- Strip HTML residual tags
- Strip NUL characters (existing)
- Image → alt text (existing regex)
- Strip `#` from heading markers in content
- Tag tables for chunk protection (add sentinel
  markers that the chunker respects)
- PII detection: warn on emails, IPs, API keys,
  internal domains. Report-only, no auto-removal

**Step 3 — Deduplicate** (E12.04):
Remove duplicate content.
- Exact: SHA-256 hash per file → skip identical
- Near-duplicate: MinHash+LSH per section →
  report similar content with similarity score
- Semantic: Embedder cosine threshold → detect
  semantically equivalent content (uses lore-mcp
  Embedder, not LLM)
- Output: report of duplicates found, optionally
  remove

**Step 4 — Validate** (E12.07):
Quality gate using lint.
- Run `lint.py:analyze_file()` on each file
- Block `poor` files unless `--force`
- Warn on `warn` files
- Summary table in output

**Step 5 — Enrich** (E12.09, opt-in):
LLM-powered upstream enrichment.
- `--enrich context`: contextual retrieval
  (Claude adds context paragraph per section)
- `--enrich qa`: Q&A mode (Claude generates
  2-3 questions per section, appended)
- Requires `LORE_LLM_URL` or Claude API
- Not run by default — explicit opt-in

### CLI interface

```bash
# Basic: clean markdown sources
lore-mcp preprocess \
  --source-dir /path/to/raw/ \
  --output-dir /path/to/clean/

# With manifest (use manifest source list)
lore-mcp preprocess \
  --manifest manifest.yaml \
  --docs-base-dir /path/to/raw/ \
  --output-dir /path/to/clean/

# Multi-format with quality gate
lore-mcp preprocess \
  --source-dir /path/to/raw/ \
  --output-dir /path/to/clean/ \
  --formats md,pdf,html \
  --strict  # fail on poor quality files

# With LLM enrichment
lore-mcp preprocess \
  --source-dir /path/to/raw/ \
  --output-dir /path/to/clean/ \
  --enrich context,qa
```

### Config YAML integration

```yaml
preprocess:
  formats: [md, pdf, html]
  normalize: true       # NFC + HTML strip
  dedup: true           # SHA-256 + MinHash
  pii_warn: true        # report PII patterns
  quality_gate: warn    # warn | strict | off
  enrich: []            # context, qa, props
```

### Module structure

```
src/lore_mcp/preprocess/
├── __init__.py     # preprocess() pipeline
├── parse.py        # format conversion
├── clean.py        # normalization, sanitization
├── dedup.py        # deduplication
└── validate.py     # quality gate (wraps lint)
```

The existing `preprocess()` in `ingest.py` is
replaced by a call to the new module. Backward
compatible: the new module produces the same
output as the old function when given markdown
input with default config.

### Build integration (E12.10)

```
lore-mcp build manifest.yaml \
  --docs-dir /path/to/raw/ \
  --output-dir /output/ \
  --preprocess          # run preprocess first
```

Build workflow: preprocess → optimize → index →
metadata. Preprocessed files go to a temp dir,
build reads from there.

### Dependency impact

| Dependency | License | Step | Optional |
|-----------|---------|------|----------|
| docling | MIT | Parse | Yes (PDF/DOCX only) |
| trafilatura | GPL-3.0+ | Parse | Yes (HTML only) |
| datasketch | MIT | Dedup | Yes (MinHash) |

All compatible with AGPL-3.0. Parse dependencies
are optional — only installed if the user needs
non-markdown formats.

### MVP sequence

1. **MVP1**: E12.02 — text normalization (NFC,
   HTML strip, consolidate `preprocess()`). CLI
   `lore-mcp preprocess` with clean step only.
   Immediate value, no new dependencies.

2. **MVP2**: E12.04 + E12.07 — deduplication +
   quality gate. SHA-256 dedup + lint integration.
   Embedder for semantic dedup. One new optional
   dependency (datasketch).

3. **MVP3**: E12.08 — LLM capability study +
   wiring. Transversal foundation: shared LLM
   client, config (`LORE_LLM_URL` / Claude API),
   opt-in flag. Consumed by parse (MVP4) and
   enrich (MVP6). Must be wired before any LLM-
   dependent step.

4. **MVP4**: E12.03 — multi-format parsing.
   Docling + trafilatura + LLM tier 3 (consumes
   MVP3). Depends on E6.06 study. Two new
   optional dependencies.

5. **MVP5**: E12.05 + E12.06 — PII detection +
   table protection. Regex-based PII, table
   sentinel markers. No LLM.

6. **MVP6**: E12.09 — LLM enrichment (consumes
   MVP3). Contextual retrieval, Q&A mode,
   proposition indexing. Opt-in `--enrich`.

7. **MVP7**: E12.10 — build integration.
   `--preprocess` flag in `lore-mcp build`.

## DoD

1. Grooming artifact with architecture, CLI
   interface, config YAML, module structure,
   MVP sequence, dependency analysis
2. User validation before implementation

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
