FROM python:3.13-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng \
    ffmpeg build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

RUN pip install --no-cache-dir .[parse,eval]

FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng \
    ffmpeg && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin/lore-mcp /usr/local/bin/lore-mcp

WORKDIR /app

ENTRYPOINT ["lore-mcp"]
CMD ["serve"]
