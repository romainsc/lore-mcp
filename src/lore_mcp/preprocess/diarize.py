"""Speaker diarization via pyannote.audio or diarize. See E12.125."""

import logging

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


def diarize_audio(audio_path: str, model_name: str) -> tuple[list[dict], str]:
    """Run speaker diarization on audio. Returns (speaker_turns, error).

    Each turn: {"speaker": "SPEAKER_00", "start": float, "end": float}.
    Supports pyannote.audio (model_name starts with 'pyannote')
    and diarize library (model_name 'diarize' or empty).
    Returns ([], error_message) on failure, (turns, "") on success.
    """
    if model_name.startswith("pyannote"):
        return _diarize_pyannote(audio_path, model_name)
    return _diarize_simple(audio_path)


def _diarize_pyannote(audio_path: str, model_name: str) -> tuple[list[dict], str]:
    if not _HAS_PYANNOTE:
        return [], "pyannote.audio not installed"
    try:
        pipeline = _Pipeline.from_pretrained(model_name)
        result = pipeline(audio_path)
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


def align_speakers(
    segments: list[dict],
    speaker_turns: list[dict],
) -> list[dict]:
    """Align STT segments with speaker turns by temporal overlap.

    Each segment gets a 'speaker' field based on which turn
    has the most overlap with the segment's time span.
    """
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
    """Format diarized segments as markdown with speaker headings.

    Consecutive segments from the same speaker are merged.
    Speakers are numbered: SPEAKER_00 → Speaker 1.
    """
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
