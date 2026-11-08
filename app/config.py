import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

VULTR_API_KEY = os.getenv("VULTR_INFERENCE_API_KEY", "")
VULTR_BASE_URL = os.getenv("VULTR_INFERENCE_BASE_URL", "https://api.vultrinference.com/v1")
VULTR_MODEL = os.getenv("VULTR_MODEL", "Qwen2.5-Coder-32B-Instruct")

SANDBOX_IMAGE = os.getenv("SANDBOX_IMAGE", "brz-sandbox:latest")
SANDBOX_TIMEOUT = int(os.getenv("SANDBOX_TIMEOUT_SEC", "20"))
SANDBOX_MEMORY = os.getenv("SANDBOX_MEMORY", "256m")
SANDBOX_CPUS = os.getenv("SANDBOX_CPUS", "0.5")
SANDBOX_PIDS = os.getenv("SANDBOX_PIDS", "64")
SANDBOX_RUNTIME = os.getenv("SANDBOX_RUNTIME", "").strip()

MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "5")) * 1024 * 1024
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_RUNS", "2"))
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "12"))

SANDBOX_MODE = os.getenv("SANDBOX_MODE", "auto").strip().lower()  # auto | docker | local
if SANDBOX_MODE == "auto":
    SANDBOX_MODE = "docker" if shutil.which("docker") else "local"  # local = restricted mode (no Docker)
LOCAL_MEMORY_MB = int(os.getenv("LOCAL_MEMORY_MB", "800"))
