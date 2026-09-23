# Grooming E12.58 — Unified --allow-download flag

- **Status:** Prêt
- **Date:** 2026-09-23

## Problem

Source URL downloads happen silently. Model
downloads require --allow-download. Inconsistent.

## Solution

Single --allow-download flag gates both:
- Source URL-only fetches (manifest)
- Model downloads (HuggingFace builtin)

Without flag: error with clear message.

## DoD

1. allow_download in LoreConfig
2. _fetch_url checks flag
3. Clear error if URL-only without flag
4. --allow-download on preprocess and build CLI
5. Tests

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
