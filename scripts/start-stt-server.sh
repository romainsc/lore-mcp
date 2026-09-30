#!/bin/bash
# Lance le serveur STT Canary-1B-v2
# API: http://127.0.0.1:<port>/v1/audio/transcriptions
#      http://127.0.0.1:<port>/health
#      http://127.0.0.1:<port>/v1/models
# Usage: ./start-stt-server.sh [--cpu] [--no-timestamps] [--no-pnc] [port]
#   ou:  STT_PORT=9000 ./start-stt-server.sh
# --cpu           : CPU only (plus lent)
# --no-timestamps : desactiver les timestamps segments/mots
# --no-pnc        : desactiver ponctuation et capitalisation

set -euo pipefail

CPU_MODE=""
NO_TS=""
NO_PNC=""
PORT=""
for arg in "$@"; do
    case "$arg" in
        --cpu) CPU_MODE="1" ;;
        --no-timestamps) NO_TS="1" ;;
        --no-pnc) NO_PNC="1" ;;
        *) [ -z "$PORT" ] && PORT="$arg" ;;
    esac
done
PORT="${PORT:-${STT_PORT:-8093}}"
CONTAINER_NAME="stt-server"
IMAGE="nvcr.io/nvidia/nemo-speech:26.07"
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

if [ -z "$CPU_MODE" ] \
    && command -v nvidia-smi >/dev/null; then
    VRAM_FREE=$(nvidia-smi \
        --query-gpu=memory.free \
        --format=csv,noheader,nounits 2>/dev/null \
        | head -1)
    if [ -n "$VRAM_FREE" ] \
        && [ "$VRAM_FREE" -lt 2500 ]; then
        echo "WARNING: VRAM libre ${VRAM_FREE}" \
             "MiB < 2500 MiB"
    fi
fi

echo "=== STT Canary-1B-v2 Server ($MODE_LABEL) ==="
echo "Port: $PORT"
echo "API: http://127.0.0.1:${PORT}/v1/audio/transcriptions"
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
    ${NO_TS:+-e STT_TIMESTAMPS=0} \
    ${NO_PNC:+-e STT_PNC=0} \
    --log-driver k8s-file --log-opt path=/tmp/is-logs/start-stt-server.log --shm-size=2g \
    "$IMAGE" \
    bash -c '
apt-get update -qq && apt-get install -yqq \
    ffmpeg >/dev/null 2>&1
pip install -q fastapi uvicorn \
    python-multipart 2>&1 | tail -1
python3 /scripts/stt-server.py
'

echo "Démarrage en cours (~30s modèle)..."
echo "Suivre: podman logs -f $CONTAINER_NAME"
