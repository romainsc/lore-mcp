#!/bin/bash
# Lance le serveur de captioning Molmo2-O 7B
# API: http://127.0.0.1:<port>/v1/chat/completions
#      http://127.0.0.1:<port>/health
#      http://127.0.0.1:<port>/v1/models
# Usage: ./start-molmo2-server.sh [port]
#   ou:  MOLMO_PORT=9000 ./start-molmo2-server.sh

set -euo pipefail

PORT="${1:-${MOLMO_PORT:-8090}}"
CONTAINER_NAME="molmo2-server"
IMAGE="nvcr.io/nvidia/pytorch:26.03-py3"
HF_CACHE="${HOME}/.cache/huggingface"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if podman ps --filter name="$CONTAINER_NAME" \
    --format "{{.Names}}" 2>/dev/null \
    | grep -q "$CONTAINER_NAME"; then
    echo "Déjà en cours: $CONTAINER_NAME"
    echo "  http://127.0.0.1:${PORT}/health"
    echo "Arrêter: podman stop $CONTAINER_NAME"
    exit 0
fi

podman rm "$CONTAINER_NAME" 2>/dev/null || true

echo "=== Molmo2-O 7B Captioning Server ==="
echo "Port: $PORT"
echo "API: http://127.0.0.1:${PORT}/caption"
echo "Arrêter: podman stop $CONTAINER_NAME"

mkdir -p /tmp/is-logs
    podman run -d \
    --name "$CONTAINER_NAME" \
    --security-opt=label=disable \
    -v "${HF_CACHE}:/root/.cache/huggingface" \
    -v "${SCRIPT_DIR}:/scripts:ro" \
    -p "${PORT}:8080" \
    --log-driver k8s-file --log-opt path=/tmp/is-logs/start-molmo2-server.log --shm-size=4g \
    "$IMAGE" \
    bash -c '
pip install -q "transformers==4.57.1" \
    accelerate einops pillow sentencepiece \
    protobuf torchvision fastapi uvicorn \
    python-multipart 2>&1 | tail -1
python3 /scripts/molmo2-server.py
'

echo "Démarrage en cours (~30s install + ~5s chargement modèle)..."
echo "Suivre: podman logs -f $CONTAINER_NAME"
