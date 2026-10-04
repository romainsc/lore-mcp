# Grooming E12.106 — add_recipe progress not reported

## Bug

`get_task_status()` returns only "running" +
elapsed time for add_recipe tasks. No phase info
(parsing 3/5, embedding 12/15, etc.).

`report_progress()` from task_manager.py is
available but not wired into `run_build()` when
called via `add_recipe`.

Progress files exist in `.work/` but the
TaskManager doesn't read them.

## Fix

Wire `report_progress()` calls into `run_build`
at key points:
- Before preprocess: "Preprocessing N sources"
- Before optimization: "Optimizing (config M/N)"
- Before indexing: "Indexing N files"
- Before metadata: "Generating metadata"

`report_progress()` detects the running task via
`threading.current_thread()._task_info` — no
parameter changes needed.

## DoD

- `get_task_status()` returns phase info during
  add_recipe execution
- At least 3 progress updates visible during a
  typical build
- Test: start add_recipe, poll status, verify
  progress message non-empty
- CI green

## MVP

Single fix — add `report_progress()` calls in
`run_build`.
