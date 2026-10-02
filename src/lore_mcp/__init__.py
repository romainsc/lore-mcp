"""lore-mcp — Local Offline Retrieval Engine for MCP.

See docs/architecture.md for system design and docs/configuration.md
for environment variables.
"""

try:
    from lore_mcp._version import __version__
except ImportError:
    __version__ = "0.0.0.dev0+unknown"
