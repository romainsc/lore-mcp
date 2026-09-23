# Grooming E12.61 — Preserve source directory tree

- **Status:** Prêt
- **Date:** 2026-09-23

## Problem

Two files with the same name in different
subdirectories collide in prep/ output.

## Solution

prep/ mirrors orig/ tree structure. Path in
manifest-prep reflects relative path including
subdirectory.

## DoD

1. Preprocess preserves tree orig → prep
2. manifest-prep path: subdir/doc.md
3. No collision on same-name files
4. Build indexes with full relative path
5. Tests

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
