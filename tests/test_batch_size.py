"""Tests for E10.17: configurable batch size."""

import os
from unittest.mock import patch

import pytest


class TestBatchSizeConfig:
    def test_default_batch_size(self):
        from lore_mcp.ingest import get_batch_size
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LORE_BATCH_SIZE", None)
            assert get_batch_size() == 64

    def test_env_override(self):
        from lore_mcp.ingest import get_batch_size
        with patch.dict(os.environ, {"LORE_BATCH_SIZE": "32"}):
            assert get_batch_size() == 32

    def test_env_override_small(self):
        from lore_mcp.ingest import get_batch_size
        with patch.dict(os.environ, {"LORE_BATCH_SIZE": "1"}):
            assert get_batch_size() == 1
