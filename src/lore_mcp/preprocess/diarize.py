"""Speaker diarization via pyannote.audio or diarize. See E12.125."""

import logging
import subprocess
import tempfile
from pathlib import Path
from collections import defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)

_HAS_PYANNOTE = False
_HAS_DIARIZE = False
try:
    from pyannote.audio import Pipeline as _Pipeline
    _HAS_PYANNOTE = True
except ImportError:
    pass
try:
    import diarize as _diarize_lib
    _HAS_DIARIZE = True
except ImportError:
    pass


def _resolve_device(device: str) -> str:
    """Resolve 'auto' to 'gpu' or 'cpu'. Checks VRAM for auto."""
    if device in ("gpu", "cuda"):
        return "gpu"
    if device == "cpu":
        return "cpu"
    try:
        import torch
        if torch.cuda.is_available():
            vram_mb = torch.cuda.get_device_properties(0).total_memory // 1048576
            if vram_mb >= 4096:
                return "gpu"
            logger.warning("GPU VRAM %d MB < 4096 MB, using CPU for diarization", vram_mb)
    except ImportError:
        pass
    return "cpu"


def diarize_audio(audio_path: str, model_name: str, device: str = "auto") -> tuple[list[dict], str]:
    """Run speaker diarization on audio. Returns (speaker_turns, error).

    Each turn: {"speaker": "SPEAKER_00", "start": float, "end": float}.
    Supports pyannote.audio (model_name starts with 'pyannote')
    and diarize library (model_name 'diarize' or empty).
    Returns ([], error_message) on failure, (turns, "") on success.
    """
    if model_name.startswith("pyannote"):
        return _diarize_pyannote(audio_path, model_name, device)
    return _diarize_simple(audio_path)


