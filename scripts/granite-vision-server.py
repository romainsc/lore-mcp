"""Serveur Granite Vision 4.1 4B — API OpenAI.

IS local — GPU NF4 (~2.7 Go VRAM), ~10s/image.
API compatible OpenAI Vision:
  POST /v1/chat/completions
  GET /health
  GET /v1/models
"""
import torch
import time
import base64
import io
import os
import uuid

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from PIL import Image
from transformers import (
    AutoProcessor,
    AutoModelForImageTextToText,
    BitsAndBytesConfig,
)
from typing import Optional

MODEL_ID = os.environ.get(
    "GRANITE_VISION_MODEL",
    "ibm-granite/granite-vision-4.1-4b")
PORT = int(os.environ.get("GRANITE_VISION_PORT", "8080"))

app = FastAPI(title="Granite Vision 4.1 4B")

model = None
processor = None
load_time = 0
inference_ok = False


class ImageUrl(BaseModel):
    url: str


class ContentPart(BaseModel):
    type: str
    text: Optional[str] = None
    image_url: Optional[ImageUrl] = None


class Message(BaseModel):
    role: str
    content: list[ContentPart] | str


class ChatRequest(BaseModel):
    model: str = MODEL_ID
    messages: list[Message]
    max_tokens: int = Field(default=2048)
    temperature: float = 0.0
    top_p: Optional[float] = None
    seed: Optional[int] = None


@app.on_event("startup")
def load_model():
    global model, processor, load_time
    device = "cuda" if torch.cuda.is_available() \
        else "cpu"
    print(f"Loading {MODEL_ID} on {device}...")

    if device == "cuda":
        free, total = torch.cuda.mem_get_info()
        print(f"VRAM: {round(free/1e9,2)} Go libre")

    t0 = time.time()
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    processor.tokenizer.padding_side = "left"

    if device == "cuda":
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
        )
        model = AutoModelForImageTextToText \
            .from_pretrained(
                MODEL_ID,
                quantization_config=bnb_config,
                device_map="cuda:0",
                torch_dtype=torch.float16,
            ).eval()
    else:
        model = AutoModelForImageTextToText \
            .from_pretrained(
                MODEL_ID,
                device_map="cpu",
                torch_dtype=torch.float32,
            ).eval()

    load_time = round(time.time() - t0, 1)
    print(f"Model loaded in {load_time}s")

    if device == "cuda":
        free2, _ = torch.cuda.mem_get_info()
        used = round((free - free2) / 1e9, 2)
        margin = round(free2 / 1e9, 2)
        print(f"VRAM used: {used} Go, "
              f"margin: {margin} Go")
        if margin < 1.0:
            print(f"WARNING: VRAM margin {margin} Go "
                  f"< 1.0 Go. High-res images may "
                  f"cause OOM (507). Free GPU memory "
                  f"by stopping other GPU processes.")

    global inference_ok
    try:
        probe_img = Image.new("RGB", (8, 8), "white")
        convs = [[{"role": "user", "content": [
            {"type": "image"},
            {"type": "text", "text": "ok"},
        ]}]]
        texts = [processor.apply_chat_template(
            c, tokenize=False,
            add_generation_prompt=True)
            for c in convs]
        dev = "cuda:0" if device == "cuda" else "cpu"
        inputs = processor(
            text=texts, images=[probe_img],
            return_tensors="pt", padding=True,
            do_pad=True).to(dev)
        with torch.inference_mode():
            model.generate(**inputs, max_new_tokens=1,
                           use_cache=True)
        if device == "cuda":
            torch.cuda.empty_cache()
        inference_ok = True
        print("Inference probe OK")
    except Exception as e:
        print(f"Inference probe FAILED: {e}")
        inference_ok = False


