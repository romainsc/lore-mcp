# Grooming E3.04 — Documentation reorganization

- **Status:** En attente validation
- **Date:** 2026-09-09

## Problem

The documentation has grown organically. Tutorial
mixes with configuration reference. README doesn't
reflect the current state (preprocessing tool,
multi-format parsing, manifest v2).

## Solution

1. **Separate tutorial from reference**: tutorial.md
   = how to run (step-by-step), configuration.md =
   exhaustive parameter reference
2. **Update README**: reflect current features
   (preprocess, build, lint, eval, optimize),
   manifest v2 format, installation with extras
   `[parse]`, `[html]`, `[pdf]`
3. **Update architecture.md**: preprocessing
   pipeline (preprocess/ module), manifest v2
   cascade

### Content audit

| File | Current state | Action |
|------|--------------|--------|
| README.md | Missing preprocess, manifest v2, extras | Update |
| tutorial.md | Preprocess section added but brief | Expand |
| configuration.md | Manifest v2 updated | Verify complete |
| architecture.md | Manifest v2 updated | Add preprocess module section |
| preprocessing.md | Complete but pre-E12 | Update with CLI examples |

## DoD

1. README reflects current features and install
2. Tutorial has complete preprocess→build workflow
3. Configuration reference is exhaustive
4. Architecture documents preprocess module
5. No stale information

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
