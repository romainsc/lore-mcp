#!/bin/bash
# Lance le serveur granite-docling-258M (GPU)
# API: http://127.0.0.1:<port>/v1/chat/completions
#      http://127.0.0.1:<port>/health
#      http://127.0.0.1:<port>/v1/models
# Usage: ./start-docling-server.sh [--cpu] [--empty-cache] [port]
#   ou:  DOCLING_PORT=9000 ./start-docling-server.sh
# --cpu         : CPU only (documents denses OK, plus lent)
# --empty-cache : vider le cache CUDA entre chaque requete

set -euo pipefail

CPU_MODE=""
EMPTY_CACHE=""
PORT=""
for arg in "$@"; do
    case "$arg" in
        --cpu) CPU_MODE="1" ;;
        --empty-cache) EMPTY_CACHE="1" ;;
        *) [ -z "$PORT" ] && PORT="$arg" ;;
    esac
done
PORT="${PORT:-${DOCLING_PORT:-8091}}"
CONTAINER_NAME="docling-server"
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

GPU_FLAGS="--device nvidia.com/gpu=all"
MODE_LABEL="GPU"
if [ -n "$CPU_MODE" ]; then
    GPU_FLAGS=""
    MODE_LABEL="CPU"
fi

if [ -z "$CPU_MODE" ] && command -v nvidia-smi >/dev/null; then
    VRAM_FREE=$(nvidia-smi --query-gpu=memory.free \
        --format=csv,noheader,nounits 2>/dev/null \
        | head -1)
    if [ -n "$VRAM_FREE" ] && [ "$VRAM_FREE" -lt 2000 ]; then
        echo "WARNING: VRAM libre ${VRAM_FREE} MiB < 2000 MiB"
    fi
fi

echo "=== granite-docling-258M Server ($MODE_LABEL) ==="
echo "Port: $PORT"
echo "API: http://127.0.0.1:${PORT}/v1/chat/completions"
echo "Arrêter: podman stop $CONTAINER_NAME"

mkdir -p /tmp/is-logs
    podman run -d \
    --name "$CONTAINER_NAME" \
    $GPU_FLAGS \
    --security-opt=label=disable \
    -v "${HF_CACHE}:/root/.cache/huggingface" \
    -v "${SCRIPT_DIR}:/scripts:ro" \
    -p "${PORT}:8080" \
    -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    ${EMPTY_CACHE:+-e EMPTY_CACHE=1} \
    --log-driver k8s-file --log-opt path=/tmp/is-logs/start-docling-server.log --shm-size=2g \
    "$IMAGE" \
    bash -c '
pip install -q "transformers==4.57.1" \
    accelerate einops pillow sentencepiece \
    protobuf torchvision fastapi uvicorn \
    python-multipart docling-core 2>&1 | tail -1
python3 /scripts/docling-server.py
'

echo "Démarrage en cours..."
echo "Suivre: podman logs -f $CONTAINER_NAME"
