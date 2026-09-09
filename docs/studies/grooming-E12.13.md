# Grooming E12.13 — Proposition indexing

- **Status:** En attente validation
- **Date:** 2026-09-09

## Problem

Chunks contain mixed information. A query about
one fact matches a chunk about several facts.
Proposition indexing decomposes sections into
atomic statements, each indexed independently.
+22.5% over passage retrieval (E14.17).

## Solution

Add `--enrich props` mode to `enrich.py`.

### LLM prompt

```
Decompose this section into atomic, self-contained
propositions. Each proposition should be a single
factual statement that is true independent of
context. Output one proposition per line.

Section: {content}
```

### Output

Original:
```
## Authentication
SSO is configured via LDAP with TLS enabled.
The default timeout is 30 seconds.
```

Enriched (appended):
```
- SSO is configured via LDAP.
- TLS is enabled for SSO.
- The default SSO timeout is 30 seconds.
```

### Integration

Same pattern as `enrich_context()` and
`enrich_qa()` — per-section LLM call, append
result to section content.

### Cost

One LLM call per section. More expensive than
context/qa (~2x tokens). Suited for high-value
corpora, not bulk.

## DoD

1. `enrich_props()` in enrich.py
2. `--enrich props` CLI option
3. Test with mocked LLM
4. Test with real LLM endpoint

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
