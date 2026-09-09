"""Deduplication for preprocessing pipeline. See docs/studies/grooming-E12.01.md."""

import hashlib
from dataclasses import dataclass, field


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
                lines.append(
                    f"  {group['hash'][:12]}: "
                    f"{', '.join(group['files'])}"
                )
        return "\n".join(lines)


def find_exact_duplicates(files: dict[str, str]) -> DedupReport:
    """Find exact duplicates by SHA-256 hash.

    Args:
        files: mapping of filename → content

    Returns:
        DedupReport with duplicate groups and unique count.
    """
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
