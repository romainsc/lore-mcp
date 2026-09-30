#!/bin/bash
# TEI embedding server (nomic-embed-text-v2-moe)
# API: http://127.0.0.1:<port>/v1/embeddings
#      http://127.0.0.1:<port>/health
# Usage: ./start-tei.sh [port]
# Prerequisites: podman, nvidia GPU (or remove --device flag for CPU)

set -euo pipefail

PORT="${1:-8082}"
CONTAINER_NAME="tei-nomic-v2"
IMAGE="ghcr.io/huggingface/text-embeddings-inference:89-latest"
HF_CACHE="${HOME}/.cache/huggingface"

command -v podman >/dev/null || { echo "ERROR: podman not installed"; exit 1; }

podman ps -q --filter name="$CONTAINER_NAME" | grep -q . && {
    echo "Already running: $CONTAINER_NAME"
    echo "  http://127.0.0.1:${PORT}/health"
    exit 0
}

podman rm -f "$CONTAINER_NAME" 2>/dev/null || true
mkdir -p /tmp/is-logs

echo "=== TEI Embedding Server ==="
echo "Port: $PORT"
echo "Model: nomic-ai/nomic-embed-text-v2-moe"

podman run -d \
    --name "$CONTAINER_NAME" \
    --device nvidia.com/gpu=all \
    --security-opt=label=disable \
    --log-driver k8s-file \
    --log-opt path=/tmp/is-logs/${CONTAINER_NAME}.log \
    -v "${HF_CACHE}:/data" \
    -p "${PORT}:80" \
    -e HF_HUB_DISABLE_TELEMETRY=1 \
    "$IMAGE" \
    --model-id nomic-ai/nomic-embed-text-v2-moe \
    --port 80

echo "Starting (~15s)..."
echo "Logs: podman logs -f $CONTAINER_NAME"
