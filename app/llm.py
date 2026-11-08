import re
from openai import OpenAI
from . import config

_client = None
_resolved = None


def client():
    global _client
    if _client is None:
        if not config.VULTR_API_KEY:
            raise RuntimeError("VULTR_INFERENCE_API_KEY is not set. Add it to .env")
        _client = OpenAI(api_key=config.VULTR_API_KEY, base_url=config.VULTR_BASE_URL,
                         timeout=90, max_retries=1)
    return _client


def list_models():
    return [m.id for m in client().models.list().data]


def resolve_model():
    """Use VULTR_MODEL if it exists on Vultr, otherwise pick a sensible chat model from the live list."""
    global _resolved
    if _resolved:
        return _resolved
    try:
        ids = list_models()
        if config.VULTR_MODEL in ids:
            _resolved = config.VULTR_MODEL
        else:
            chat = [i for i in ids if not any(x in i.lower() for x in ("embed", "bge", "rerank", "whisper", "image", "flux", "sdxl"))]
            coder = [i for i in chat if "coder" in i.lower()]
            _resolved = (coder or chat or ids)[0]
    except Exception:
        _resolved = config.VULTR_MODEL
    return _resolved


def chat(messages, temperature=0.1, max_tokens=1800):
    r = client().chat.completions.create(
        model=resolve_model(), messages=messages,
        temperature=temperature, max_tokens=max_tokens,
    )
    text = r.choices[0].message.content or ""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
