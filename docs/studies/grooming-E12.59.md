# Grooming E12.59 — Graceful shutdown on SIGINT/SIGTERM

- **Status:** Prêt
- **Date:** 2026-09-23

## Problem

Ctrl+C during pipeline leaves IS containers
running and VRAM allocated. No cleanup on
interruption.

## Solution

atexit + signal handler. Track running services,
stop all on exit.

## DoD

1. Ctrl+C stops IS containers properly
2. No orphan containers after interruption
3. atexit + signal handler
4. Tests

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