def _to_wav(audio_path: str) -> str | None:
    """Convert audio to wav 16kHz mono for reliable diarization."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    try:
        subprocess.run(
            ["ffmpeg", "-i", audio_path, "-ar", "16000", "-ac", "1",
             "-y", tmp.name],
            capture_output=True, timeout=120,
        )
        if Path(tmp.name).stat().st_size > 0:
            return tmp.name
    except Exception as e:
        logger.warning("ffmpeg conversion failed: %s", e)
    Path(tmp.name).unlink(missing_ok=True)
    return None


def _diarize_pyannote(audio_path: str, model_name: str, device: str = "auto") -> tuple[list[dict], str]:
    if not _HAS_PYANNOTE:
        return [], "pyannote.audio not installed"
    wav_path = None
    try:
        pipeline = _Pipeline.from_pretrained(model_name)
        resolved = _resolve_device(device)
        if resolved == "gpu":
            import torch
            pipeline = pipeline.to(torch.device("cuda"))
            logger.info("pyannote diarization on GPU")
        else:
            logger.info("pyannote diarization on CPU")
        wav_path = _to_wav(audio_path)
        diarize_input = wav_path or audio_path
        result = pipeline(diarize_input)
        annotation = getattr(result, "speaker_diarization", result)
        turns = []
        for turn, _, speaker in annotation.itertracks(yield_label=True):
            turns.append({
                "speaker": speaker,
                "start": turn.start,
                "end": turn.end,
            })
        return turns, ""
    except Exception as e:
        logger.error("Diarization failed (pyannote): %s", e)
        return [], f"pyannote diarization failed: {e}"
    finally:
        if wav_path:
            Path(wav_path).unlink(missing_ok=True)


def _diarize_simple(audio_path: str) -> tuple[list[dict], str]:
    if not _HAS_DIARIZE:
        return [], "No diarization library installed (pip install diarize)"
    try:
        result = _diarize_lib.diarize(audio_path)
        turns = []
        for seg in result:
            turns.append({
                "speaker": seg.speaker,
                "start": seg.start,
                "end": seg.end,
            })
        return turns, ""
    except Exception as e:
        logger.error("Diarization failed (diarize): %s", e)
        return [], f"diarize failed: {e}"


def extract_speaker_audio(audio_path: str, turns: list[dict]) -> dict:
    """Extract and concatenate audio segments per speaker using ffmpeg.

    Returns {speaker_id: {"path": tmp_wav_path, "segments": [(abs_start, abs_end, rel_start, rel_end), ...]}}.
    """
    by_speaker = defaultdict(list)
    for turn in turns:
        by_speaker[turn["speaker"]].append((turn["start"], turn["end"]))

    result = {}
    for speaker, segs in by_speaker.items():
        segs.sort(key=lambda s: s[0])
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, prefix=f"lore-spk-{speaker}-")
        tmp.close()

        filter_parts = []
        for i, (start, end) in enumerate(segs):
            dur = end - start
            if dur < 0.05:
                continue
            filter_parts.append(
                f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[s{i}]"
            )

        if not filter_parts:
            Path(tmp.name).unlink(missing_ok=True)
            continue

        concat_inputs = "".join(f"[s{i}]" for i in range(len(filter_parts)))
        filter_complex = ";".join(filter_parts) + f";{concat_inputs}concat=n={len(filter_parts)}:v=0:a=1[out]"

        cmd = [
            "ffmpeg", "-y", "-i", audio_path,
            "-filter_complex", filter_complex,
            "-map", "[out]", "-ar", "16000", "-ac", "1",
            tmp.name,
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=300, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            logger.warning("ffmpeg extract failed for %s: %s", speaker, e)
            Path(tmp.name).unlink(missing_ok=True)
            continue

        segment_table = []
        rel_offset = 0.0
        for abs_start, abs_end in segs:
            dur = abs_end - abs_start
            if dur < 0.05:
                continue
            segment_table.append((abs_start, abs_end, rel_offset, rel_offset + dur))
            rel_offset += dur

        result[speaker] = {"path": tmp.name, "segments": segment_table}

    return result


def reconstruct_timeline(turns: list[dict], per_speaker: dict, title: str = "Audio") -> str:
    """Reconstruct a diarized markdown transcript from per-speaker STT results.

    turns: original diarization turns (chronological).
    per_speaker: {speaker_id: {"text": str, "segments": list[dict]}}.
    """
    speaker_map: dict[str, int] = {}
    lines = [f"# {title}\n"]

    speaker_consumed: dict[str, float] = defaultdict(float)

    current_speaker = None
    current_texts: list[str] = []
    current_start = 0.0

    def _flush():
        if current_texts and current_speaker:
            num = speaker_map.get(current_speaker, len(speaker_map) + 1)
            if current_speaker not in speaker_map:
                speaker_map[current_speaker] = num
            h = int(current_start // 3600)
            m = int((current_start % 3600) // 60)
            s = int(current_start % 60)
            ts = f"{h:02d}:{m:02d}:{s:02d}"
            lines.append(f"\n## Speaker {num} [{ts}]\n")
            lines.append(" ".join(current_texts) + "\n")

    for turn in sorted(turns, key=lambda t: t["start"]):
        speaker = turn["speaker"]
        turn_dur = turn["end"] - turn["start"]
        if turn_dur < 0.05:
            continue

        sp_data = per_speaker.get(speaker)
        if not sp_data:
            continue

        stt_segments = sp_data.get("segments", [])
        seg_table = sp_data.get("seg_table", [])
        consumed = speaker_consumed[speaker]

        turn_text_parts = []
        for stt_seg in stt_segments:
            seg_start = stt_seg.get("start", 0.0)
            seg_end = stt_seg.get("end", seg_start + 0.1)
            if seg_end <= consumed:
                continue
            if seg_start >= consumed + turn_dur + 0.5:
                break
            turn_text_parts.append(stt_seg.get("text", "").strip())

        if not turn_text_parts:
            full_text = sp_data.get("text", "")
            if full_text and consumed < len(full_text):
                chunk_len = max(1, int(len(full_text) * turn_dur / max(1, sp_data.get("total_dur", turn_dur))))
                chunk = full_text[int(consumed):int(consumed) + chunk_len].strip()
                if chunk:
                    turn_text_parts = [chunk]

        speaker_consumed[speaker] = consumed + turn_dur

        text = " ".join(turn_text_parts).strip()
        if not text:
            continue

        if speaker != current_speaker:
            _flush()
            current_speaker = speaker
            current_texts = [text]
            current_start = turn["start"]
        else:
            current_texts.append(text)

    _flush()
    return "\n".join(lines)


def align_speakers(
    segments: list[dict],
    speaker_turns: list[dict],
) -> list[dict]:
    """Align STT segments with speaker turns by temporal overlap."""
    if not segments:
        return []

    result = []
    for seg in segments:
        seg_start = seg.get("start", 0.0)
        seg_end = seg.get("end", seg_start + 0.1)
        seg_mid = (seg_start + seg_end) / 2.0

        best_speaker = "unknown"
        best_overlap = -1.0

        for turn in speaker_turns:
            t_start = turn["start"]
            t_end = turn["end"]
            overlap_start = max(seg_start, t_start)
            overlap_end = min(seg_end, t_end)
            overlap = max(0.0, overlap_end - overlap_start)

            if overlap > best_overlap:
                best_overlap = overlap
                best_speaker = turn["speaker"]

        if best_overlap <= 0 and speaker_turns:
            min_dist = float("inf")
            for turn in speaker_turns:
                dist = min(abs(seg_mid - turn["start"]), abs(seg_mid - turn["end"]))
                if dist < min_dist:
                    min_dist = dist
                    best_speaker = turn["speaker"]

        enriched = dict(seg)
        enriched["speaker"] = best_speaker
        result.append(enriched)

    return result


def format_diarized_markdown(
    segments: list[dict],
    title: str = "Audio",
) -> str:
    """Format diarized segments as markdown with speaker headings."""
    if not segments:
        return f"# {title}\n"

    speaker_map: dict[str, int] = {}
    lines = [f"# {title}\n"]

    current_speaker = None
    current_texts: list[str] = []
    current_start = 0.0

    def _flush():
        if current_texts and current_speaker:
            num = speaker_map.get(current_speaker, len(speaker_map) + 1)
            if current_speaker not in speaker_map:
                speaker_map[current_speaker] = num
            h = int(current_start // 3600)
            m = int((current_start % 3600) // 60)
            s = int(current_start % 60)
            ts = f"{h:02d}:{m:02d}:{s:02d}"
            lines.append(f"\n## Speaker {num} [{ts}]\n")
            lines.append(" ".join(current_texts) + "\n")

    for seg in segments:
        speaker = seg.get("speaker", "unknown")
        text = seg.get("text", "").strip()
        if not text:
            continue

        if speaker != current_speaker:
            _flush()
            current_speaker = speaker
            current_texts = [text]
            current_start = seg.get("start", 0.0)
        else:
            current_texts.append(text)

    _flush()
    return "\n".join(lines)
