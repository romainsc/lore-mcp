"""Serveur granite-docling-258M — API OpenAI.

IS local — GPU FP16, conversion documentaire rapide.
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
from transformers import AutoProcessor, AutoModelForVision2Seq
from typing import Optional

MODEL_ID = os.environ.get(
    "DOCLING_MODEL", "ibm-granite/granite-docling-258M")
PORT = int(os.environ.get("DOCLING_PORT", "8080"))
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.bfloat16 if DEVICE == "cuda" else torch.float32
ATTN = "flash_attention_2" if DEVICE == "cuda" else "sdpa"

app = FastAPI(title="granite-docling-258M")

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
    max_tokens: int = Field(default=8192)
    temperature: float = 0.0
    top_p: Optional[float] = None
    seed: Optional[int] = None


@app.on_event("startup")
def load_model():
    global model, processor, load_time
    print(f"Loading {MODEL_ID} on {DEVICE} "
          f"({DTYPE})...")
    t0 = time.time()
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    try:
        model = AutoModelForVision2Seq.from_pretrained(
            MODEL_ID, torch_dtype=DTYPE,
            _attn_implementation=ATTN,
        ).to(DEVICE)
    except Exception:
        model = AutoModelForVision2Seq.from_pretrained(
            MODEL_ID, torch_dtype=DTYPE,
            _attn_implementation="sdpa",
        ).to(DEVICE)
    load_time = round(time.time() - t0, 1)
    print(f"Model loaded in {load_time}s on {DEVICE}")
    if DEVICE == "cuda":
        free, total = torch.cuda.mem_get_info()
        used = round((total - free) / 1e9, 2)
        print(f"VRAM: {used} Go")

    global inference_ok
    try:
        probe_img = Image.new("RGB", (8, 8), "white")
        msgs = [{"role": "user", "content": [
            {"type": "image"},
            {"type": "text", "text": "ok"},
        ]}]
        prompt = processor.apply_chat_template(
            msgs, add_generation_prompt=True)
        inputs = processor(
            text=prompt, images=[probe_img],
            return_tensors="pt").to(DEVICE)
        with torch.inference_mode():
            model.generate(**inputs, max_new_tokens=1)
        if DEVICE == "cuda":
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
    if model and DEVICE == "cuda":
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
    prompt_text = None

    for msg in req.messages:
        if isinstance(msg.content, str):
            prompt_text = msg.content
            continue
        for part in msg.content:
            if part.type == "text" and part.text:
                prompt_text = part.text
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
            elif part.type == "image":
                pass

    if not images:
        return JSONResponse(
            status_code=400,
            content={"error": {
                "message": "No image provided",
                "type": "invalid_request",
            }})

    if not prompt_text:
        prompt_text = "Convert this page to docling."

    messages_fmt = [{
        "role": "user",
        "content": [
            {"type": "image"},
            {"type": "text", "text": prompt_text},
        ],
    }]

    img_info = (f"{images[0].size[0]}x"
                f"{images[0].size[1]}"
                if images else "?")

    if DEVICE == "cuda":
        if os.environ.get("EMPTY_CACHE"):
            torch.cuda.empty_cache()
        free, total = torch.cuda.mem_get_info()
        margin = round(free / 1e9, 2)
        print(f"[REQ] image={img_info}, "
              f"margin={margin} Go")
    else:
        print(f"[REQ] image={img_info}")

    try:
        prompt = processor.apply_chat_template(
            messages_fmt, add_generation_prompt=True)
        inputs = processor(
            text=prompt, images=images,
            return_tensors="pt").to(DEVICE)

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

    prompt_length = inputs.input_ids.shape[1]
    trimmed = output[:, prompt_length:]
    doctags = processor.batch_decode(
        trimmed, skip_special_tokens=False)[0].lstrip()

    md_output = doctags
    try:
        from docling_core.types.doc import DoclingDocument
        from docling_core.types.doc.document import (
            DocTagsDocument,
        )
        doctags_doc = (
            DocTagsDocument.from_doctags_and_image_pairs(
                [doctags], images))
        doc = DoclingDocument.load_from_doctags(
            doctags_doc, document_name="Document")
        md_output = doc.export_to_markdown()
    except ImportError:
        pass

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": md_output,
            },
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": prompt_length,
            "completion_tokens": len(trimmed[0]),
            "total_tokens": prompt_length + len(trimmed[0]),
        },
        "time_s": round(dt, 1),
        "doctags": doctags,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, host="0.0.0.0", port=PORT,
        timeout_keep_alive=300)
