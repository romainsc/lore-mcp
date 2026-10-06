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

        result = diarize_audio("/fake/audio.mp3", "fake-model")
        assert result == []


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
