"""Table protection for preprocessing pipeline. See E12.06.

Wraps markdown tables in sentinel markers so the chunker
does not split them across chunk boundaries.
"""

import re

TABLE_SENTINEL_START = "<!-- LORE_TABLE_START -->"
TABLE_SENTINEL_END = "<!-- LORE_TABLE_END -->"

_TABLE_ROW_RE = re.compile(r"^\|.*\|$")
_TABLE_SEP_RE = re.compile(r"^\|[\s:-]+\|$")


def protect_tables(text: str) -> str:
    """Wrap markdown tables in sentinel markers."""
    lines = text.split("\n")
    result = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        is_table_line = bool(_TABLE_ROW_RE.match(stripped) or _TABLE_SEP_RE.match(stripped))

        if is_table_line and not in_table:
            in_table = True
            result.append(TABLE_SENTINEL_START)
            result.append(line)
        elif is_table_line and in_table:
            result.append(line)
        elif not is_table_line and in_table:
            in_table = False
            result.append(TABLE_SENTINEL_END)
            result.append(line)
        else:
            result.append(line)

    if in_table:
        result.append(TABLE_SENTINEL_END)

    return "\n".join(result)
