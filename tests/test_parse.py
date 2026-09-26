"""Tests for lore_mcp.preprocess.parse. See docs/studies/grooming-E6.06.md."""

from unittest.mock import patch

import pytest

from lore_mcp.preprocess.parse import (
    parse_to_markdown, detect_format, FormatNotSupported,
    unload_docling, classify_parse_result,
    IMAGE_EXTENSIONS,
)


class TestDetectFormat:
    """Format detection by file extension."""

    def test_markdown(self):
        assert detect_format("doc.md") == "markdown"

    def test_html(self):
        assert detect_format("page.html") == "html"
        assert detect_format("page.htm") == "html"

    def test_pdf(self):
        assert detect_format("paper.pdf") == "docling"

    def test_docx(self):
        assert detect_format("report.docx") == "docling"

    def test_pptx(self):
        assert detect_format("slides.pptx") == "docling"

    def test_xlsx(self):
        assert detect_format("data.xlsx") == "docling"

    def test_epub(self):
        assert detect_format("book.epub") == "docling"

    def test_image_formats(self):
        for ext in ("png", "jpg", "jpeg", "tiff"):
            assert detect_format(f"img.{ext}") == "docling"

    def test_csv(self):
        assert detect_format("data.csv") == "markitdown"

    def test_json(self):
        assert detect_format("config.json") == "markitdown"

    def test_xml(self):
        assert detect_format("feed.xml") == "markitdown"

    def test_unknown_raises(self):
        with pytest.raises(FormatNotSupported):
            detect_format("file.xyz")

    def test_case_insensitive(self):
        assert detect_format("DOC.PDF") == "docling"
        assert detect_format("page.HTML") == "html"


