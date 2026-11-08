import threading
import time
from collections import defaultdict, deque

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

from . import agent, config, llm, probes, sandbox

app = FastAPI(title="Blast Radius Zero", version="1.0.0")
_slots = threading.BoundedSemaphore(config.MAX_CONCURRENT)
_hits = defaultdict(deque)


def _guard(request: Request):
    fwd = request.headers.get("x-forwarded-for")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= config.RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "Too many runs. Wait a minute and try again.")
    q.append(now)


def _with_slot(fn, *a, **kw):
    if not _slots.acquire(timeout=30):
        raise HTTPException(503, "All sandboxes are busy. Try again in a moment.")
    try:
        return fn(*a, **kw)
    finally:
        _slots.release()


@app.get("/")
def index():
    return FileResponse(config.BASE_DIR / "frontend" / "index.html")


@app.get("/api/samples/sales.csv")
def sample():
    return FileResponse(config.BASE_DIR / "samples" / "sales.csv", media_type="text/csv", filename="sales.csv")


@app.get("/api/health")
def health():
    st = sandbox.docker_status()
    return {"ok": st["docker"] and st["image_built"], **st,
            "inference_key_set": bool(config.VULTR_API_KEY),
            "mode": config.SANDBOX_MODE, "limits": sandbox.limits(), "max_attempts": config.MAX_ATTEMPTS}


@app.get("/api/models")
def models():
    try:
        return {"configured": config.VULTR_MODEL, "using": llm.resolve_model(), "available": llm.list_models()}
    except Exception as e:
        raise HTTPException(502, f"Vultr Inference error: {e}")


@app.post("/api/analyze")
async def analyze(request: Request, question: str = Form(...), file: UploadFile | None = File(None)):
    _guard(request)
    question = question.strip()
    if not question or len(question) > 1000:
        raise HTTPException(400, "Question must be 1-1000 characters.")
    data = None
    if file is not None and file.filename:
        data = await file.read()
        if len(data) > config.MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"File too large (limit {config.MAX_UPLOAD_BYTES // 1024 // 1024} MB).")
    try:
        return await run_in_threadpool(_with_slot, agent.analyze, question, data, file.filename if file else None)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Run failed: {e}")


@app.get("/api/probes")
def list_probes():
    return probes.public_list()


@app.post("/api/probes/{pid}")
async def run_probe(pid: str, request: Request):
    if pid not in probes.PROBES:
        raise HTTPException(404, "Unknown probe")
    _guard(request)
    return await run_in_threadpool(_with_slot, probes.run_probe, pid)
