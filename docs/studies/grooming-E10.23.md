# Grooming E10.23 — Fix RAGAS import crash

- **Status:** Validé
- **Date:** 2026-09-01

## Context

ragas 0.4.3 imports ChatVertexAI from
langchain_community at import time.
langchain-community was sunset May 2026,
the module was removed. ragas crashes on
Python 3.14.

## Fix

Stub the missing module before importing ragas.
Verified working — Faithfulness and ContextRecall
metrics are available after stub.

## DoD

1. Stub in eval.py before ragas import
2. Keep ragas>=0.4 in [eval]
3. Test: ragas imports without crash
4. Document workaround and why

## Provenance

> This document was produced with AI assistance
> (Claude, Anthropic) and reviewed by
> Romain Chantereau.