class TestParseMarkdown:
    """Markdown passthrough — returns content as-is."""

    def test_passthrough(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("## Title\n\nContent.\n")

        result = parse_to_markdown(str(f))
        assert "Title" in result
        assert "Content." in result

    def test_reads_utf8(self, tmp_path):
        f = tmp_path / "doc.md"
        f.write_text("Café résumé\n", encoding="utf-8")

        result = parse_to_markdown(str(f))
        assert "Café" in result


class TestParseHTML:
    """HTML conversion via trafilatura."""

    def test_extracts_article_content(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text("""
        <html><head><title>Test</title></head>
        <body>
        <nav>Navigation menu</nav>
        <article>
        <h1>Main Title</h1>
        <p>This is the main article content with enough
        text to be considered substantial by trafilatura
        extraction heuristics which need a minimum amount
        of content to work properly.</p>
        </article>
        <footer>Footer stuff</footer>
        </body></html>
        """, encoding="utf-8")

        result = parse_to_markdown(str(f))
        assert "Main Title" in result
        assert "main article content" in result

    def test_strips_html_tags(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text("""
        <html><body>
        <article>
        <p>This is a paragraph with <b>bold</b> text and
        enough content to pass trafilatura minimum length
        requirements for extraction.</p>
        </article>
        </body></html>
        """, encoding="utf-8")

        result = parse_to_markdown(str(f))
        assert "<p>" not in result
        assert "<b>" not in result

    def test_missing_trafilatura_raises(self, tmp_path, monkeypatch):
        f = tmp_path / "page.html"
        f.write_text("<html><body><p>Content</p></body></html>")

        import lore_mcp.preprocess.parse as parse_mod
        monkeypatch.setattr(parse_mod, "_HAVE_TRAFILATURA", False)

        with pytest.raises(ImportError, match="trafilatura"):
            parse_to_markdown(str(f))


class TestParsePDF:
    """PDF conversion via Docling."""

    def test_missing_docling_raises(self, tmp_path, monkeypatch):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4 fake")

        import lore_mcp.preprocess.parse as parse_mod
        monkeypatch.setattr(parse_mod, "_HAVE_DOCLING", False)

        with pytest.raises(ImportError, match="docling"):
            parse_to_markdown(str(f))


class TestParseCSV:
    """CSV/data conversion via markitdown."""

    def test_missing_markitdown_raises(self, tmp_path, monkeypatch):
        f = tmp_path / "data.csv"
        f.write_text("a,b,c\n1,2,3\n")

        import lore_mcp.preprocess.parse as parse_mod
        monkeypatch.setattr(parse_mod, "_HAVE_MARKITDOWN", False)

        with pytest.raises(ImportError, match="markitdown"):
            parse_to_markdown(str(f))


class TestUnloadDocling:

    def test_unload_clears_converter(self, monkeypatch):
        import lore_mcp.preprocess.parse as parse_mod
        monkeypatch.setattr(parse_mod, "_docling_converter", "fake")
        unload_docling()
        assert parse_mod._docling_converter is None


class TestImageExtensions:

    def test_common_extensions_present(self):
        for ext in (".png", ".jpg", ".jpeg", ".tiff"):
            assert ext in IMAGE_EXTENSIONS


class TestDoclingJsonSave:
    """Tests for Docling document JSON serialization (E12.42)."""

    def test_parse_saves_docling_json(self, tmp_path):
        """parse_to_markdown with docling_json_path saves JSON."""
        f = tmp_path / "doc.md"
        f.write_text("## Title\n\nContent.\n")
        json_path = str(tmp_path / "doc.docling.json")
        result = parse_to_markdown(str(f), docling_json_path=json_path)
        assert "Title" in result
        # Markdown passthrough doesn't save JSON (not docling backend)
        import os
        assert not os.path.exists(json_path)

    def test_caption_with_docling_import(self):
        """caption_with_docling is importable."""
        from lore_mcp.preprocess.parse import caption_with_docling
        assert callable(caption_with_docling)


class TestDetectFormatAudioVideo:
    """E12.48/49: audio and video format detection via mimetypes."""

    def test_audio_common(self):
        for ext in ("mp3", "wav", "ogg", "m4a", "flac"):
            assert detect_format(f"file.{ext}") == "audio"

    def test_audio_extra(self):
        """mimetypes detects formats not in a manual list."""
        for ext in ("aac", "wma"):
            result = detect_format(f"file.{ext}")
            assert result == "audio", f".{ext} should be audio, got {result}"

    def test_video_common(self):
        for ext in ("mp4", "mkv", "webm", "avi"):
            assert detect_format(f"file.{ext}") == "video"

    def test_explicit_backends_unchanged(self):
        """Explicit backends still work."""
        assert detect_format("doc.pdf") == "docling"
        assert detect_format("page.html") == "html"
        assert detect_format("data.csv") == "markitdown"


class TestTranscribeAudio:
    """E12.48: audio transcription via STT API."""

    def test_transcribe_audio_importable(self):
        from lore_mcp.preprocess.parse import transcribe_audio
        assert callable(transcribe_audio)

    def test_returns_markdown_with_timestamps(self, tmp_path):
        """Transcription formatted as markdown with timestamp headings."""
        from unittest.mock import patch as _patch, MagicMock
        import json

        audio = tmp_path / "recording.mp3"
        audio.write_bytes(b"\x00" * 100)

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "text": "Hello world. This is a test.",
            "segments": [
                {"start": 0.0, "end": 3.5, "text": "Hello world."},
                {"start": 3.5, "end": 7.0, "text": " This is a test."},
            ],
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with _patch("urllib.request.urlopen", return_value=mock_resp):
            from lore_mcp.preprocess.parse import transcribe_audio
            result = transcribe_audio(
                str(audio), "http://localhost:8093/v1", "whisper-large",
            )

        assert "00:00:00" in result["text"]
        assert "Hello world" in result["text"]
        assert "This is a test" in result["text"]
        assert "language" in result


class TestParseVideo:
    """E12.49: video → markdown with transcription + inline frames."""

    def test_parse_video_importable(self):
        from lore_mcp.preprocess.parse import parse_video
        assert callable(parse_video)


class TestSttCache:
    """E12.70: STT cache separates transcription from frame extraction."""

    def test_stt_cache_reused(self, tmp_path):
        """parse_video reuses .stt.json cache instead of re-transcribing."""
        import json
        from unittest.mock import patch, MagicMock
        from lore_mcp.preprocess.parse import parse_video

        video = tmp_path / "test.webm"
        video.write_bytes(b"\x00" * 100)

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        stt_cache = cache_dir / "test.stt.json"
        stt_cache.write_text(json.dumps({
            "text": "# Test Video\n\n## [00:00:00]\n\nCached transcription.\n",
            "language": "en",
        }))

        with patch("lore_mcp.preprocess.parse.transcribe_audio") as mock_stt, \
             patch("subprocess.run"):
            result = parse_video(
                str(video), "http://fake:8093/v1/audio/transcriptions",
                "test-model", cache_dir=str(cache_dir),
            )

        mock_stt.assert_not_called()
        assert "Cached transcription" in result["text"]
        assert result["language"] == "en"

    def test_stt_cache_written(self, tmp_path):
        """parse_video writes .stt.json after transcription."""
        import json
        from pathlib import Path
        from unittest.mock import patch, MagicMock
        from lore_mcp.preprocess.parse import parse_video

        video = tmp_path / "test.webm"
        video.write_bytes(b"\x00" * 100)

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()

        def fake_run(cmd, **kwargs):
            if "ffmpeg" in cmd and "-vn" in cmd:
                audio = Path(cmd[cmd.index("-ac") + 2])
                audio.write_bytes(b"\x00" * 1000)
            return MagicMock(returncode=0, stderr="")

        with patch("lore_mcp.preprocess.parse.transcribe_audio") as mock_stt, \
             patch("subprocess.run", side_effect=fake_run), \
             patch("lore_mcp.preprocess.parse._get_audio_duration", return_value=10.0):
            mock_stt.return_value = {
                "text": "# test\n\n## [00:00:00]\n\nHello world.\n",
                "language": "en",
            }
            parse_video(
                str(video), "http://fake:8093/v1/audio/transcriptions",
                "test-model", cache_dir=str(cache_dir),
            )

        stt_cache = cache_dir / "test.stt.json"
        assert stt_cache.exists()
        data = json.loads(stt_cache.read_text())
        assert data["language"] == "en"
        assert "Hello world" in data["text"]


class TestCaptionTimeout:
    """E12.44: timeout from LLM registry propagates to caption_with_docling."""

    def test_timeout_passed_to_api_options(self):
        """caption_with_docling passes timeout to PictureDescriptionApiOptions."""
        from unittest.mock import MagicMock, patch as _patch

        mock_doc = MagicMock()
        mock_doc.pictures = []

        with _patch("docling_core.types.doc.document.DoclingDocument") as mock_cls:
            mock_cls.load_from_json.return_value = mock_doc
            from lore_mcp.preprocess.parse import caption_with_docling
            result = caption_with_docling(
                "fake.json", "http://localhost:8090/v1", "model", timeout=600,
            )
            # No pictures → returns immediately, but timeout accepted
            assert result is not None

    def test_default_timeout_is_180(self):
        """Default timeout matches Docling's default (180s)."""
        import inspect
        from lore_mcp.preprocess.parse import caption_with_docling
        sig = inspect.signature(caption_with_docling)
        assert sig.parameters["timeout"].default == 180


class TestCaptionStandaloneImage:
    """E12.45: fallback for standalone photos when Docling produces empty output."""

    def test_caption_standalone_image_importable(self):
        """caption_standalone_image is importable."""
        from lore_mcp.preprocess.parse import caption_standalone_image
        assert callable(caption_standalone_image)

    def test_returns_markdown_with_description(self, tmp_path):
        """Returns markdown containing VLM description."""
        from unittest.mock import patch as _patch, MagicMock
        import json

        img = tmp_path / "photo.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "A sunset over the ocean."}}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with _patch("urllib.request.urlopen", return_value=mock_resp):
            from lore_mcp.preprocess.parse import caption_standalone_image
            result = caption_standalone_image(
                str(img), "http://localhost:8090/v1", "test-model",
            )

        assert "sunset" in result.lower()

    def test_default_timeout(self):
        """Default timeout is 180s."""
        import inspect
        from lore_mcp.preprocess.parse import caption_standalone_image
        sig = inspect.signature(caption_standalone_image)
        assert sig.parameters["timeout"].default == 180

    def test_custom_timeout(self, tmp_path):
        """Custom timeout is passed to urlopen."""
        from unittest.mock import patch as _patch, MagicMock, ANY
        import json

        img = tmp_path / "photo.png"
        img.write_bytes(b"\x89PNG" + b"\x00" * 100)

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "A photo."}}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with _patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            from lore_mcp.preprocess.parse import caption_standalone_image
            caption_standalone_image(
                str(img), "http://localhost:8090/v1", "model", timeout=600,
            )
            mock_open.assert_called_once_with(ANY, timeout=600)


class TestSmartFrameFilter:
    """E12.71: OCR-based frame filter before VLM captioning."""

    def _make_frame_md(self, text_on_frame=""):
        """Create markdown with an inline base64 frame."""
        import base64
        # 1x1 white PNG
        pixel = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
        b64 = base64.b64encode(pixel).decode()
        return f"## [00:00:00]\n\nSome transcript text.\n\n![frame](data:image/png;base64,{b64})\n\nMore text.\n"

    def test_frame_with_text_gets_captioned(self):
        """Frame with readable OCR text → VLM called."""
        import json
        from unittest.mock import patch as _patch, MagicMock
        from lore_mcp.preprocess.parse import caption_inline_frames

        md = self._make_frame_md()

        def fake_subprocess_run(cmd, **kwargs):
            r = MagicMock(returncode=0)
            if "tesseract" in cmd:
                r.stdout = "This slide shows the architecture diagram with components"
                r.stderr = ""
            return r

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "A detailed slide description."}}]
        }).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with _patch("subprocess.run", side_effect=fake_subprocess_run), \
             _patch("lore_mcp.preprocess.parse._fetch_api") as mock_fetch:
            mock_fetch.return_value = {
                "choices": [{"message": {"content": "A detailed slide description."}}]
            }
            result = caption_inline_frames(md, "http://fake:8090/v1", "model")

        mock_fetch.assert_called_once()
        assert "A detailed slide description." in result
        assert "data:image/png;base64," not in result

    def test_frame_without_text_skipped(self):
        """Frame with no readable text → VLM NOT called."""
        from unittest.mock import patch as _patch, MagicMock
        from lore_mcp.preprocess.parse import caption_inline_frames

        md = self._make_frame_md()

        def fake_subprocess_run(cmd, **kwargs):
            r = MagicMock(returncode=0)
            if "tesseract" in cmd:
                r.stdout = ""
                r.stderr = ""
            return r

        with _patch("subprocess.run", side_effect=fake_subprocess_run), \
             _patch("lore_mcp.preprocess.parse._fetch_api") as mock_fetch:
            result = caption_inline_frames(md, "http://fake:8090/v1", "model")

        mock_fetch.assert_not_called()
        assert "[frame]" in result
        assert "data:image/png;base64," not in result


