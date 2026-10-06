# Trace E12.125 — Diarization test attempt

Date: 2026-10-06
Command: `preprocess_source(file="/tmp/Réunion suivi école sophie 6 octobre 2026.mp3", collection="test-diarize", enrich="speaker_id", force=true)`
Task: a0975f2b

## Result: INCONCLUSIVE
- file_count: 1
- Elapsed: 1895s (~31.5 min)
- Output: workspace-validation/build/test-diarize/prep/Réunion suivi école sophie 6 octobre 2026.md (20 Ko)

## Observations

### 1. No diarization applied
Output contains only timestamps (`## [HH:MM:SS]`), no speaker labels (`## Speaker 1`).
Phase 1.5 diarization was not triggered.

### Root cause
Config.yaml was modified AFTER the MCP server started.
`get_config` output does NOT show:
- `parse.diarization_model` field
- `pyannote-diarize` in LLM registry
The MCP server loads config once at startup — no dynamic reload.

### 2. STT still translates FR→EN
Despite E12.127 (params passthrough) being implemented, the STT
still produces English output for French audio.
Missing: `params: {language: "fr"}` in canary-stt config entry.

### 3. get_config does not expose diarization_model
Even after config reload, `get_config` may not show this field
(not verified — server not restarted in this session).

## Action required
1. Restart MCP server to pick up config changes
2. Add `params: {language: "fr"}` to canary-stt LLM registry entry
3. Verify `get_config` exposes `diarization_model`
4. Re-run this test after restart
