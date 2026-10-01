# Grooming E3.17: Exhaustive MCP validation

## Context

E12.95-97 validation found 3 critical bugs
(E3.14-16) that unit tests missed. Several MCP
tools remain untested in integration:
start_optimize, cancel_task, purge_pipeline_state,
start_build, start_preprocess, start_enrich,
start_eval via SDK. The add/search/remove cycle
was only tested manually.

## Scope

Enrich `validate_mcp_sdk.py` to cover all 17
MCP tools programmatically. No LLM needed —
direct Python imports.

## Coverage matrix

### Currently tested (validate_mcp_sdk.py)

1. list_indexed_sources
2. get_service_status
3. lint_source
4. list_pipeline_state
5. list_tasks
6. search_docs

### To add

7. add_source → search_docs → remove_source cycle
8. start_build (mock run_build)
9. start_preprocess (mock preprocess_sources)
10. start_eval (real, on existing .db)
11. start_optimize (mock run_optimize)
12. start_enrich (mock preprocess_sources)
13. cancel_task (start slow task + cancel)
14. get_task_status (already used implicitly)
15. purge_pipeline_state (create state + purge)
16. list_collections (single-collection mode)
17. search_docs with filter param

## Implementation

### MVP1: add/search/remove cycle

```python
# Create temp .md, add_source, search, remove, verify
doc = create_temp_doc("platypus content")
add_source(doc, build_dir)
# poll get_task_status until completed
results = search_docs("platypus")
assert "platypus" in results
remove_source("doc.md", build_dir)
results = search_docs("platypus")
assert "platypus" not in results  # or low score
```

### MVP2: long-running tools via mock

For tools that launch background tasks, mock the
underlying function and verify:
- Returns task_id
- get_task_status shows completed
- Result is accessible

### MVP3: cancel + purge

- Start a slow mock task, cancel immediately
- Create checkpoint state, purge it, verify gone

## DoD

- validate_mcp_sdk.py tests all 17 MCP tools
- add/search/remove cycle passes without error
- No transient errors
- Exit 0 = all passed, exit 1 = any failure
- validate_cli.py: add `lore-mcp optimize` step

## Risks

- add/search/remove needs TEI running (embedder)
- start_eval needs a .db with content
- Mocking long-running tools may miss real issues
