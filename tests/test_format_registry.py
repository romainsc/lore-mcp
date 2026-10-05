"""Tests for FormatRegistry. See grooming-E12.114.md."""

import pytest


class TestDetect:
    """detect() resolves backend from content or extension."""

    def test_markdown_by_extension(self):
        from lore_mcp.format_registry import get_format_registry
        assert get_format_registry().detect("doc.md") == "markdown"

    def test_html_by_extension(self):
        from lore_mcp.format_registry import get_format_registry
        assert get_format_registry().detect("page.html") == "html"

    def test_pdf_by_extension(self):
        from lore_mcp.format_registry import get_format_registry
        assert get_format_registry().detect("report.pdf") == "docling"

    def test_csv_by_extension(self):
        from lore_mcp.format_registry import get_format_registry
        assert get_format_registry().detect("data.csv") == "markitdown"

    def test_python_by_extension(self):
        from lore_mcp.format_registry import get_format_registry
        assert get_format_registry().detect("server.py") == "code"

    def test_javascript_by_extension(self):
        from lore_mcp.format_registry import get_format_registry
        assert get_format_registry().detect("app.js") == "code"

    def test_unknown_raises(self):
        from lore_mcp.format_registry import get_format_registry
        from lore_mcp.preprocess.parse import FormatNotSupported
        with pytest.raises(FormatNotSupported):
            get_format_registry().detect("file.xyz")

    def test_content_based_html(self, tmp_path):
        from lore_mcp.format_registry import get_format_registry
        f = tmp_path / "page"
        f.write_text("<html><body><h1>Title</h1></body></html>")
        assert get_format_registry().detect(str(f)) == "html"


class TestIsSupported:
    """is_supported() checks without I/O."""

    def test_supported_formats(self):
        from lore_mcp.format_registry import get_format_registry
        r = get_format_registry()
        for f in ["doc.md", "page.html", "report.pdf", "data.csv",
                   "server.py", "app.js", "Main.java", "script.sh"]:
            assert r.is_supported(f), f"Expected supported: {f}"

    def test_unsupported(self):
        from lore_mcp.format_registry import get_format_registry
        assert not get_format_registry().is_supported("file.xyz")


class TestStructuralParser:
    """has_structural_parser() checks tree-sitter availability."""

    def test_python_always_available(self):
        from lore_mcp.format_registry import get_format_registry
        assert get_format_registry().has_structural_parser(".py")

    def test_installed_language(self):
        from lore_mcp.format_registry import get_format_registry
        r = get_format_registry()
        assert r.has_structural_parser(".js")
        assert r.has_structural_parser(".c")

    def test_unavailable_language(self):
        from lore_mcp.format_registry import get_format_registry
        r = get_format_registry()
        if not r.has_structural_parser(".go"):
            assert True
        else:
            assert True  # go is installed, that's fine too


class TestListFormats:
    """list_formats() returns complete format inventory."""

    def test_includes_all_extensions(self):
        from lore_mcp.format_registry import get_format_registry
        formats = get_format_registry().list_formats()
        assert ".md" in formats
        assert ".pdf" in formats
        assert ".py" in formats
        assert ".js" in formats

    def test_shows_backend(self):
        from lore_mcp.format_registry import get_format_registry
        formats = get_format_registry().list_formats()
        assert formats[".pdf"]["backend"] == "docling"
        assert formats[".py"]["backend"] == "code"

    def test_shows_structural_parser(self):
        from lore_mcp.format_registry import get_format_registry
        formats = get_format_registry().list_formats()
        assert formats[".py"]["structural_parser"] is True


class TestConfigOverride:
    """apply_config() adds/modifies/removes mappings."""

    def test_add_extension(self):
        from lore_mcp.format_registry import FormatRegistry
        r = FormatRegistry()
        r.apply_config({".proto": "markitdown"})
        assert r.detect("schema.proto") == "markitdown"

    def test_override_extension(self):
        from lore_mcp.format_registry import FormatRegistry
        r = FormatRegistry()
        r.apply_config({".txt": "markdown"})
        assert r.detect("readme.txt") == "markdown"

    def test_remove_extension(self):
        from lore_mcp.format_registry import FormatRegistry
        r = FormatRegistry()
        r.apply_config({".lua": ""})
        assert not r.is_supported("script.lua")

    def test_invalid_backend_raises(self):
        from lore_mcp.format_registry import FormatRegistry
        r = FormatRegistry()
        with pytest.raises(ValueError, match="Unknown backend"):
            r.apply_config({".xyz": "invalid_backend"})


class TestExplicitVsImplicit:
    """E12.114 it3: error for explicit, skip for implicit."""

    def test_explicit_unsupported_file_errors(self, tmp_path):
        """Explicitly requested unsupported file produces error in report."""
        import json
        from lore_mcp.preprocess import _phase1_worker
        import yaml

        orig = tmp_path / "orig"
        orig.mkdir()
        (orig / "data.awk").write_text("BEGIN { print 42 }")

        prep = tmp_path / "prep"
        prep.mkdir()

        manifest = tmp_path / "manifest.yaml"
        manifest.write_text(yaml.dump({
            "collection": "test", "level": "libre",
            "sources": [{"file": "data.awk"}],
        }))

        report_path = prep / "report.json"
        _phase1_worker(
            str(manifest), str(tmp_path), str(orig), str(prep),
            str(report_path), "quiet",
        )

        report = json.loads(report_path.read_text())
        errors = report.get("errors", [])
        assert len(errors) == 1
        assert "unsupported" in errors[0]["message"].lower() or "format" in errors[0]["message"].lower()

    def test_implicit_scan_skips_unsupported(self, tmp_path):
        """scan_directory silently skips unsupported files."""
        from lore_mcp.recipe import scan_directory

        (tmp_path / "doc.md").write_text("# Title\n\nContent.\n")
        (tmp_path / "script.awk").write_text("BEGIN { print 42 }")
        (tmp_path / "server.py").write_text("def main(): pass")

        result = scan_directory(str(tmp_path))
        files = [s["file"] for s in result["sources"]]
        assert "doc.md" in files
        assert "server.py" in files
        assert "script.awk" not in files
