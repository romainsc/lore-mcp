"""Shared test fixtures. See docs/architecture.md for design context."""

import sqlite3

import pytest
import sqlite_vec
from sqlite_vec import serialize_float32


DIMS = 8


def make_embedding(seed: float, dims: int = DIMS) -> list[float]:
    """Return a deterministic fake embedding for testing."""
    return [seed * (i + 1) % 1.0 for i in range(dims)]


@pytest.fixture
def db():
    """In-memory SQLite database with sqlite-vec loaded."""
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    yield conn
    conn.close()
