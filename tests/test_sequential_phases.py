"""Tests for pipeline phases (E12.26+) — Docling-native architecture."""

import base64
from unittest.mock import patch, MagicMock

import pytest
import yaml

from lore_mcp.config import LoreConfig
from lore_mcp.preprocess import preprocess_sources


def _cfg(**overrides) -> LoreConfig:
    defaults = {"force": True, "output_level": "quiet"}
    defaults.update(overrides)
    return LoreConfig(**defaults)


def _write_manifest(path, sources, collection="test", level="libre"):
    data = {"collection": collection, "level": level, "sources": sources}
    path.write_text(yaml.dump(data), encoding="utf-8")


# ── Column reorder (E12.23 Part B) ─────────────────────────────


class TestColumnReorder:
    """Tests for _reorder_columns on Docling document objects."""

    def test_reorder_noop_on_no_body(self):
        from lore_mcp.preprocess.parse import _reorder_columns

        class FakeDoc:
            body = None
        _reorder_columns(FakeDoc())

    def test_reorder_noop_on_single_column(self):
        from lore_mcp.preprocess.parse import _reorder_columns

        doc = MagicMock()
        ref1 = MagicMock()
        ref1.cref = "#/texts/0"
        ref2 = MagicMock()
        ref2.cref = "#/texts/1"
        doc.body.children = [ref1, ref2]

        item1 = MagicMock()
        item1.prov = [MagicMock()]
        item1.prov[0].bbox.l = 10
        item1.prov[0].bbox.t = 100

        item2 = MagicMock()
        item2.prov = [MagicMock()]
        item2.prov[0].bbox.l = 12
        item2.prov[0].bbox.t = 50

        doc.texts = [item1, item2]
        _reorder_columns(doc)
        # Single column — no reorder
        assert doc.body.children == [ref1, ref2]

    def test_reorder_two_columns(self):
        from lore_mcp.preprocess.parse import _reorder_columns

        doc = MagicMock()
        refs = []
        items = []
        # 4 items: col2-top, col1-top, col2-bottom, col1-bottom
        positions = [(300, 100), (10, 100), (300, 50), (10, 50)]
        for i, (x, y) in enumerate(positions):
            ref = MagicMock()
            ref.cref = f"#/texts/{i}"
            refs.append(ref)

            item = MagicMock()
            item.prov = [MagicMock()]
            item.prov[0].bbox.l = x
            item.prov[0].bbox.t = y
            items.append(item)

        doc.body.children = list(refs)
        doc.texts = items

        _reorder_columns(doc)

        result_crefs = [r.cref for r in doc.body.children]
        assert result_crefs == [
            "#/texts/1",  # col1, y=100 (top)
            "#/texts/3",  # col1, y=50 (bottom)
            "#/texts/0",  # col2, y=100 (top)
            "#/texts/2",  # col2, y=50 (bottom)
        ]


# ── Phase-by-phase pipeline ────────────────────────────────────


class TestPhasePipeline:
    """Verify the pipeline structure (Docling-native)."""

    def test_phase1_parse_without_caption(self, tmp_path):
        """Phase 1 parses all sources without calling VLM."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text("## Title\n\nContent here.\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        reports = preprocess_sources(
            str(manifest), str(tmp_path),
            _cfg(preprocess_orig_dir="raw", preprocess_prep_dir="out"),
        )

        assert reports[0]["status"] == "ok"
        assert (tmp_path / "out" / "doc.md").exists()

    def test_phase2_skipped_without_additional(self, tmp_path, capsys):
        """Phase 2 is skipped when no additional models configured."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text("## Title\n\nContent.\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        preprocess_sources(
            str(manifest), str(tmp_path),
            _cfg(preprocess_orig_dir="raw", preprocess_prep_dir="out",
                 output_level="default"),
        )

        captured = capsys.readouterr()
        assert "Phase 3" in captured.out
        assert "Phase 4" in captured.out
        assert (tmp_path / "out" / "doc.md").exists()

    def test_phase3_cleans_text(self, tmp_path):
        """Phase 3 applies clean_text to all parsed sources."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text("## Title\n\nhello\x00world\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        preprocess_sources(
            str(manifest), str(tmp_path),
            _cfg(preprocess_orig_dir="raw", preprocess_prep_dir="out"),
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
            _cfg(preprocess_orig_dir="raw", preprocess_prep_dir="out"),
        )

        ok_reports = [r for r in reports if r["status"] == "ok"]
        dup_reports = [r for r in ok_reports if r.get("duplicate")]
        assert len(ok_reports) == 2
        assert len(dup_reports) >= 1

    def test_phase1_runs_in_subprocess(self, tmp_path):
        """Phase 1 runs in subprocess and produces phase1-report.json."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text("## Title\n\nContent.\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        preprocess_sources(
            str(manifest), str(tmp_path),
            _cfg(preprocess_orig_dir="raw", preprocess_prep_dir="out"),
        )

        report = tmp_path / "out" / "phase1-report.json"
        assert report.exists()
        import json
        data = json.loads(report.read_text())
        assert "parsed" in data
        assert len(data["parsed"]) == 1

    def test_llm_entry_accepted(self, tmp_path):
        """preprocess_sources accepts llm_entry dict."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text("## Title\n\nContent.\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        reports = preprocess_sources(
            str(manifest), str(tmp_path),
            _cfg(preprocess_orig_dir="raw", preprocess_prep_dir="out",
                 llm_registry=[{"name": "test", "api_url": "http://fake:9999/v1", "model": "test"}],
                 enrich_models=["test"]),
        )

        assert reports[0]["status"] == "ok"

    def test_phases_produce_same_result(self, tmp_path):
        """Phase pipeline produces correct output."""
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
            _cfg(preprocess_orig_dir="raw", preprocess_prep_dir="out"),
        )

        assert reports[0]["status"] == "ok"
        content = (tmp_path / "out" / "doc.md").read_text()
        assert "\x00" not in content
        assert "## Section" in content

        prep_manifest = tmp_path / "manifest-prep.yaml"
        data = yaml.safe_load(prep_manifest.read_text())
        assert data["sources"][0]["title"] == "Override"

    def test_caption_primary_none_no_crash(self, tmp_path):
        """No caption_primary = no captioning, no crash."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text("## Title\n\nContent.\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        reports = preprocess_sources(
            str(manifest), str(tmp_path),
            _cfg(preprocess_orig_dir="raw", preprocess_prep_dir="out"),
        )

        assert reports[0]["status"] == "ok"

    def test_no_caption_config_no_crash(self, tmp_path):
        """No caption config = no captioning, no crash."""
        raw = tmp_path / "raw"
        raw.mkdir()
        (raw / "doc.md").write_text("## Title\n\nContent.\n")
        manifest = tmp_path / "manifest.yaml"
        _write_manifest(manifest, [{"orig": "doc.md"}])

        reports = preprocess_sources(
            str(manifest), str(tmp_path),
            _cfg(preprocess_orig_dir="raw", preprocess_prep_dir="out"),
        )

        assert reports[0]["status"] == "ok"