@app.get("/health")
def health():
    ready = model is not None and inference_ok
    result = {"status": "ok" if ready else "loading"}
    if model and torch.cuda.is_available():
        free, total = torch.cuda.mem_get_info()
        result["vram_margin_gb"] = round(free / 1e9, 2)
    return result


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [{
            "id": MODEL_ID,
            "object": "model",
            "owned_by": "ibm-granite",
        }],
    }


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    images = []
    prompt_parts = []
    has_image_placeholder = False

    for msg in req.messages:
        if isinstance(msg.content, str):
            prompt_parts.append(msg.content)
            continue
        for part in msg.content:
            if part.type == "text" and part.text:
                prompt_parts.append(part.text)
            elif part.type == "image_url" \
                    and part.image_url:
                url = part.image_url.url
                if url.startswith("data:"):
                    header, b64 = url.split(",", 1)
                    img_bytes = base64.b64decode(b64)
                    images.append(
                        Image.open(io.BytesIO(img_bytes))
                        .convert("RGB"))
                    has_image_placeholder = True
                else:
                    return JSONResponse(
                        status_code=400,
                        content={"error": {
                            "message": "Only base64 "
                            "data URIs supported",
                            "type": "invalid_request",
                        }})

    if not images:
        return JSONResponse(
            status_code=400,
            content={"error": {
                "message": "No image provided",
                "type": "invalid_request",
            }})

    prompt = " ".join(prompt_parts) or \
        "Describe this image in detail."

    conversations = [[{
        "role": "user",
        "content": [
            {"type": "image"},
            {"type": "text", "text": prompt},
        ],
    }]]
    texts = [processor.apply_chat_template(
        conv, tokenize=False,
        add_generation_prompt=True)
        for conv in conversations]

    device = next(model.parameters()).device
    img_info = (f"{images[0].size[0]}x"
                f"{images[0].size[1]}"
                if images else "?")

    if device.type == "cuda":
        if os.environ.get("EMPTY_CACHE"):
            torch.cuda.empty_cache()
        free, total = torch.cuda.mem_get_info()
        margin = round(free / 1e9, 2)
        print(f"[REQ] image={img_info}, "
              f"margin={margin} Go, "
              f"prompt={len(prompt)} chars")
    else:
        print(f"[REQ] image={img_info}, "
              f"prompt={len(prompt)} chars")

    try:
        inputs = processor(
            text=texts, images=images,
            return_tensors="pt", padding=True,
            do_pad=True,
        ).to(device)

        gen_kwargs = dict(
            max_new_tokens=req.max_tokens,
            use_cache=True)
        if req.temperature > 0:
            gen_kwargs["do_sample"] = True
            gen_kwargs["temperature"] = \
                req.temperature
        if req.top_p is not None:
            gen_kwargs["top_p"] = req.top_p
            gen_kwargs["do_sample"] = True
        if req.seed is not None:
            torch.manual_seed(req.seed)

        t0 = time.time()
        with torch.inference_mode():
            output = model.generate(
                **inputs, **gen_kwargs)
        dt = time.time() - t0
    except torch.cuda.OutOfMemoryError as oom:
        torch.cuda.empty_cache()
        free_oom, _ = torch.cuda.mem_get_info()
        return JSONResponse(
            status_code=507,
            content={"error": {
                "message": f"GPU out of memory "
                f"({img_info}). {oom}. "
                f"Free after cleanup: "
                f"{round(free_oom/1e9,2)} Go.",
                "type": "insufficient_storage",
            }})
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {
                "message": str(e),
                "type": "server_error",
            }})

    prompt_length = inputs["input_ids"].shape[1]
    result = processor.decode(
        output[0, prompt_length:],
        skip_special_tokens=True)

    completion_tokens = len(output[0]) - prompt_length

    return {
        "id": "chatcmpl-" + uuid.uuid4().hex[:12],
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": result,
            },
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": prompt_length,
            "completion_tokens": completion_tokens,
            "total_tokens":
                prompt_length + completion_tokens,
        },
        "time_s": round(dt, 1),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, host="0.0.0.0", port=PORT,
        timeout_keep_alive=300)
