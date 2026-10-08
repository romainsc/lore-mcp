"""Tests for E12.125: speaker diarization and alignment."""

import pytest
from unittest.mock import patch, MagicMock


class TestAlignSpeakers:
    """Align STT segments with diarization speaker turns."""

    def test_single_speaker(self):
        from lore_mcp.preprocess.diarize import align_speakers

        segments = [
            {"text": "Hello world", "start": 0.0, "end": 1.5},
            {"text": "How are you", "start": 2.0, "end": 3.0},
        ]
        turns = [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 5.0},
        ]
        result = align_speakers(segments, turns)
        assert len(result) == 2
        assert result[0]["speaker"] == "SPEAKER_00"
        assert result[1]["speaker"] == "SPEAKER_00"

    def test_two_speakers(self):
        from lore_mcp.preprocess.diarize import align_speakers

        segments = [
            {"text": "Hello I'm Alice", "start": 0.5, "end": 1.5},
            {"text": "Hi Alice I'm Bob", "start": 2.0, "end": 3.5},
            {"text": "Nice to meet you", "start": 4.0, "end": 5.0},
        ]
        turns = [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 2.0},
            {"speaker": "SPEAKER_01", "start": 2.0, "end": 4.0},
            {"speaker": "SPEAKER_00", "start": 4.0, "end": 6.0},
        ]
        result = align_speakers(segments, turns)
        assert result[0]["speaker"] == "SPEAKER_00"
        assert result[1]["speaker"] == "SPEAKER_01"
        assert result[2]["speaker"] == "SPEAKER_00"

    def test_empty_segments(self):
        from lore_mcp.preprocess.diarize import align_speakers

        result = align_speakers([], [{"speaker": "SPEAKER_00", "start": 0, "end": 5}])
        assert result == []

    def test_empty_turns(self):
        from lore_mcp.preprocess.diarize import align_speakers

        segments = [{"text": "Hello", "start": 0.0, "end": 1.0}]
        result = align_speakers(segments, [])
        assert len(result) == 1
        assert result[0].get("speaker", "unknown") == "unknown"

    def test_segment_spans_two_turns(self):
        from lore_mcp.preprocess.diarize import align_speakers

        segments = [
            {"text": "Long sentence spanning two speakers", "start": 1.5, "end": 3.5},
        ]
        turns = [
            {"speaker": "SPEAKER_00", "start": 0.0, "end": 2.0},
            {"speaker": "SPEAKER_01", "start": 2.0, "end": 5.0},
        ]
        result = align_speakers(segments, turns)
        assert len(result) == 1
        assert result[0]["speaker"] in ("SPEAKER_00", "SPEAKER_01")


class TestFormatDiarizedMarkdown:
    """Format aligned segments as markdown with speaker headings."""

    def test_basic_format(self):
        from lore_mcp.preprocess.diarize import format_diarized_markdown

        segments = [
            {"text": "Hello I'm Alice", "start": 0.5, "speaker": "SPEAKER_00"},
            {"text": "Hi Alice", "start": 2.0, "speaker": "SPEAKER_01"},
            {"text": "Nice to meet you", "start": 4.0, "speaker": "SPEAKER_00"},
        ]
        md = format_diarized_markdown(segments, "Meeting")
        assert "# Meeting" in md
        assert "Speaker 1" in md
        assert "Speaker 2" in md
        assert "Hello I'm Alice" in md

    def test_consecutive_same_speaker_merged(self):
        from lore_mcp.preprocess.diarize import format_diarized_markdown

        segments = [
            {"text": "First sentence.", "start": 0.5, "speaker": "SPEAKER_00"},
            {"text": "Second sentence.", "start": 1.5, "speaker": "SPEAKER_00"},
            {"text": "Other person.", "start": 3.0, "speaker": "SPEAKER_01"},
        ]
        md = format_diarized_markdown(segments, "Test")
        assert md.count("Speaker 1") == 1
        assert "First sentence. Second sentence." in md


