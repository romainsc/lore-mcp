"""Tests for checkpoint with per-phase hash. See E12.67, E2.04."""

import json
import os
import time
import pytest

from lore_mcp.checkpoint import (
    Checkpoint, phase_hash, list_states, purge_state_by_hash, purge_states,
)
from lore_mcp.config import LoreConfig


_manifest_counter = 0

def _manifest(tmp_path, content=None):
    global _manifest_counter
    _manifest_counter += 1
    if content is None:
        content = f"collection: test-{_manifest_counter}\nsources: []\n"
    m = tmp_path / "manifest.yaml"
    m.write_text(content)
    return str(m)


# ── Phase hash variations (E12.67) ────────────────────────────


class TestPhaseHash:
    """E12.67: phase_hash varies by phase-relevant config."""

    def test_different_frame_strategy_different_hash(self, tmp_path):
        m = _manifest(tmp_path)
        cfg1 = LoreConfig(video_frame_strategy="scene")
        cfg2 = LoreConfig(video_frame_strategy="ocr")
        assert phase_hash(m, cfg1, "phase1") != phase_hash(m, cfg2, "phase1")

    def test_same_config_same_hash(self, tmp_path):
        m = _manifest(tmp_path)
        cfg1 = LoreConfig(video_frame_strategy="ocr", ocr_engine="tesseract")
        cfg2 = LoreConfig(video_frame_strategy="ocr", ocr_engine="tesseract")
        assert phase_hash(m, cfg1, "phase1") == phase_hash(m, cfg2, "phase1")

    def test_enrich_change_does_not_affect_phase1(self, tmp_path):
        m = _manifest(tmp_path)
        cfg1 = LoreConfig(enrich_techniques=["context"])
        cfg2 = LoreConfig(enrich_techniques=["context", "qa"])
        assert phase_hash(m, cfg1, "phase1") == phase_hash(m, cfg2, "phase1")

    def test_different_ocr_engine_different_phase1(self, tmp_path):
        m = _manifest(tmp_path)
        cfg1 = LoreConfig(ocr_engine="tesseract")
        cfg2 = LoreConfig(ocr_engine="rapidocr")
        assert phase_hash(m, cfg1, "phase1") != phase_hash(m, cfg2, "phase1")

    def test_different_frame_interval_different_phase1(self, tmp_path):
        m = _manifest(tmp_path)
        cfg1 = LoreConfig(video_frame_interval=30)
        cfg2 = LoreConfig(video_frame_interval=10)
        assert phase_hash(m, cfg1, "phase1") != phase_hash(m, cfg2, "phase1")

    def test_different_caption_primary_different_phase2(self, tmp_path):
        m = _manifest(tmp_path)
        cfg1 = LoreConfig(caption_primary="granite-vision")
        cfg2 = LoreConfig(caption_primary="molmo-7b")
        assert phase_hash(m, cfg1, "phase2") != phase_hash(m, cfg2, "phase2")

    def test_caption_change_does_not_affect_phase1(self, tmp_path):
        m = _manifest(tmp_path)
        cfg1 = LoreConfig(caption_primary="granite-vision")
        cfg2 = LoreConfig(caption_primary="molmo-7b")
        assert phase_hash(m, cfg1, "phase1") == phase_hash(m, cfg2, "phase1")

    def test_different_enrich_different_phase3(self, tmp_path):
        m = _manifest(tmp_path)
        cfg1 = LoreConfig(enrich_techniques=["context"])
        cfg2 = LoreConfig(enrich_techniques=["context", "qa"])
        assert phase_hash(m, cfg1, "phase3") != phase_hash(m, cfg2, "phase3")

    def test_enrich_change_does_not_affect_phase2(self, tmp_path):
        m = _manifest(tmp_path)
        cfg1 = LoreConfig(enrich_techniques=["context"])
        cfg2 = LoreConfig(enrich_techniques=["context", "qa"])
        assert phase_hash(m, cfg1, "phase2") == phase_hash(m, cfg2, "phase2")

    def test_different_stt_model_different_stt_hash(self, tmp_path):
        m = _manifest(tmp_path)
        cfg1 = LoreConfig(stt_model="canary")
        cfg2 = LoreConfig(stt_model="whisper")
        assert phase_hash(m, cfg1, "stt") != phase_hash(m, cfg2, "stt")

    def test_deterministic(self, tmp_path):
        m = _manifest(tmp_path)
        cfg = LoreConfig(ocr_engine="tesseract", video_frame_strategy="ocr")
        h1 = phase_hash(m, cfg, "phase1")
        h2 = phase_hash(m, cfg, "phase1")
        assert h1 == h2

    def test_no_config_returns_manifest_hash(self, tmp_path):
        m = _manifest(tmp_path)
        h = phase_hash(m, None, "phase1")
        assert len(h) == 16


# ── Phase hash checkpoint integration ─────────────────────────


