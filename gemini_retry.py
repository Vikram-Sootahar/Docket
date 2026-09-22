"""Gemini helper: picks a model from a fallback chain and moves on when one is busy or out of quota.

Free-tier limits are counted per model, so trying the next model keeps the app working."""

import time

MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
]

_FALLBACK_ERRORS = ("429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE", "500", "INTERNAL", "404", "NOT_FOUND")
_cooldown_until = {}


def generate_with_retry(**kwargs):
    from ai_chat import client

    kwargs.pop("model", None)
    models = kwargs.pop("models", None) or MODELS
    last_error = None

    for model in models:
        if _cooldown_until.get(model, 0) > time.time():
            continue
        try:
            response = client.models.generate_content(model=model, **kwargs)
            print(f"[GEMINI] used {model}")
            return response
        except Exception as e:
            text = str(e)
            last_error = e
            if not any(code in text for code in _FALLBACK_ERRORS):
                raise
            if "429" in text or "RESOURCE_EXHAUSTED" in text:
                _cooldown_until[model] = time.time() + (3600 if "PerDay" in text else 60)
            else:
                _cooldown_until[model] = time.time() + 20
            print(f"[GEMINI] {model} unavailable, trying the next model")

    if last_error is not None:
        raise last_error
    raise Exception("429 RESOURCE_EXHAUSTED: all models are cooling down, try again in a minute")