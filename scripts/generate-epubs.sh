#!/bin/bash
# generate-epubs.sh — Generate versioned EPUBs from project docs
# Usage: ./scripts/generate-epubs.sh [--force]
#
# Prerequisite: pandoc
# Generates EPUBs in docs/output/epub/ with version suffix.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
EPUB_CSS="$SCRIPT_DIR/epub-style.css"
OUTPUT_DIR="$PROJECT_DIR/docs/output/epub"

# Extract version from pyproject.toml
VERSION=$(grep '^version' "$PROJECT_DIR/pyproject.toml" | head -1 | sed 's/.*"\(.*\)".*/\1/')

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

CHANGED=0
SKIPPED=0
ERRORS=0
FORCE=false

[ "${1:-}" = "--force" ] && FORCE=true

generate_epub() {
    local md_file="$1"
    local output_dir="$2"
    local name
    name="$(basename "$md_file" .md)"
    local epub_file="$output_dir/lore-mcp-${name}-v${VERSION}.epub"

    if [ "$FORCE" != "true" ] && [ -f "$epub_file" ] && \
       [ "$epub_file" -nt "$md_file" ]; then
        echo -e "  ${name} (up to date)"
        SKIPPED=$((SKIPPED + 1))
        return 0
    fi

    local title
    title="$(head -1 "$md_file" | sed 's/^#\+ //')"

    if pandoc "$md_file" \
        -o "$epub_file" \
        --toc \
        --toc-depth=3 \
        -V lang=en \
        --css="$EPUB_CSS" \
        --metadata title="lore-mcp — $title" \
        --metadata author="Romain Chantereau" \
        --metadata date="$(date +%Y-%m-%d)" \
        --split-level=2 \
        2>/dev/null; then
        echo -e "  ${YELLOW}changed${NC} : lore-mcp-${name}-v${VERSION}.epub ($(du -h "$epub_file" | cut -f1))"
        CHANGED=$((CHANGED + 1))
    else
        echo -e "  ${RED}ERROR${NC}   : ${name}.epub"
        ERRORS=$((ERRORS + 1))
    fi
}

mkdir -p "$OUTPUT_DIR"

echo ""
echo "════════════════════════════════════════════════"
echo "  EPUB generation — lore-mcp v${VERSION}"
echo "  $(date +%Y-%m-%d)"
echo "════════════════════════════════════════════════"
echo ""

# --- Technical docs ---
echo -e "${BLUE}[INFO]${NC}  Technical documentation"
for doc in "$PROJECT_DIR"/docs/architecture.md \
           "$PROJECT_DIR"/docs/configuration.md \
           "$PROJECT_DIR"/docs/ai-guidelines.md \
           "$PROJECT_DIR"/docs/code-guide.md \
           "$PROJECT_DIR"/docs/tutorial.md \
           "$PROJECT_DIR"/docs/implementation-reference.md; do
    [ -f "$doc" ] && generate_epub "$doc" "$OUTPUT_DIR"
done

# --- ADRs (compiled into one) ---
echo ""
echo -e "${BLUE}[INFO]${NC}  Architecture Decision Records"
ADR_DIR="$PROJECT_DIR/docs/adr"
ADR_COMBINED="$OUTPUT_DIR/.adr-combined.md"
if [ -d "$ADR_DIR" ]; then
    cat "$ADR_DIR"/*.md > "$ADR_COMBINED"
    generate_epub "$ADR_COMBINED" "$OUTPUT_DIR"
    rm -f "$ADR_COMBINED"
    # Rename from combined temp name
    for f in "$OUTPUT_DIR"/lore-mcp-.adr-combined-*.epub; do
        [ -f "$f" ] && mv "$f" "$OUTPUT_DIR/lore-mcp-adr-v${VERSION}.epub"
    done
fi

# --- Studies ---
STUDIES_DIR="$PROJECT_DIR/docs/studies/reference"
if [ -d "$STUDIES_DIR" ]; then
    echo ""
    echo -e "${BLUE}[INFO]${NC}  Studies and research notes"
    for doc in "$STUDIES_DIR"/*.md; do
        [ -f "$doc" ] && generate_epub "$doc" "$OUTPUT_DIR"
    done
fi

echo ""
echo "════════════════════════════════════════════════"
echo -e "  ${YELLOW}changed${NC} : $CHANGED"
echo -e "  ok      : $SKIPPED"
[ $ERRORS -gt 0 ] && echo -e "  ${RED}errors${NC}  : $ERRORS"
echo "  total   : $((CHANGED + SKIPPED + ERRORS))"
echo "  output  : $OUTPUT_DIR"
echo "════════════════════════════════════════════════"
