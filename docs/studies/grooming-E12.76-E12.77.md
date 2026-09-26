# Grooming E12.76 + E12.77: State dir isolation and resilience

## Context

Pipeline validation (21 sources, `build --preprocess`)
crashed with `FileNotFoundError` on state dir writes.

Root cause analysis traced to `test_purge_all` in
`test_mcp_tools.py` calling `purge_pipeline_state(
purge_all=True)` on the **real** `~/.local/state/lore-mcp/`
directory — no isolation. A Claude Code fork ran
`pytest test_mcp_tools.py` at 23:14 CEST while the
pipeline was captioning frame 11/49 of a PPTX, deleting
the active state directory.

## E12.76 — Test state isolation

### Problem

Three tests touch the real state dir:
- `test_purge_all`: calls `purge_states(purge_all=True)`
- `test_purge_nonexistent`: harmless but should be isolated
- `test_with_state`: creates a real `Checkpoint` object

### Fix

`monkeypatch.setattr(checkpoint, "_state_dir", lambda: tmp_path)`
on all state-touching tests. Added regression test
`test_does_not_touch_real_state_dir` that verifies a
sentinel in the real state dir survives `purge_all`.

## E12.77 — Resilient state dir writes

### Problem

Two write points crash if the state dir is externally
deleted during a long-running pipeline:
- `parse.py:caption_inline_frames` — intermediate file
- `service.py:capture_service_logs` — IS log file

### Fix

Add `Path(...).parent.mkdir(parents=True, exist_ok=True)`
before each `write_text` call. Three points patched:
- `parse.py:354` (frame skip write)
- `parse.py:401` (frame caption write)
- `service.py:122` (IS logs write)
