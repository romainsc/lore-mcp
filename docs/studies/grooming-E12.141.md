# Grooming E12.141 — Skip global STT when diarization configured

## Problem

Phase 1.6 (global STT) runs BEFORE phase 1.5
(diarization + per-speaker STT). When both are
configured, phase 1.6 sets data["text"], which
causes phase 1.5's per-speaker STT condition
(`not data.get("text")`) to be False — the
per-speaker path is never reached.

This also explains E12.142: diarization executes
but per-speaker STT is skipped because text
already exists from global STT.

## Root cause (E12.142)

Line 959: `if stt_entry and not data.get("text"):`

After phase 1.6 sets data["text"], this condition
is always False. The per-speaker STT (E12.138)
was dead code.

## Fix

Define `skip_global_stt` early (before E12.129
placeholder detection). When diarize_entry is
configured with a model:
- Phase 1.6 is skipped entirely for audio/video
- E12.129 placeholder detection silently clears
  the placeholder (no error report)
- Phase 1.5 runs with data["text"] = None,
  triggering per-speaker STT

## DoD

- Phase 1.6 skipped when diarization configured
- Phase 1.5 per-speaker STT executes correctly
- Non-diarized path unchanged (regression-safe)
- E12.129 placeholder not reported as error
  when diarization handles it
- Tests pass
- CI green