class TestPhaseHashCheckpoint:
    """E12.67: checkpoint invalidation when phase hash changes."""

    def test_phase_done_with_matching_hash(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_phase_done("phase1", hash_value="abc123")
        assert cp.is_phase_done("phase1", expected_hash="abc123")

    def test_phase_not_done_with_different_hash(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_phase_done("phase1", hash_value="abc123")
        assert not cp.is_phase_done("phase1", expected_hash="def456")

    def test_phase_done_without_hash_backward_compat(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_phase_done("phase1")
        assert cp.is_phase_done("phase1")
        assert cp.is_phase_done("phase1", expected_hash="")


# ── Force mode ─────────────────────────────────────────────────


class TestForceMode:
    """Force mode bypasses all checkpoint state."""

    def test_force_ignores_phase_done(self, tmp_path):
        m = _manifest(tmp_path)
        cp = Checkpoint(m, force=False)
        cp.mark_phase_done("phase1", hash_value="h1")
        cp.mark_completed("stt", "video.mp4")
        cp.mark_image("phase2", "doc.pdf", 0, "captioned")

        cp_force = Checkpoint(m, force=True)
        assert not cp_force.is_phase_done("phase1")
        assert not cp_force.is_phase_done("phase1", expected_hash="h1")
        assert not cp_force.is_completed("stt", "video.mp4")
        assert cp_force.get_image_status("phase2", "doc.pdf", 0) == "pending"

    def test_force_starts_with_empty_data(self, tmp_path):
        m = _manifest(tmp_path)
        cp = Checkpoint(m, force=False)
        cp.mark_phase_done("phase1")
        cp.mark_phase_done("stt")
        cp.mark_phase_done("phase3")

        cp_force = Checkpoint(m, force=True)
        assert cp_force.summary()["phases"] == {}


# ── Resume from each phase ─────────────────────────────────────


class TestResume:
    """Checkpoint correctly identifies which phases to skip."""

    def test_phase1_done_skips_phase1_only(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_phase_done("phase1", hash_value="h1")

        assert cp.is_phase_done("phase1", expected_hash="h1")
        assert not cp.is_phase_done("stt")
        assert not cp.is_phase_done("phase2")
        assert not cp.is_phase_done("phase3")

    def test_phase1_and_stt_done(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_phase_done("phase1", hash_value="h1")
        cp.mark_completed("stt", "video1.mp4")
        cp.mark_completed("stt", "video2.mp4")

        assert cp.is_phase_done("phase1", expected_hash="h1")
        assert cp.is_completed("stt", "video1.mp4")
        assert cp.is_completed("stt", "video2.mp4")
        assert not cp.is_completed("stt", "video3.mp4")

    def test_all_phases_done_skips_everything(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        for phase in ["phase1", "stt", "frame_caption", "phase2", "phase3"]:
            cp.mark_phase_done(phase)

        for phase in ["phase1", "stt", "frame_caption", "phase2", "phase3"]:
            assert cp.is_phase_done(phase)


# ── Cascade invalidation ──────────────────────────────────────


class TestCascadeInvalidation:
    """invalidate_phase removes a phase from checkpoint data."""

    def test_invalidate_removes_phase(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_phase_done("stt")
        cp.mark_completed("stt", "video.mp4")
        assert cp.is_phase_done("stt")

        cp.invalidate_phase("stt")
        assert not cp.is_phase_done("stt")
        assert not cp.is_completed("stt", "video.mp4")

    def test_invalidate_nonexistent_is_noop(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_phase_done("phase1")
        cp.invalidate_phase("nonexistent")
        assert cp.is_phase_done("phase1")

    def test_invalidate_preserves_other_phases(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_phase_done("phase1", hash_value="h1")
        cp.mark_phase_done("stt")
        cp.mark_phase_done("frame_caption")

        cp.invalidate_phase("stt")
        cp.invalidate_phase("frame_caption")

        assert cp.is_phase_done("phase1", expected_hash="h1")
        assert not cp.is_phase_done("stt")
        assert not cp.is_phase_done("frame_caption")

    def test_invalidate_persists_to_disk(self, tmp_path):
        m = _manifest(tmp_path)
        cp = Checkpoint(m, force=False)
        cp.mark_phase_done("stt")
        cp.invalidate_phase("stt")

        cp2 = Checkpoint(m, force=False)
        assert not cp2.is_phase_done("stt")


# ── Per-source completion ──────────────────────────────────────


class TestPerSourceCompletion:
    """mark_completed and is_completed track individual sources."""

    def test_mark_and_check(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_completed("stt", "a.mp4")
        assert cp.is_completed("stt", "a.mp4")
        assert not cp.is_completed("stt", "b.mp4")

    def test_multiple_sources(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_completed("phase3", "doc1.md")
        cp.mark_completed("phase3", "doc2.md")
        assert cp.is_completed("phase3", "doc1.md")
        assert cp.is_completed("phase3", "doc2.md")
        assert not cp.is_completed("phase3", "doc3.md")

    def test_no_duplicate_on_remark(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_completed("stt", "a.mp4")
        cp.mark_completed("stt", "a.mp4")
        data = json.loads(cp._file.read_text())
        assert data["phases"]["stt"]["completed"].count("a.mp4") == 1

    def test_persists_to_disk(self, tmp_path):
        m = _manifest(tmp_path)
        cp = Checkpoint(m, force=False)
        cp.mark_completed("stt", "video.mp4")

        cp2 = Checkpoint(m, force=False)
        assert cp2.is_completed("stt", "video.mp4")

    def test_force_ignores_completed(self, tmp_path):
        m = _manifest(tmp_path)
        cp = Checkpoint(m, force=False)
        cp.mark_completed("stt", "video.mp4")

        cp_force = Checkpoint(m, force=True)
        assert not cp_force.is_completed("stt", "video.mp4")


# ── Per-image checkpoint (E12.64) ──────────────────────────────


class TestPerImageCheckpoint:
    """E12.64: per-image status within a source."""

    def test_default_status_pending(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        assert cp.get_image_status("phase2", "doc.pdf", 0) == "pending"

    def test_mark_and_get_status(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_image("phase2", "doc.pdf", 0, "captioned")
        cp.mark_image("phase2", "doc.pdf", 1, "skipped", reason="<10KB")
        cp.mark_image("phase2", "doc.pdf", 2, "error", reason="timeout")

        assert cp.get_image_status("phase2", "doc.pdf", 0) == "captioned"
        assert cp.get_image_status("phase2", "doc.pdf", 1) == "skipped"
        assert cp.get_image_status("phase2", "doc.pdf", 2) == "error"
        assert cp.get_image_status("phase2", "doc.pdf", 3) == "pending"

    def test_force_returns_pending(self, tmp_path):
        m = _manifest(tmp_path)
        cp = Checkpoint(m, force=False)
        cp.mark_image("phase2", "doc.pdf", 0, "captioned")

        cp_force = Checkpoint(m, force=True)
        assert cp_force.get_image_status("phase2", "doc.pdf", 0) == "pending"

    def test_persists_to_disk(self, tmp_path):
        m = _manifest(tmp_path)
        cp = Checkpoint(m, force=False)
        cp.mark_image("phase2", "doc.pdf", 5, "captioned")

        cp2 = Checkpoint(m, force=False)
        assert cp2.get_image_status("phase2", "doc.pdf", 5) == "captioned"

    def test_different_sources_independent(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_image("phase2", "a.pdf", 0, "captioned")
        cp.mark_image("phase2", "b.pdf", 0, "error")

        assert cp.get_image_status("phase2", "a.pdf", 0) == "captioned"
        assert cp.get_image_status("phase2", "b.pdf", 0) == "error"


# ── Summary ────────────────────────────────────────────────────


class TestSummary:
    """Checkpoint.summary() returns useful metadata."""

    def test_empty_checkpoint(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        s = cp.summary()
        assert s["phases"] == {}

    def test_summary_counts(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_phase_done("phase1")
        cp.mark_completed("stt", "a.mp4")
        cp.mark_completed("stt", "b.mp4")

        s = cp.summary()
        assert s["phases"]["phase1"]["status"] == "done"
        assert s["phases"]["stt"]["completed"] == 2


# ── State management ───────────────────────────────────────────


class TestStateManagement:
    """list_states, purge_state_by_hash, purge_states."""

    def test_list_states(self, tmp_path):
        m = _manifest(tmp_path)
        cp = Checkpoint(m, force=False)
        cp.mark_phase_done("phase1")

        states = list_states()
        hashes = [s["hash"] for s in states]
        assert cp._hash in hashes

    def test_purge_by_hash(self, tmp_path):
        m = _manifest(tmp_path)
        cp = Checkpoint(m, force=False)
        cp.mark_phase_done("phase1")
        h = cp._hash
        state_path = cp.state_dir

        assert state_path.exists()
        assert purge_state_by_hash(h)
        assert not state_path.exists()

    def test_purge_nonexistent_returns_false(self, tmp_path):
        assert not purge_state_by_hash("nonexistent_hash_prefix")

    def test_purge_all(self, tmp_path):
        m1 = _manifest(tmp_path)
        m2 = tmp_path / "m2.yaml"
        m2.write_text(f"collection: purge-b-{_manifest_counter+100}\nsources: []\n")
        cp1 = Checkpoint(str(m1), force=False)
        cp1.mark_phase_done("phase1")
        cp2 = Checkpoint(str(m2), force=False)
        cp2.mark_phase_done("phase1")

        removed = purge_states(purge_all=True)
        assert removed >= 2
        assert len(list_states()) == 0

    def test_cleanup_removes_state_dir(self, tmp_path):
        cp = Checkpoint(_manifest(tmp_path), force=False)
        cp.mark_phase_done("phase1")
        state_path = cp.state_dir
        assert state_path.exists()

        cp.cleanup()
        assert not state_path.exists()
