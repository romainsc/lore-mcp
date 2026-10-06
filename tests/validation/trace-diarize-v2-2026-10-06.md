# Trace E12.125 — Diarization test v2

Date: 2026-10-06
Command: `preprocess_source(file="/tmp/Réunion...mp3", collection="test-diarize-v2", enrich="speaker_id", force=true)`
Task: 37e840fa

## Result: FAIL
- file_count: 1
- Elapsed: 1729s (~29 min)
- Output: 103 bytes placeholder only

## Root cause
STT container not started. `preprocess_source` (E3.43) does not
start inference services (STT, VLM). The pipeline ran for 29 min
but produced only the placeholder `[Audio file — requires STT
service for transcription]`.

No error reported — task completed successfully with empty output.

## Bugs identified

### 1. preprocess_source does not start inference services
E3.43 preprocess-only MCP tools must start required services
(STT for audio, VLM for images) just like add_source does.
Currently services are only started by the add_source/add_directory
path.

### 2. Silent STT failure
When STT service is unavailable, the pipeline should report
an error, not silently output the placeholder. 29 min wasted
with no indication of failure.

### 3. E12.126 cleanup removes evidence
The .work/ directory was cleaned up (E12.126), making it
impossible to diagnose what happened during the 29 min run.
preprocess_source should keep .work/ since prep/ is the
deliverable (same as CLI preprocess).

## Config verified
- `diarization_model: pyannote-diarize` ✓ (visible in get_config)
- `pyannote-diarize` in LLM registry ✓
- `target_lang` auto-set fix in parse.py ✓
- But none exercised because STT never ran
