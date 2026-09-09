"""Deduplication for preprocessing pipeline. See docs/studies/grooming-E12.01.md.

Two levels:
1. Exact: SHA-256 hash (skip identical files)
2. Near-duplicate: MinHash+LSH via datasketch

Parameters follow academic defaults from "Mining of Massive Datasets"
(Leskovec, Rajaraman, Ullman): k=5 word shingles, 128 permutations,
threshold=0.8 Jaccard for near-duplicate detection.
"""

import hashlib
from dataclasses import dataclass, field

SHINGLE_K = 5
NUM_PERM = 128
DEFAULT_NEAR_THRESHOLD = 0.8


@dataclass
class DedupReport:
    """Result of deduplication analysis."""

    duplicates: list[dict] = field(default_factory=list)
    unique_count: int = 0

    @property
    def to_skip(self) -> list[str]:
        """Files to skip (all but first in each duplicate group)."""
        skip = []
        for group in self.duplicates:
            skip.extend(group["files"][1:])
        return skip

    def format(self) -> str:
        """Format report as human-readable text."""
        lines = []
        if not self.duplicates:
            lines.append(f"{self.unique_count} files, 0 duplicates")
        else:
            total_dupes = sum(len(g["files"]) - 1 for g in self.duplicates)
            lines.append(
                f"{self.unique_count} unique, "
                f"{total_dupes} duplicates in "
                f"{len(self.duplicates)} groups"
            )
            for group in self.duplicates:
                label = group.get("hash", "")[:12]
                lines.append(
                    f"  {label}: "
                    f"{', '.join(group['files'])}"
                )
        return "\n".join(lines)


def find_exact_duplicates(files: dict[str, str]) -> DedupReport:
    """Find exact duplicates by SHA-256 hash."""
    hash_to_files: dict[str, list[str]] = {}

    for name, content in files.items():
        h = hashlib.sha256(content.encode("utf-8")).hexdigest()
        hash_to_files.setdefault(h, []).append(name)

    duplicates = []
    for h, names in hash_to_files.items():
        if len(names) > 1:
            duplicates.append({"files": names, "hash": h})

    unique_count = len(hash_to_files)
    return DedupReport(duplicates=duplicates, unique_count=unique_count)


def _word_shingles(text: str, k: int = SHINGLE_K) -> set[str]:
    """Generate k-word shingles from text."""
    words = text.lower().split()
    if len(words) < k:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def find_near_duplicates(
    files: dict[str, str],
    threshold: float = DEFAULT_NEAR_THRESHOLD,
    num_perm: int = NUM_PERM,
    shingle_k: int = SHINGLE_K,
) -> DedupReport:
    """Find near-duplicate content using MinHash+LSH (datasketch).

    Parameters from "Mining of Massive Datasets":
    - shingle_k=5: word-level 5-grams
    - num_perm=128: MinHash permutations
    - threshold=0.8: Jaccard similarity for near-duplicate
    """
    try:
        from datasketch import MinHash, MinHashLSH
    except ImportError:
        return DedupReport(duplicates=[], unique_count=len(files))

    if not files:
        return DedupReport(duplicates=[], unique_count=0)

    lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
    minhashes: dict[str, MinHash] = {}

    for name, content in files.items():
        m = MinHash(num_perm=num_perm)
        for shingle in _word_shingles(content, k=shingle_k):
            m.update(shingle.encode("utf-8"))
        minhashes[name] = m
        try:
            lsh.insert(name, m)
        except ValueError:
            pass

    seen = set()
    duplicates = []

    for name, m in minhashes.items():
        if name in seen:
            continue
        candidates = lsh.query(m)
        group = [c for c in candidates if c not in seen]
        if len(group) > 1:
            duplicates.append({"files": group, "hash": "near-dup"})
            seen.update(group)

    unique_count = len(files) - sum(len(g["files"]) - 1 for g in duplicates)
    return DedupReport(duplicates=duplicates, unique_count=unique_count)