class TestDiarizeAudioGraceful:
    """diarize_audio skips gracefully when pyannote not installed."""

    def test_skip_without_pyannote(self):
        from lore_mcp.preprocess.diarize import diarize_audio

        turns, error = diarize_audio("/fake/audio.mp3", "fake-model")
        assert turns == []
        assert error  # should have an error message

    def test_error_surfaced_on_failure(self):
        from lore_mcp.preprocess.diarize import diarize_audio

        turns, error = diarize_audio("/nonexistent/audio.mp3", "diarize")
        assert turns == []
        assert "failed" in error.lower() or "not installed" in error.lower()


class TestEnrichSpeakerId:
    """enrich_speaker_id replaces anonymous labels with LLM-inferred names."""

    def test_with_hint(self):
        from lore_mcp.preprocess.enrich import enrich_speaker_id
        from lore_mcp.preprocess.llm import LLMConfig

        text = (
            "# Meeting\n\n"
            "## Speaker 1 [00:00:00]\n\n"
            "Hello I'm presenting today\n\n"
            "## Speaker 2 [00:01:00]\n\n"
            "Thank you for the presentation\n"
        )
        mock_llm = LLMConfig(api_url="http://fake", model="fake")

        with patch("lore_mcp.preprocess.enrich.call_llm") as mock_call:
            mock_call.return_value = '{"Speaker 1": "Alice", "Speaker 2": "Bob"}'
            result = enrich_speaker_id(
                text, speakers_hint="Alice presents, Bob asks questions",
                llm=mock_llm,
            )
        assert "Alice" in result
        assert "Bob" in result
        assert "Speaker 1" not in result

    def test_without_hint(self):
        from lore_mcp.preprocess.enrich import enrich_speaker_id
        from lore_mcp.preprocess.llm import LLMConfig

        text = (
            "## Speaker 1 [00:00:00]\n\n"
            "Hi I'm John from marketing\n\n"
            "## Speaker 2 [00:01:00]\n\n"
            "Welcome John\n"
        )
        mock_llm = LLMConfig(api_url="http://fake", model="fake")

        with patch("lore_mcp.preprocess.enrich.call_llm") as mock_call:
            mock_call.return_value = '{"Speaker 1": "John", "Speaker 2": "Speaker 2"}'
            result = enrich_speaker_id(text, llm=mock_llm)
        assert "John" in result

    def test_no_speaker_labels_passthrough(self):
        from lore_mcp.preprocess.enrich import enrich_speaker_id
        from lore_mcp.preprocess.llm import LLMConfig

        text = "## Section\n\nRegular document without speakers.\n"
        mock_llm = LLMConfig(api_url="http://fake", model="fake")
        result = enrich_speaker_id(text, llm=mock_llm)
        assert result == text