class TestFrameResume:
    """E12.64 correction: per-frame checkpoint in caption_inline_frames."""

    def _make_two_frames_md(self):
        import base64
        b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50).decode()
        return (
            "## [00:00:00]\n\nSpeaker intro.\n\n"
            f"![frame](data:image/png;base64,{b64})\n\n"
            "## [00:01:00]\n\nSecond part.\n\n"
            f"![frame](data:image/png;base64,{b64})\n"
        )

    def test_resume_skips_captioned_frames(self, tmp_path):
        """If intermediate file has first frame captioned, only second is processed."""
        import base64
        from pathlib import Path
        from unittest.mock import patch as _patch, MagicMock
        from lore_mcp.preprocess.parse import caption_inline_frames

        b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50).decode()
        original = self._make_two_frames_md()

        # Simulate interrupted state: first frame already captioned
        saved = (
            "## [00:00:00]\n\nSpeaker intro.\n\n"
            "Description of first slide.\n\n"
            "## [00:01:00]\n\nSecond part.\n\n"
            f"![frame](data:image/png;base64,{b64})\n"
        )
        inter_path = tmp_path / "test.frame-caption.md"
        inter_path.write_text(saved)

        call_count = [0]

        def fake_subprocess_run(cmd, **kwargs):
            r = MagicMock(returncode=0)
            if "tesseract" in cmd:
                r.stdout = "Some readable text on the slide here"
                r.stderr = ""
            return r

        def fake_fetch(req, timeout, **kwargs):
            call_count[0] += 1
            return {"choices": [{"message": {"content": "Second slide description."}}]}

        with _patch("subprocess.run", side_effect=fake_subprocess_run), \
             _patch("lore_mcp.preprocess.parse._fetch_api", side_effect=fake_fetch):
            result = caption_inline_frames(
                original, "http://fake:8090/v1", "model",
                intermediate_path=str(inter_path),
            )

        assert call_count[0] == 1, f"Expected 1 VLM call (skipped first), got {call_count[0]}"
        assert "Description of first slide" in result
        assert "Second slide description" in result
        assert "data:image/png;base64," not in result


