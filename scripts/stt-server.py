"""Serveur STT Canary-1B-v2 — API OpenAI.

IS local — CPU FP32 (~0.56x realtime).
API compatible OpenAI:
  POST /v1/audio/transcriptions
  GET /health
  GET /v1/models

Paramètres de transcription exposés :

OpenAI standard :
  file            : fichier audio (requis)
  model           : nom du modèle (ignoré)
  language        : langue source ISO 639-1
  response_format : json | verbose_json | text
  timestamp_granularities[] : word | segment

NeMo spécifiques :
  target_lang     : langue cible (traduction)
  pnc             : ponctuation (yes/no, défaut yes)
  timestamps      : activer timestamps (true/false)
  chunk_len       : durée chunk en sec (défaut 40)
"""
import torch
import time
import os
import uuid
import tempfile
import subprocess

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse, PlainTextResponse
from typing import Optional

MODEL_ID = os.environ.get(
    "STT_MODEL", "nvidia/canary-1b-v2")
PORT = int(os.environ.get("STT_PORT", "8080"))
DEFAULT_PNC = os.environ.get("STT_PNC", "1") == "1"
DEFAULT_TS = os.environ.get(
    "STT_TIMESTAMPS", "1") == "1"

app = FastAPI(
    title="STT Canary-1B-v2",
    description="OpenAI-compatible STT API "
    "backed by NVIDIA Canary-1B-v2 (NeMo)")

model = None
load_time = 0
inference_ok = False


@app.on_event("startup")
def load_model():
    global model, load_time, inference_ok
    import nemo.collections.asr as nemo_asr

    device = "cuda" if torch.cuda.is_available() \
        else "cpu"
    print(f"Loading {MODEL_ID} on {device}...")

    if device == "cuda":
        free, total = torch.cuda.mem_get_info()
        print(f"VRAM: {round(free/1e9,2)} Go libre")

    t0 = time.time()
    model = nemo_asr.models \
        .EncDecMultiTaskModel.from_pretrained(
            model_name=MODEL_ID)
    if device == "cuda":
        model = model.cuda()
    else:
        model = model.cpu()
    model.eval()
    load_time = round(time.time() - t0, 1)
    print(f"Model loaded in {load_time}s")

    if device == "cuda":
        free2, _ = torch.cuda.mem_get_info()
        used = round((free - free2) / 1e9, 2)
        print(f"VRAM used: {used} Go")

    try:
        import numpy as np
        import soundfile as sf
        probe = np.zeros(16000, dtype=np.float32)
        p = "/tmp/probe.wav"
        sf.write(p, probe, 16000)
        model.transcribe([p])
        os.unlink(p)
        if device == "cuda":
            torch.cuda.empty_cache()
        inference_ok = True
        print("Inference probe OK")
    except Exception as e:
        print(f"Inference probe FAILED: {e}")
        inference_ok = False


@app.get("/health")
def health():
    ready = model is not None and inference_ok
    result = {"status": "ok" if ready else "loading"}
    if model and torch.cuda.is_available():
        free, _ = torch.cuda.mem_get_info()
        result["vram_margin_gb"] = \
            round(free / 1e9, 2)
    return result


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [{
            "id": MODEL_ID,
            "object": "model",
            "owned_by": "nvidia",
        }],
    }


def _convert_to_mono_wav(src: str) -> str:
    """Convert any audio to mono 16kHz WAV."""
    dst = src + ".mono.wav"
    subprocess.run(
        ["ffmpeg", "-i", src,
         "-ar", "16000", "-ac", "1",
         dst, "-y"],
        capture_output=True, timeout=300)
    if os.path.exists(dst):
        os.unlink(src)
        return dst
    return src