class TestExtractSpeakerAudio:
    """E12.138: extract and concat audio segments per speaker."""

    def test_groups_by_speaker(self):
        from lore_mcp.preprocess.diarize import extract_speaker_audio
        from unittest.mock import patch
        import subprocess

        turns = [
            {"speaker": "S01", "start": 0.0, "end": 3.0},
            {"speaker": "S02", "start": 3.0, "end": 5.0},
            {"speaker": "S01", "start": 5.0, "end": 8.0},
        ]

        with patch("lore_mcp.preprocess.diarize.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0)
            result = extract_speaker_audio("/fake/audio.mp3", turns)

        assert "S01" in result
        assert "S02" in result
        s01_segs = result["S01"]["segments"]
        assert len(s01_segs) == 2
        assert s01_segs[0] == (0.0, 3.0, 0.0, 3.0)
        assert s01_segs[1] == (5.0, 8.0, 3.0, 6.0)

    def test_empty_turns(self):
        from lore_mcp.preprocess.diarize import extract_speaker_audio

        result = extract_speaker_audio("/fake/audio.mp3", [])
        assert result == {}

    def test_skipped_short_segments_contiguous_labels(self):
        """E12.148: segments < 0.05s must not break ffmpeg filter labels."""
        from lore_mcp.preprocess.diarize import extract_speaker_audio
        from unittest.mock import patch, call
        import subprocess

        turns = [
            {"speaker": "S01", "start": 0.0, "end": 2.0},
            {"speaker": "S01", "start": 2.0, "end": 2.03},  # < 0.05s, skipped
            {"speaker": "S01", "start": 2.1, "end": 5.0},
            {"speaker": "S01", "start": 5.0, "end": 5.01},  # < 0.05s, skipped
            {"speaker": "S01", "start": 5.1, "end": 7.0},
        ]

        with patch("lore_mcp.preprocess.diarize.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess([], 0)
            result = extract_speaker_audio("/fake/audio.mp3", turns)

        assert "S01" in result
        # 3 valid segments (indices 0, 2, 4 in original list)
        assert len(result["S01"]["segments"]) == 3

        # Verify ffmpeg filter_complex has contiguous labels [s0][s1][s2]
        cmd = mock_run.call_args[0][0]
        fc_idx = cmd.index("-filter_complex")
        filter_complex = cmd[fc_idx + 1]
        assert "[s0]" in filter_complex
        assert "[s1]" in filter_complex
        assert "[s2]" in filter_complex
        # Must NOT contain non-contiguous labels from enumerate
        assert "[s3]" not in filter_complex
        assert "[s4]" not in filter_complex
        assert "concat=n=3" in filter_complex

    def test_ffmpeg_failure_skips_speaker(self):
        from lore_mcp.preprocess.diarize import extract_speaker_audio
        from unittest.mock import patch

        turns = [{"speaker": "S01", "start": 0.0, "end": 3.0}]

        with patch("lore_mcp.preprocess.diarize.subprocess.run", side_effect=FileNotFoundError("ffmpeg not found")):
            result = extract_speaker_audio("/fake/audio.mp3", turns)

        assert result == {}


class TestReconstructTimeline:
    """E12.138: reconstruct timeline from per-speaker STT."""

    def test_basic_reconstruction(self):
        from lore_mcp.preprocess.diarize import reconstruct_timeline

        turns = [
            {"speaker": "S01", "start": 0.0, "end": 3.0},
            {"speaker": "S02", "start": 3.0, "end": 5.0},
            {"speaker": "S01", "start": 5.0, "end": 8.0},
        ]
        per_speaker = {
            "S01": {
                "text": "Bonjour comment allez-vous Très bien merci",
                "segments": [
                    {"text": "Bonjour comment allez-vous", "start": 0.0, "end": 3.0},
                    {"text": "Très bien merci", "start": 3.0, "end": 6.0},
                ],
                "seg_table": [(0.0, 3.0, 0.0, 3.0), (5.0, 8.0, 3.0, 6.0)],
                "total_dur": 6.0,
            },
            "S02": {
                "text": "Hello nice to meet you",
                "segments": [
                    {"text": "Hello nice to meet you", "start": 0.0, "end": 2.0},
                ],
                "seg_table": [(3.0, 5.0, 0.0, 2.0)],
                "total_dur": 2.0,
            },
        }
        md = reconstruct_timeline(turns, per_speaker, "Meeting")
        assert "# Meeting" in md
        assert "Speaker 1" in md
        assert "Speaker 2" in md

    def test_no_duplication_with_single_stt_segment(self):
        """E12.150: per-speaker STT with one fake segment [0,10] must not duplicate text."""
        from lore_mcp.preprocess.diarize import reconstruct_timeline

        s01_text = "Alpha bravo charlie delta echo foxtrot golf hotel india juliet"
        s02_text = "One two three four five six seven eight nine ten"
        turns = [
            {"speaker": "S01", "start": 0.0, "end": 5.0},
            {"speaker": "S02", "start": 5.0, "end": 8.0},
            {"speaker": "S01", "start": 8.0, "end": 12.0},
            {"speaker": "S02", "start": 12.0, "end": 15.0},
            {"speaker": "S01", "start": 15.0, "end": 20.0},
        ]
        per_speaker = {
            "S01": {
                "text": s01_text,
                "segments": [{"text": s01_text, "start": 0.0, "end": 10.0}],
                "seg_table": [],
                "total_dur": 12.0,
            },
            "S02": {
                "text": s02_text,
                "segments": [{"text": s02_text, "start": 0.0, "end": 10.0}],
                "seg_table": [],
                "total_dur": 6.0,
            },
        }
        md = reconstruct_timeline(turns, per_speaker, "Test")
        assert "# Test" in md

        content_lines = [line for line in md.split("\n")
                         if line.strip() and not line.startswith("#")]
        all_text = " ".join(content_lines)
        assert all_text.count("Alpha bravo") == 1, f"Text duplicated: {all_text[:200]}"
        assert all_text.count("One two") == 1, f"Text duplicated: {all_text[:200]}"

    def test_speaker_always_in_heading(self):
        """E12.150: every heading must include a speaker identifier."""
        from lore_mcp.preprocess.diarize import reconstruct_timeline
        import re

        s01_text = "Hello world from speaker one part two"
        s02_text = "Bonjour de speaker deux"
        turns = [
            {"speaker": "S01", "start": 0.0, "end": 3.0},
            {"speaker": "S02", "start": 3.0, "end": 6.0},
            {"speaker": "S01", "start": 6.0, "end": 9.0},
        ]
        per_speaker = {
            "S01": {"text": s01_text,
                    "segments": [{"text": s01_text, "start": 0.0, "end": 10.0}],
                    "seg_table": [], "total_dur": 6.0},
            "S02": {"text": s02_text,
                    "segments": [{"text": s02_text, "start": 0.0, "end": 10.0}],
                    "seg_table": [], "total_dur": 3.0},
        }
        md = reconstruct_timeline(turns, per_speaker, "Test")
        headings = re.findall(r"^## .+", md, re.MULTILINE)
        for h in headings:
            assert "Speaker" in h, f"Heading missing speaker: {h}"

    def test_proportional_distribution(self):
        """E12.150: text distributed proportionally across turns."""
        from lore_mcp.preprocess.diarize import reconstruct_timeline

        turns = [
            {"speaker": "S01", "start": 0.0, "end": 5.0},
            {"speaker": "S01", "start": 10.0, "end": 15.0},
        ]
        per_speaker = {
            "S01": {"text": "AAAAAAAAAA" + "BBBBBBBBBB",
                    "segments": [{"text": "AAAAAAAАААБBBBBBBБББ", "start": 0.0, "end": 10.0}],
                    "seg_table": [], "total_dur": 10.0},
        }
        md = reconstruct_timeline(turns, per_speaker, "Test")
        lines = [l for l in md.split("\n") if l.strip() and not l.startswith("#")]
        assert len(lines) == 1
        text = lines[0]
        assert "A" in text
        assert "B" in text

    def test_empty_per_speaker(self):
        from lore_mcp.preprocess.diarize import reconstruct_timeline

        turns = [{"speaker": "S01", "start": 0.0, "end": 3.0}]
        md = reconstruct_timeline(turns, {}, "Empty")
        assert "# Empty" in md


class TestDiarizationDevice:
    """E12.137: diarization_device config."""

    def test_resolve_cpu(self):
        from lore_mcp.preprocess.diarize import _resolve_device
        assert _resolve_device("cpu") == "cpu"

    def test_resolve_gpu(self):
        from lore_mcp.preprocess.diarize import _resolve_device
        assert _resolve_device("gpu") == "gpu"

    def test_resolve_cuda(self):
        from lore_mcp.preprocess.diarize import _resolve_device
        assert _resolve_device("cuda") == "gpu"

    def test_config_diarization_device(self):
        from lore_mcp.config import LoreConfig
        cfg = LoreConfig.defaults()
        assert cfg.diarization_device == "auto"

    def test_config_from_yaml(self, tmp_path):
        import yaml
        from lore_mcp.config import LoreConfig

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "parse": {"diarization_device": "gpu"},
        }))
        cfg = LoreConfig.from_file(str(config_file))
        assert cfg.diarization_device == "gpu"


class TestConfigDiarizationModel:
    """Config reads diarization_model from parse section."""

    def test_config_default_empty(self):
        from lore_mcp.config import LoreConfig
        cfg = LoreConfig.defaults()
        assert cfg.diarization_model == ""

    def test_config_from_yaml(self, tmp_path):
        import yaml
        from lore_mcp.config import LoreConfig

        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "parse": {"diarization_model": "pyannote-diarize"},
        }))
        cfg = LoreConfig.from_file(str(config_file))
        assert cfg.diarization_model == "pyannote-diarize"
