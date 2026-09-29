# Grooming E12.95 + E12.96 + E12.97: Validation

## E12.95 — Validation CLI end-to-end

All IS scripts in `scripts/` (self-contained).
Config in `tests/validation/config-validation.yaml`.
Recipe in `tests/validation/recipe-validation.yaml`.

### IS scripts

| Script | Service | Usage |
|---|---|---|
| start-tei.sh | TEI embedding | build, optimize, serve |
| start-vlm-granite.sh | granite-vision | captioning |
| start-vlm-molmo.sh | molmo-7b | captioning |
| start-stt.sh | canary STT | video transcription |
| start-llm.sh | LLM generic | enrichment, RAGAS judge |

Each: parameterized (port, CPU/GPU, model), checks
prerequisites, no external dependency.

### All 9 metrics

```yaml
judge:
  metrics:
    - score_spread
    - source_diversity
    - result_diversity
    - hit
    - word_overlap
    - mrr
    - faithfulness
    - context_recall
    - answer_correctness
```

### Script

`tests/validation/validate_cli.py`:
preprocess → build (optimize + RAGAS) → eval → lint → search.
Criteria: 0 errors, scores > 0, relevant results.
Executable < 10 min with GPU.

## E12.96 — Validation MCP via SDK

Programmatic test of all MCP tools via Python SDK.
No LLM needed — direct tool calls with assertions.

`tests/validation/validate_mcp_sdk.py`

## E12.97 — Validation MCP via LLM

Natural language playbook, same questions before
and after indexing.

### Playbook structure

Phase 1 — Before indexing (baseline):
  Q1-Q4 asked and answers saved.

Phase 2 — Index collection via MCP.

Phase 3 — After indexing (same Q1-Q4):
  Compare with baseline. Q1-Q3 must be better.
  Q4 (out of corpus) must remain the same.

Phase 4 — Incremental: add, verify, remove, verify.

Phase 5 — From scratch: single document, LLM
  must ask or infer missing params.

### Assertions

- expect_better_than: after > before for in-corpus
- expect_same_as: after == before for out-of-corpus
- expect_tools: LLM chose the right MCP tool
- expect_behavior: LLM asked for missing info

### Dependencies

E3.09a-d (TaskManager, start_build, add_source)
for phases 2, 4, 5. Without E3.09, only phases
1 and 3 are testable.
