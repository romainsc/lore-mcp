"""Tests for E12.26 — sequential model processing (phase-by-phase pipeline)."""

import base64
from unittest.mock import patch, MagicMock

import pytest
import yaml

from lore_mcp.preprocess import preprocess_sources
from lore_mcp.preprocess.parse import (
    caption_inline_images,
    _vlm_api_call,
    _INLINE_IMAGE_RE,
)


def _write_manifest(path, sources, collection="test", level="libre"):
    data = {"collection": collection, "level": level, "sources": sources}
    path.write_text(yaml.dump(data), encoding="utf-8")


# ── caption_inline_images ──────────────────────────────────────


class TestCaptionInlineImages:
    """Unit tests for caption_inline_images."""

    def test_no_vlm_returns_unchanged(self):
        text = "![](data:image/png;base64,iVBOR)"
        assert caption_inline_images(text, "", "", "") == text

    def test_preserves_existing_alt_text(self):
        text = "![existing alt](data:image/png;base64,iVBOR)"
        result = caption_inline_images(
            text, "http://fake:9999/v1", "model", ""
        )
        assert result == text

    @patch("lore_mcp.preprocess.parse._vlm_api_call")
    def test_replaces_empty_alt_with_caption(self, mock_vlm):
        mock_vlm.side_effect = ["photo", "A sunset over mountains"]
        b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()
        text = f"![](data:image/png;base64,{b64})"

        result = caption_inline_images(
            text, "http://fake:9999/v1", "model", ""
        )

        assert "A sunset over mountains" in result
        assert mock_vlm.call_count == 2

    @patch("lore_mcp.preprocess.parse._vlm_api_call")
    def test_classify_selects_specialized_prompt(self, mock_vlm):
        mock_vlm.side_effect = ["chart", "X axis: time, Y axis: revenue"]
        b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()
        text = f"![](data:image/png;base64,{b64})"

        caption_inline_images(text, "http://fake:9999/v1", "model", "")

        caption_call_prompt = mock_vlm.call_args_list[1][0][2]
        assert "axes labels" in caption_call_prompt.lower() or "chart" in caption_call_prompt.lower()

    @patch("lore_mcp.preprocess.parse._vlm_api_call")
    def test_passes_context_and_description(self, mock_vlm):
        mock_vlm.side_effect = ["photo", "A bird"]
        b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()
        text = f"![](data:image/png;base64,{b64})"

        caption_inline_images(
            text, "http://fake:9999/v1", "model", "",
            context="Wildlife guide", description="Chapter on birds",
        )

        caption_call_prompt = mock_vlm.call_args_list[1][0][2]
        assert "Wildlife guide" in caption_call_prompt
        assert "Chapter on birds" in caption_call_prompt

    @patch("lore_mcp.preprocess.parse._vlm_api_call")
    def test_multiple_images_all_captioned(self, mock_vlm):
        mock_vlm.side_effect = [
            "photo", "First image",
            "diagram", "Second image",
        ]
        b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()
        text = (
            f"Before ![](data:image/png;base64,{b64}) "
            f"middle ![](data:image/jpeg;base64,{b64}) after"
        )

        result = caption_inline_images(
            text, "http://fake:9999/v1", "model", ""
        )

        assert "First image" in result
        assert "Second image" in result
        assert mock_vlm.call_count == 4

    def test_no_images_returns_unchanged(self):
        text = "Just plain markdown with **bold** text."
        result = caption_inline_images(
            text, "http://fake:9999/v1", "model", ""
        )
        assert result == text

    @patch("lore_mcp.preprocess.parse._vlm_api_call")
    def test_brackets_in_caption_escaped(self, mock_vlm):
        mock_vlm.side_effect = ["photo", "A [bracketed] caption"]
        b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()
        text = f"![](data:image/png;base64,{b64})"

        result = caption_inline_images(
            text, "http://fake:9999/v1", "model", ""
        )

        assert "[bracketed]" not in result
        assert "(bracketed)" in result


class TestInlineImageRegex:
    """Verify the regex matches expected patterns."""

    def test_matches_png_base64(self):
        text = "![alt](data:image/png;base64,iVBOR)"
        assert _INLINE_IMAGE_RE.search(text) is not None

    def test_matches_jpeg_base64(self):
        text = "![](data:image/jpeg;base64,/9j/4AAQ)"
        assert _INLINE_IMAGE_RE.search(text) is not None

    def test_no_match_regular_image(self):
        text = "![alt](image.png)"
        assert _INLINE_IMAGE_RE.search(text) is None

    def test_no_match_http_url(self):
        text = "![alt](https://example.com/image.png)"
        assert _INLINE_IMAGE_RE.search(text) is None


# ── Phase-by-phase pipeline ────────────────────────────────────


