# Grooming E10.21 — YAML key consistency

- **Status:** Validé
- **Date:** 2026-09-01

## Context

Two entry points accept model lists:
- `--models file.yaml` → `parse_model_configs()`
  expects key `models:`
- `--config file.yaml` → `BuildConfig.from_file()`
  expects key `embedding_models:`

A user who writes `embedding_models:` in a
`--models` file gets silently empty model list.
A user who writes `models:` in a `--config` file
gets the same.

## Fix

Accept both keys in both contexts:
- `parse_model_configs()`: try `models:`, fall
  back to `embedding_models:`
- `BuildConfig.from_file()`: try
  `embedding_models:`, fall back to `models:`
- If neither key present and models expected:
  error with clear message listing both valid keys

## DoD

1. Both keys accepted in parse_model_configs
2. Both keys accepted in BuildConfig.from_file
3. Clear error if neither key found
4. Tests TDD
5. Documentation updated

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
