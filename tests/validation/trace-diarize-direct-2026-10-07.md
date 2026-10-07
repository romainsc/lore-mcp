# Trace diarization — test direct Python (hors MCP)

Date: 2026-10-07

## Test 1: 30s meeting audio

```python
diarize_audio('/tmp/Réunion...mp3' (30s extract),
              'pyannote/speaker-diarization-community-1', 'cpu')
```

- Turns: 15
- Speakers: SPEAKER_00, SPEAKER_01 (2)
- Note: 4 interlocuteurs réels, 2 détectés
  (contexte insuffisant sur 30s)

## Test 2: 25 min meeting audio (AVANT fix wav)

```python
diarize_audio('/tmp/Réunion...mp3' (complet),
              'pyannote/speaker-diarization-community-1', 'cpu')
```

- Turns: 0
- Error: "requested chunk [00:24:39 → 00:24:49]
  resulted in 432036 samples instead of 441000"
- Cause: mp3 durée inexacte, pyannote crash

## Test 3: 25 min meeting audio (APRÈS fix wav)

```python
diarize_audio('/tmp/Réunion...mp3' (complet),
              'pyannote/speaker-diarization-community-1', 'cpu')
```

- **Turns: 342**
- **Speakers: SPEAKER_00, SPEAKER_01, SPEAKER_02,
  SPEAKER_03 (4 — correct)**
- **Error: '' (aucune)**
- Time: 846s (14.1 min CPU)
- Fix: conversion wav 16kHz mono via ffmpeg
  avant pyannote

## Fixes appliqués

- `_to_wav()` dans diarize.py : ffmpeg conversion
  avant pyannote
- `_get_config()` : XDG fallback uniquement
- `.mcp.json` : `--config` déjà passé

## À valider par session validation

1. Redémarrer le serveur MCP (pour charger le
   nouveau code + config via --config)
2. `preprocess_source(file="/tmp/Réunion...mp3",
   enrich="speaker_id",
   speakers="Christine et Sonia (enseignantes),
   Sarah et Romain (parents)")`
3. Vérifier: diarization 4 speakers + per-speaker
   STT + speaker identification LLM