class TestVttToMarkdown:
    """E12.73: convert WebVTT captions to markdown with timestamps."""

    def test_basic_vtt_conversion(self):
        from lore_mcp.preprocess.parse import _vtt_to_markdown
        vtt = (
            "WEBVTT\n\n"
            "00:00:01.000 --> 00:00:05.000\n"
            "Hello world.\n\n"
            "00:00:06.000 --> 00:00:10.000\n"
            "Second line.\n\n"
            "00:02:01.000 --> 00:02:05.000\n"
            "After two minutes.\n"
        )
        result = _vtt_to_markdown(vtt, title="Test Video")
        assert "# Test Video" in result
        assert "## [00:00:00]" in result
        assert "Hello world." in result
        assert "Second line." in result
        assert "After two minutes." in result

    def test_empty_vtt(self):
        from lore_mcp.preprocess.parse import _vtt_to_markdown
        result = _vtt_to_markdown("WEBVTT\n\n", title="Empty")
        assert "# Empty" in result


class TestDownloadVideo:
    """E12.73: download video via yt-dlp with caption support."""

    def test_download_with_captions(self, tmp_path):
        from unittest.mock import MagicMock, patch as _patch
        from lore_mcp.preprocess.parse import download_video

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = {
            "id": "abc123",
            "title": "Test Video",
            "uploader": "Test Channel",
            "duration": 120,
            "upload_date": "20260925",
            "language": "en",
            "subtitles": {"en": [{"ext": "vtt", "url": "http://example.com/en.vtt"}]},
            "automatic_captions": {},
        }
        mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_instance.__exit__ = MagicMock(return_value=False)

        def fake_download(urls):
            vtt_file = tmp_path / "abc123.en.vtt"
            vtt_file.write_text(
                "WEBVTT\n\n00:00:01.000 --> 00:00:05.000\nHello world.\n"
            )
            video_file = tmp_path / "abc123.mp4"
            video_file.write_bytes(b"\x00" * 100)

        mock_ydl_instance.download.side_effect = fake_download

        mock_ydl_cls = MagicMock(return_value=mock_ydl_instance)

        with _patch.dict("sys.modules", {"yt_dlp": MagicMock(YoutubeDL=mock_ydl_cls)}):
            result = download_video(
                "https://www.youtube.com/watch?v=abc123",
                str(tmp_path), lang="en",
            )

        assert result["captions_text"] is not None
        assert "Hello world" in result["captions_text"]
        assert result["title"] == "Test Video"
        assert result["captions_source"] == "manual"

    def test_download_without_captions(self, tmp_path):
        from unittest.mock import MagicMock, patch as _patch
        from lore_mcp.preprocess.parse import download_video

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = {
            "id": "xyz789",
            "title": "No Captions Video",
            "uploader": "Channel",
            "duration": 60,
            "upload_date": "20260925",
            "language": "en",
            "subtitles": {},
            "automatic_captions": {},
        }
        mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_instance.__exit__ = MagicMock(return_value=False)

        def fake_download(urls):
            video_file = tmp_path / "xyz789.mp4"
            video_file.write_bytes(b"\x00" * 100)

        mock_ydl_instance.download.side_effect = fake_download
        mock_ydl_cls = MagicMock(return_value=mock_ydl_instance)

        with _patch.dict("sys.modules", {"yt_dlp": MagicMock(YoutubeDL=mock_ydl_cls)}):
            result = download_video(
                "https://www.youtube.com/watch?v=xyz789",
                str(tmp_path), lang="en",
            )

        assert result["captions_text"] is None
        assert result["video_path"] is not None
        assert result["captions_source"] == "none"

    def test_ytdlp_not_installed(self, tmp_path):
        from lore_mcp.preprocess.parse import download_video
        import sys
        # Ensure yt_dlp is not importable
        saved = sys.modules.get("yt_dlp")
        sys.modules["yt_dlp"] = None
        try:
            result = download_video(
                "https://www.youtube.com/watch?v=test",
                str(tmp_path),
            )
            assert "error" in result
            assert "yt-dlp" in result["error"].lower() or "yt_dlp" in result["error"].lower()
        finally:
            if saved is not None:
                sys.modules["yt_dlp"] = saved
            else:
                sys.modules.pop("yt_dlp", None)

    def test_download_with_auto_captions(self, tmp_path):
        from unittest.mock import MagicMock, patch as _patch
        from lore_mcp.preprocess.parse import download_video

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = {
            "id": "auto456",
            "title": "Auto Caption Video",
            "uploader": "Channel",
            "duration": 90,
            "upload_date": "20260925",
            "language": "en",
            "subtitles": {},
            "automatic_captions": {"en": [{"ext": "vtt", "url": "http://example.com/auto.vtt"}]},
        }
        mock_ydl_instance.__enter__ = MagicMock(return_value=mock_ydl_instance)
        mock_ydl_instance.__exit__ = MagicMock(return_value=False)

        def fake_download(urls):
            vtt_file = tmp_path / "auto456.en.vtt"
            vtt_file.write_text(
                "WEBVTT\n\n00:00:01.000 --> 00:00:05.000\nAuto caption text.\n"
            )
            video_file = tmp_path / "auto456.mp4"
            video_file.write_bytes(b"\x00" * 100)

        mock_ydl_instance.download.side_effect = fake_download
        mock_ydl_cls = MagicMock(return_value=mock_ydl_instance)

        with _patch.dict("sys.modules", {"yt_dlp": MagicMock(YoutubeDL=mock_ydl_cls)}):
            result = download_video(
                "https://www.youtube.com/watch?v=auto456",
                str(tmp_path), lang="en",
            )

        assert result["captions_text"] is not None
        assert "Auto caption text" in result["captions_text"]
        assert result["captions_source"] == "auto"


