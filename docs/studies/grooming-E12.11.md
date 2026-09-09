# Grooming E12.11 — Fix double clean_text

- **Status:** En attente validation
- **Date:** 2026-09-09
- **Type:** Bug

## Problem

`preprocess_sources()` calls `clean_text()` on
parsed content. Then `_ingest_file()` in
`ingest.py` calls `clean_text()` again. If
preprocess→build, content is cleaned twice.

NFC/HTML/image operations are idempotent, so
double clean doesn't corrupt data — but it wastes
cycles and makes the pipeline confusing.

## Fix

Remove `clean_text()` call from `_ingest_file()`.
Preprocessing is the responsibility of
`preprocess_sources()`. If a file is already
preprocessed (written to prep-subdir), ingest
should not re-clean it.

If build runs without preprocess (`--skip-optimize`
on raw markdown), the file goes through ingest
un-cleaned. This is acceptable — the user chose
to skip preprocessing.

## DoD

1. Remove `clean_text` import and call from
   `ingest.py:_ingest_file()`
2. Update test_ingest if needed
3. Verify: preprocess→build produces same result

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