class TestPhasePipeline:
    """Verify the 4-phase pipeline structure."""

    def test_phase1_parse_without_vlm(self, tmp_path):
        """Phase 1 parses all sources without calling VLM."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text("## Title\n\nContent here.\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        reports = preprocess_sources(
            str(manifest), str(tmp_path),
            orig_dir="raw", prep_dir="out", force=True,
            output_level="quiet",
        )

        assert reports[0]["status"] == "ok"
        assert (tmp_path / "out" / "doc.md").exists()

    def test_phase2_skipped_without_vlm(self, tmp_path, capsys):
        """Phase 2 is skipped when no VLM is configured."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text("## Title\n\nContent.\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        preprocess_sources(
            str(manifest), str(tmp_path),
            orig_dir="raw", prep_dir="out", force=True,
        )

        captured = capsys.readouterr()
        assert "Phase 1" in captured.out
        assert "Phase 3" in captured.out
        assert "Phase 4" in captured.out

    def test_phase3_cleans_text(self, tmp_path):
        """Phase 3 applies clean_text to all parsed sources."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text("## Title\n\nhello\x00world\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        preprocess_sources(
            str(manifest), str(tmp_path),
            orig_dir="raw", prep_dir="out", force=True,
            output_level="quiet",
        )

        content = (tmp_path / "out" / "doc.md").read_text()
        assert "\x00" not in content
        assert "helloworld" in content

    def test_phase4_dedup_and_write(self, tmp_path):
        """Phase 4 performs dedup analysis and writes files."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "a.md").write_text("## Same\n\nIdentical content here.\n")
        (raw / "b.md").write_text("## Same\n\nIdentical content here.\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "a.md"}, {"orig": "b.md"}])

        reports = preprocess_sources(
            str(manifest), str(tmp_path),
            orig_dir="raw", prep_dir="out", force=True,
            output_level="quiet",
        )

        ok_reports = [r for r in reports if r["status"] == "ok"]
        dup_reports = [r for r in ok_reports if r.get("duplicate")]
        assert len(ok_reports) == 2
        assert len(dup_reports) >= 1

    def test_service_lifecycle_called_for_vlm(self, tmp_path):
        """Phase 2 calls start_service/stop_service when VLM entry has commands."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text(
            "## Title\n\n![](data:image/png;base64,iVBOR)\n"
        )
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        vlm_entry = {
            "api_url": "http://127.0.0.1:19999/v1",
            "model": "test-vlm",
            "start": "echo starting",
            "stop": "echo stopping",
        }

        with patch("lore_mcp.preprocess.start_service") as mock_start, \
             patch("lore_mcp.preprocess.stop_service") as mock_stop, \
             patch("lore_mcp.preprocess.caption_inline_images", return_value="captioned"):
            preprocess_sources(
                str(manifest), str(tmp_path),
                orig_dir="raw", prep_dir="out", force=True,
                vlm_entry=vlm_entry,
                output_level="quiet",
            )

            mock_start.assert_called_once_with(vlm_entry)
            mock_stop.assert_called_once_with(vlm_entry)

    def test_service_stop_called_on_error(self, tmp_path):
        """stop_service is called even when VLM captioning fails."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text(
            "## Title\n\n![](data:image/png;base64,iVBOR)\n"
        )
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        vlm_entry = {
            "api_url": "http://127.0.0.1:19999/v1",
            "model": "test-vlm",
            "start": "echo starting",
            "stop": "echo stopping",
        }

        with patch("lore_mcp.preprocess.start_service") as mock_start, \
             patch("lore_mcp.preprocess.stop_service") as mock_stop, \
             patch("lore_mcp.preprocess.caption_inline_images",
                   side_effect=Exception("VLM error")):
            with pytest.raises(Exception, match="VLM error"):
                preprocess_sources(
                    str(manifest), str(tmp_path),
                    orig_dir="raw", prep_dir="out", force=True,
                    vlm_entry=vlm_entry,
                    output_level="quiet",
                )

            mock_stop.assert_called_once_with(vlm_entry)

    def test_docling_unloaded_after_phase1(self, tmp_path):
        """unload_docling is called between phase 1 and phase 2."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text("## Title\n\nContent.\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        with patch("lore_mcp.preprocess.unload_docling") as mock_unload:
            preprocess_sources(
                str(manifest), str(tmp_path),
                orig_dir="raw", prep_dir="out", force=True,
                output_level="quiet",
            )

            mock_unload.assert_called_once()

    def test_new_signature_llm_entry(self, tmp_path):
        """preprocess_sources accepts llm_entry dict instead of separate params."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text("## Title\n\nContent.\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        reports = preprocess_sources(
            str(manifest), str(tmp_path),
            orig_dir="raw", prep_dir="out", force=True,
            llm_entry={"api_url": "http://fake:9999/v1", "model": "test"},
            output_level="quiet",
        )

        assert reports[0]["status"] == "ok"

    def test_phases_produce_same_result(self, tmp_path):
        """Phase-by-phase produces the same output as before."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text(
            "---\ntitle: My Doc\nauthor: RC\n---\n\n"
            "## Section\n\nSome content with\x00 nul chars.\n"
        )
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [
            {"orig": "doc.md", "title": "Override"},
        ])

        reports = preprocess_sources(
            str(manifest), str(tmp_path),
            orig_dir="raw", prep_dir="out", force=True,
            output_level="quiet",
        )

        assert reports[0]["status"] == "ok"
        content = (tmp_path / "out" / "doc.md").read_text()
        assert "\x00" not in content
        assert "## Section" in content

        prep_manifest = tmp_path / "manifest-prep.yaml"
        data = yaml.safe_load(prep_manifest.read_text())
        assert data["sources"][0]["title"] == "Override"
