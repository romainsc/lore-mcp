"""Serveur de captioning Molmo2-O 7B — API OpenAI.

IS local — CPU FP32, ~2 min/image.
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
)
from typing import Optional

MODEL_ID = os.environ.get(
    "MOLMO_MODEL", "allenai/Molmo2-O-7B")
PORT = int(os.environ.get("MOLMO_PORT", "8080"))

app = FastAPI(title="Molmo2-O Captioning")

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
    max_tokens: int = Field(default=500, alias="max_tokens")
    temperature: float = 1.0
    top_p: Optional[float] = None
    seed: Optional[int] = None


@app.on_event("startup")
def load_model():
    global model, processor, load_time
    print(f"Loading {MODEL_ID} (CPU FP32)...")
    t0 = time.time()
    processor = AutoProcessor.from_pretrained(
        MODEL_ID, trust_remote_code=True)
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID, trust_remote_code=True,
        torch_dtype=torch.float32, device_map="cpu")
    load_time = round(time.time() - t0, 1)
    print(f"Model loaded in {load_time}s")

    global inference_ok
    try:
        probe_img = Image.new("RGB", (8, 8), "white")
        msgs = [{"role": "user", "content": [
            dict(type="image", image=probe_img),
            dict(type="text", text="ok"),
        ]}]
        inputs = processor.apply_chat_template(
            msgs, tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt", return_dict=True)
        with torch.inference_mode():
            model.generate(**inputs, max_new_tokens=1)
        inference_ok = True
        print("Inference probe OK")
    except Exception as e:
        print(f"Inference probe FAILED: {e}")
        inference_ok = False


@app.get("/health")
def health():
    ready = model is not None and inference_ok
    return {"status": "ok" if ready else "loading"}


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [{
            "id": MODEL_ID,
            "object": "model",
            "owned_by": "allenai",
        }],
    }


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    images = []
    prompt_parts = []

    for msg in req.messages:
        if isinstance(msg.content, str):
            prompt_parts.append(msg.content)
            continue
        for part in msg.content:
            if part.type == "text" and part.text:
                prompt_parts.append(part.text)
            elif part.type == "image_url" and part.image_url:
                url = part.image_url.url
                if url.startswith("data:"):
                    header, b64 = url.split(",", 1)
                    img_bytes = base64.b64decode(b64)
                    images.append(
                        Image.open(io.BytesIO(img_bytes))
                        .convert("RGB"))
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

    molmo_content = []
    for img in images:
        molmo_content.append(
            dict(type="image", image=img))
    molmo_content.append(
        dict(type="text", text=prompt))

    messages = [{"role": "user", "content": molmo_content}]
    img_info = (f"{images[0].size[0]}x"
                f"{images[0].size[1]}"
                if images else "?")
    print(f"[REQ] image={img_info}, "
          f"prompt={len(prompt)} chars")
    try:
        inputs = processor.apply_chat_template(
            messages, tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt", return_dict=True)

        gen_kwargs = dict(
            max_new_tokens=req.max_tokens)
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
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {
                "message": str(e),
                "type": "server_error",
            }})

    tokens = output[0, inputs["input_ids"].size(1):]
    caption = processor.tokenizer.decode(
        tokens, skip_special_tokens=True)

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": caption,
            },
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": inputs["input_ids"].size(1),
            "completion_tokens": len(tokens),
            "total_tokens":
                inputs["input_ids"].size(1) + len(tokens),
        },
        "time_s": round(dt, 1),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, host="0.0.0.0", port=PORT,
        timeout_keep_alive=300)