def _extract_hypothesis(item):
    """Extract text, segments, words from NeMo."""
    text = ""
    segments = []
    words = []

    if item is None:
        return text, segments, words

    if hasattr(item, 'text'):
        text = item.text
    elif isinstance(item, str):
        text = item
    elif isinstance(item, dict):
        text = item.get('text', str(item))
    else:
        text = str(item)

    if hasattr(item, 'timestamp') and item.timestamp:
        ts = item.timestamp
        if isinstance(ts, dict):
            for seg in ts.get('segment', []):
                segments.append({
                    "start": seg.get('start', 0.0),
                    "end": seg.get('end', 0.0),
                    "text": seg.get('segment', ''),
                })
            for w in ts.get('word', []):
                words.append({
                    "start": w.get('start', 0.0),
                    "end": w.get('end', 0.0),
                    "word": w.get('word', ''),
                })

    return text, segments, words


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(
        ..., description="Audio file"),
    model: Optional[str] = Form(
        None, description="Model name (ignored)"),
    language: Optional[str] = Form(
        None,
        description="Source language ISO 639-1"),
    target_lang: Optional[str] = Form(
        None,
        description="Target language for "
        "translation (NeMo)"),
    response_format: Optional[str] = Form(
        "json",
        description="json | verbose_json | text"),
    pnc: Optional[str] = Form(
        None,
        description="Punctuation: yes | no "
        "(default: yes)"),
    timestamps: Optional[str] = Form(
        None,
        description="Enable timestamps: "
        "true | false (default: true)"),
    chunk_len: Optional[float] = Form(
        None,
        description="Chunk duration in seconds "
        "(default: 40.0)"),
    timestamp_granularities: Optional[str] = Form(
        None,
        description="word | segment (OpenAI compat,"
        " both always returned if timestamps on)"),
):
    audio_bytes = await file.read()
    suffix = os.path.splitext(
        file.filename or "")[1] or ".wav"

    with tempfile.NamedTemporaryFile(
        suffix=suffix, delete=False
    ) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    tmp_path = _convert_to_mono_wav(tmp_path)

    use_ts = DEFAULT_TS
    if timestamps is not None:
        use_ts = timestamps.lower() in (
            "true", "1", "yes")
    use_pnc = DEFAULT_PNC
    if pnc is not None:
        use_pnc = pnc.lower() in (
            "yes", "true", "1", "pnc")

    print(f"[REQ] file={file.filename}, "
          f"size={len(audio_bytes)//1024} Ko, "
          f"lang={language}, "
          f"pnc={use_pnc}, "
          f"timestamps={use_ts}, "
          f"chunk_len={chunk_len}")

    try:
        t0 = time.time()
        kwargs = {}
        if language:
            kwargs["source_lang"] = language
        if target_lang:
            kwargs["target_lang"] = target_lang
        if chunk_len is not None:
            kwargs["chunk_len_in_secs"] = chunk_len

        results = globals()["model"].transcribe(
            [tmp_path], batch_size=1,
            timestamps=use_ts,
            pnc="yes" if use_pnc else "no",
            **kwargs)
        dt = time.time() - t0

        if isinstance(results, tuple):
            items = results[0]
        else:
            items = results

        item = items[0] if items else None
        text, segments, words = \
            _extract_hypothesis(item)

        import soundfile as sf
        try:
            audio_duration = \
                sf.info(tmp_path).duration
        except Exception:
            audio_duration = dt

        import gc
        del results, items, item
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        rss = os.popen(
            "cat /proc/self/status "
            "| grep VmRSS"
        ).read().strip()
        print(f"[MEM] {rss}, "
              f"transcribe={round(dt,1)}s")

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {
                "message": str(e),
                "type": "server_error",
            }})
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    usage = {
        "type": "duration",
        "seconds": int(audio_duration),
    }

    if response_format == "verbose_json":
        api_segments = []
        for i, seg in enumerate(segments):
            api_segments.append({
                "id": i,
                "seek": 0,
                "start": seg.get("start", 0.0),
                "end": seg.get("end", 0.0),
                "text": seg.get("text", ""),
                "tokens": [],
                "temperature": 0.0,
                "avg_logprob": 0.0,
                "compression_ratio": 0.0,
                "no_speech_prob": 0.0,
            })
        return {
            "task": "transcribe",
            "language": language or "en",
            "duration": round(audio_duration, 2),
            "text": text,
            "segments": api_segments,
            "words": words if words else None,
            "usage": usage,
        }

    if response_format == "text":
        return PlainTextResponse(text)

    return {"text": text, "usage": usage}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, host="0.0.0.0", port=PORT,
        timeout_keep_alive=600)
