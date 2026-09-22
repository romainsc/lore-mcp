# Grooming E10.08 — Auto-configure embedding model from .db meta

- **Status:** Prêt
- **Date:** 2026-09-22

## Problem

Receiving a third-party .db requires knowing
which embedding model was used. The model is
stored in the `meta` table but the server
refuses to query if the configured model doesn't
match.

## Solution

When config does not specify `embedding.model`,
read `model_name` from the .db `meta` table at
first DB load and use it.

### Behavior matrix

| Config model | DB model | Result |
|---|---|---|
| not set | present | auto-configure from DB |
| same | present | OK |
| different | present | error (existing behavior) |

## DoD

1. Config without `embedding.model` → at DB load,
   read `model_name` from `meta` and configure
2. Clear error if model not found in HF cache
3. Tests

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