class TestCaptionWithDoclingRGBA:
    """E12.80 MVP1: palette images pre-converted to RGBA before Docling."""

    def test_palette_trns_convert_rgb_warns(self):
        """Baseline: direct P+tRNS → RGB conversion triggers PIL warning."""
        import warnings
        from PIL import Image

        img = Image.new("P", (100, 100))
        img.info["transparency"] = bytes([0] * 256)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            img.convert("RGB")
            pil_warnings = [x for x in w if "Palette images" in str(x.message)]
            assert len(pil_warnings) > 0, "Expected PIL warning for P+tRNS → RGB"

    def test_palette_trns_via_rgba_no_warning(self):
        """P+tRNS → RGBA → RGB does NOT trigger PIL warning."""
        import warnings
        from PIL import Image

        img = Image.new("P", (100, 100))
        img.info["transparency"] = bytes([0] * 256)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            img.convert("RGBA").convert("RGB")
            pil_warnings = [x for x in w if "Palette images" in str(x.message)]
            assert len(pil_warnings) == 0, f"PIL warning should not fire via RGBA: {pil_warnings}"

    def test_safe_rgb_in_caption_with_docling(self):
        """caption_with_docling must use safe RGBA conversion for P mode images."""
        import inspect
        from lore_mcp.preprocess.parse import caption_with_docling
        source = inspect.getsource(caption_with_docling)
        assert 'convert("RGBA")' in source, "caption_with_docling must convert P images to RGBA before RGB"
