# Grooming E3.09: Full MCP control

## Design decisions

### Recipe file
- Rename manifest → recipe
- Two sections: `sources` (what) + `options` (how)
- `file` replaces `orig` (neutral naming)
- `path` removed (derived from file in build_dir/prep/)
- Recipe is read-only input, never modified by lore-mcp
- URL fallback: if file absent + url present → download
- Template available as MCP resource

### MCP tool design
- Instance config (config.yaml) implicit — loaded at serve
- Recipe path + build_dir = the only params for build
- force = only inline flag
- Short ops (search, lint): synchronous, return result
- Long ops (build, preprocess, enrich): async, return task_id

### TaskManager architecture
- Subprocess-based (not threads) — memory isolation
- Semaphore(1) for long-running ops (MVP)
- Progress via status file in build_dir/.work/
- MCP serve process stays lightweight (~20 MB)
- search_docs unaffected by running builds

### .db lifecycle during build
- Build writes to collection.db.tmp
- Atomic rename when complete
- search_docs reloads connection on next query

### add_source upsert pattern
- add_source = insert or update (hash-based via E6.01)
- No recipe needed — operates on build_dir .db directly
- .db sources table = source of truth for indexed content

### Resource management (future)
- Semaphore per resource type (GPU, CPU, network)
- Item E3.13 — deferred, MVP uses global semaphore

## Items

### E3.09a — TaskManager framework
- task_manager.py: TaskInfo, TaskManager (subprocess, semaphore)
- MCP tools: get_task_status, cancel_task
- Progress callback mechanism
- Test: start mock task → poll → complete/cancel

### E3.09b — start_build MCP tool
- Wraps run_build in subprocess
- Params: recipe, build_dir, force
- Progress from build phases

### E3.09c — start_preprocess MCP tool
- Wraps preprocess_sources in subprocess
- Params: recipe, build_dir, force

### E3.09d — add_source + remove_source
- add_source: upsert (async) — preprocess + ingest one file
- remove_source: sync — delete from .db
- Params: file, build_dir, url, title, lang

### E3.09e — start_eval + start_optimize
- Wrap eval/optimize in subprocess

### E3.09f — start_enrich
- Wrap enrich in subprocess
- Can run in parallel with build (different resources)

### E3.13 — Resource-aware task scheduling
- Semaphore per resource type (GPU, CPU, network)
- Task declares required resources
- Concurrent tasks if resources don't conflict

## Related items
- E12.91 — Add lang to sources table
- E12.92 — Rename orig → file, remove path
- E12.93 — Rename manifest → recipe (code + CLI + docs)
